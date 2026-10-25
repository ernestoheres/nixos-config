"""Lifecycle tests without launching desktop windows or project services."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("project_context", Path(__file__).with_name("project-context.py"))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def client(address, app_class, workspace="other"):
    return {"address": address, "pid": 10, "stableId": address,
            "class": app_class, "mapped": True, "workspace": {"name": workspace}}


class FakeHyprland:
    def __init__(self, _executable):
        self.windows = []
        self.focused = None

    def clients(self):
        return self.windows[:]

    def focus(self, workspace):
        self.focused = workspace

    def move(self, window, workspace):
        window["workspace"]["name"] = workspace


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root / "contexts.json"
        self.manifest.write_text(json.dumps({
            "contexts": {"awl": {
                "name": "AWL Context", "directory": str(self.root), "workspace": "AWL",
                "terminal": ["kitty"], "shell": ["zsh", "-i"],
                "supervisor": {"command": ["nix", "run", ".#process-compose"],
                               "environment": {"NOTEBOOK_FILE": "awl-cv.py"}},
                "browser": {"command": ["firefox", "--new-window"], "class": "firefox"},
            }},
            "tools": {"hyprctl": "hyprctl", "direnv": "direnv", "bash": "/bin/bash",
                      "xdgOpen": "/host/xdg-open", "notifySend": "notify-send"},
        }))
        environment = patch.dict(os.environ, {
            "XDG_RUNTIME_DIR": str(self.root), "HYPRLAND_INSTANCE_SIGNATURE": "test-session",
            "DESKTOP_ONLY": "host",
        })
        environment.start()
        self.addCleanup(environment.stop)
        hypr = patch.object(launcher, "Hyprland", FakeHyprland)
        hypr.start()
        self.addCleanup(hypr.stop)
        self.context = launcher.Context(self.manifest, "awl")

    def seed(self):
        state = {"windows": {}, "generation": "generation-one",
                 "desktopEnvironment": {"PATH": "/host/bin", "DESKTOP_ONLY": "host"}}
        self.context.save(state)
        return state

    def spawn(self, command, **kwargs):
        if command[0] == "kitty":
            app_class = command[command.index("--class") + 1]
        elif command[0] == "firefox":
            app_class = "firefox"
        else:
            self.fail(f"Unexpected application: {command}")
        self.context.hypr.windows.append(client(str(len(self.context.hypr.windows)), app_class))
        process = unittest.mock.Mock()
        process.poll.return_value = 0
        return process

    def test_repeated_launch_reuses_windows_and_does_not_restart_supervisor(self):
        with patch.object(launcher.subprocess, "Popen", side_effect=self.spawn) as spawn:
            self.context.launch()
            self.context.launch()
        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(self.context.hypr.focused, "AWL")
        self.assertTrue(all(c["workspace"]["name"] == "AWL" for c in self.context.hypr.clients()))

    def test_relaunch_restores_only_missing_terminal(self):
        with patch.object(launcher.subprocess, "Popen", side_effect=self.spawn) as spawn:
            self.context.launch()
            self.context.hypr.windows = [c for c in self.context.hypr.windows if c["class"].endswith("supervisor")]
            self.context.launch()
        self.assertEqual(spawn.call_count, 3)
        self.assertEqual(len(self.context.hypr.windows), 2)

    def test_desktop_terminals_do_not_hold_the_launchers_stdio_open(self):
        with patch.object(launcher.subprocess, "Popen", side_effect=self.spawn) as spawn:
            self.context.launch()
        for call in spawn.call_args_list:
            self.assertEqual(call.kwargs["stdin"], subprocess.DEVNULL)
            self.assertIsNotNone(call.kwargs["stdout"])
            self.assertIsNotNone(call.kwargs["stderr"])
            self.assertTrue(call.kwargs["start_new_session"])

    def test_competing_operation_has_a_bounded_lock_wait(self):
        with launcher.locked(self.context.lock_path):
            with self.assertRaisesRegex(launcher.ContextError, "still running"):
                with launcher.locked(self.context.lock_path, timeout=0):
                    self.fail("The competing operation acquired an already-held lock")

    def test_notebook_callback_preserves_actual_url_and_desktop_environment(self):
        self.seed()
        unrelated = client("existing", "firefox", "browser-workspace")
        self.context.hypr.windows.append(unrelated)
        url = "http://localhost:2721?access_token=real-token"
        with patch.object(launcher.subprocess, "Popen", side_effect=self.spawn) as spawn:
            self.context.open_url("generation-one", url)
            self.context.open_url("generation-one", url)
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(spawn.call_args.args[0], ["firefox", "--new-window", url])
        self.assertEqual(spawn.call_args.kwargs["env"], {"PATH": "/host/bin", "DESKTOP_ONLY": "host"})
        self.assertEqual(unrelated["workspace"]["name"], "browser-workspace")
        self.assertEqual(self.context.hypr.windows[-1]["workspace"]["name"], "AWL")
        self.assertEqual(self.context.load()["url"], url)

    def test_stale_callback_cannot_open_old_notebook(self):
        self.seed()
        with patch.object(launcher.subprocess, "Popen") as spawn:
            self.context.open_url("old-generation", "http://localhost:2718?access_token=old")
        spawn.assert_not_called()
        self.assertNotIn("url", self.context.load())

    def test_reused_window_address_does_not_claim_unrelated_window(self):
        original = client("same-address", "firefox")
        record = launcher.identity(original)
        replacement = dict(original, stableId="new-window")
        self.assertIsNone(launcher.find_record([replacement], record))

    def test_restore_browser_without_starting_another_supervisor(self):
        with patch.object(launcher.subprocess, "Popen", side_effect=self.spawn) as spawn:
            self.context.launch()
            state = self.context.load()
            state["url"] = "http://localhost:2720?access_token=retained"
            state["supervisor"] = launcher.process_identity(os.getpid())
            self.context.save(state)
            self.context.launch()
            self.context.hypr.windows = [c for c in self.context.hypr.windows if c["class"] != "firefox"]
            self.context.launch()
        self.assertEqual(spawn.call_count, 4)  # Two terminals, initial browser, restored browser.

    def test_runner_loads_direnv_before_nix_and_installs_scoped_opener(self):
        self.seed()
        environment = b"PATH=/project/bin\0VIRTUAL_ENV=/project/.venv\0LD_LIBRARY_PATH=/cuda/lib\0"
        process = unittest.mock.Mock()
        process.wait.return_value = 0
        # Avoid changing the test process's working directory or signal handlers.
        with patch.object(launcher.os, "chdir") as chdir, \
             patch.object(launcher.signal, "signal"), \
             patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, environment)) as load, \
             patch.object(launcher.subprocess, "Popen", return_value=process) as spawn:
            self.assertEqual(self.context.run_terminal("supervisor", "generation-one"), 0)
        chdir.assert_called_once_with(self.root)
        self.assertEqual(load.call_args.args[0], ["direnv", "exec", str(self.root), "env", "-0"])
        self.assertEqual(spawn.call_args.args[0], ["nix", "run", ".#process-compose"])
        runtime_env = spawn.call_args.kwargs["env"]
        self.assertEqual(runtime_env["NOTEBOOK_FILE"], "awl-cv.py")
        self.assertEqual(runtime_env["LD_LIBRARY_PATH"], "/cuda/lib")
        opener = Path(runtime_env["PATH"].split(":", 1)[0]) / "xdg-open"
        self.assertIn('open-url awl generation-one "$@"', opener.read_text())
        self.assertEqual(self.context.load()["desktopEnvironment"]["PATH"], "/host/bin")

    def test_supervisor_lifetime_lock_prevents_duplicate_services(self):
        self.seed()
        with launcher.locked(self.context.runtime / "supervisor.lock"):
            with patch.object(launcher.subprocess, "Popen") as spawn:
                self.assertEqual(self.context.run_terminal("supervisor", "generation-one"), 0)
        spawn.assert_not_called()

    def test_runtime_url_and_environment_file_is_private(self):
        self.seed()
        self.assertEqual(self.context.state_path.stat().st_mode & 0o777, 0o600)


class HyprlandTests(unittest.TestCase):
    def test_unresponsive_hyprland_does_not_hang_forever(self):
        with patch.object(launcher.subprocess, "run", side_effect=subprocess.TimeoutExpired("hyprctl", 10)):
            with self.assertRaisesRegex(launcher.ContextError, "within 10 seconds"):
                launcher.run(["hyprctl", "status"])

    def test_lua_moves_explicit_window_without_changing_focus(self):
        with patch.object(launcher, "run", side_effect=["configProvider: lua", "ok", "ok"]) as run:
            hypr = launcher.Hyprland("hyprctl")
            hypr.focus("AWL")
            hypr.move(client("0x123", "kitty"), "AWL")
        expression = run.call_args.args[0][-1]
        self.assertIn('window = "address:0x123"', expression)
        self.assertIn("follow = false", expression)

    def test_legacy_moves_explicit_window_without_changing_focus(self):
        with patch.object(launcher, "run", side_effect=["configProvider: hyprlang", "ok"]) as run:
            hypr = launcher.Hyprland("hyprctl")
            hypr.move(client("0x123", "kitty"), "AWL")
        self.assertEqual(run.call_args.args[0], ["hyprctl", "dispatch", "movetoworkspacesilent", "name:AWL,address:0x123"])


if __name__ == "__main__":
    unittest.main()
