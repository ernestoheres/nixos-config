#!/usr/bin/env python3
"""Launch and reuse project workspaces; keep project environments out of desktop apps."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid


class ContextError(Exception):
    pass


def run(command, **kwargs):
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=10, **kwargs)
    except subprocess.TimeoutExpired as error:
        raise ContextError("Hyprland did not respond within 10 seconds.") from error
    if result.returncode:
        raise ContextError(result.stderr.strip() or result.stdout.strip() or str(command))
    return result.stdout


class Hyprland:
    def __init__(self, executable):
        self.executable = executable
        self.lua = "configProvider: lua" in run([executable, "status"])

    def clients(self):
        return [c for c in json.loads(run([self.executable, "-j", "clients"])) if c["mapped"]]

    def dispatch(self, expression, legacy, argument):
        command = [self.executable, "dispatch"]
        command += [expression] if self.lua else [legacy, argument]
        response = run(command).strip()
        # Some Hyprland errors have exit status zero.
        if response != "ok":
            raise ContextError(f"Hyprland: {response}")

    def focus(self, workspace):
        target = f"name:{workspace}"
        self.dispatch(
            f"hl.dsp.focus({{ workspace = {json.dumps(target)} }})", "workspace", target
        )

    def move(self, client, workspace):
        if client["workspace"]["name"] == workspace:
            return
        target = f"name:{workspace}"
        selector = f"address:{client['address']}"
        self.dispatch(
            "hl.dsp.window.move({ workspace = " + json.dumps(target)
            + ", window = " + json.dumps(selector) + ", follow = false })",
            "movetoworkspacesilent", f"{target},{selector}",
        )


def identity(client):
    return {key: client.get(key) for key in ("address", "pid", "stableId")}


def find_record(clients, record):
    return next((c for c in clients if identity(c) == record), None)


def process_identity(pid):
    try:
        # The command name in /proc/PID/stat may itself contain spaces/parentheses.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": pid, "start": fields[19]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def process_alive(record):
    return bool(record and process_identity(record["pid"]) == record)


@contextlib.contextmanager
def locked(path, timeout=60):
    with path.open("a") as file:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ContextError("Another context operation is still running. Try again shortly.")
                time.sleep(0.1)
        yield


class Context:
    def __init__(self, config_path, name):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise ContextError("Context IDs must contain only letters, numbers, '-' or '_'.")
        self.config_path = Path(config_path).resolve()
        manifest = json.loads(self.config_path.read_text())
        if name not in manifest["contexts"]:
            raise ContextError(f"Unknown context: {name}")
        self.name = name
        self.config = manifest["contexts"][name]
        self.tools = manifest["tools"]
        self.directory = Path(self.config["directory"]).expanduser().resolve()
        signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if not signature or not runtime:
            raise ContextError("Run project-context inside your Hyprland desktop session.")
        session = hashlib.sha256(signature.encode()).hexdigest()[:16]
        self.runtime_root = Path(runtime) / "project-contexts" / session
        self.runtime = self.runtime_root / name
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_path = self.runtime / "state.json"
        self.lock_path = self.runtime / "launch.lock"
        self.hypr = Hyprland(self.tools["hyprctl"])

    def load(self):
        if not self.state_path.exists():
            return {"windows": {}}
        return json.loads(self.state_path.read_text())

    def save(self, state):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state))
        temporary.chmod(0o600)
        temporary.replace(self.state_path)

    def helper(self, *arguments):
        return [sys.executable, str(Path(__file__).resolve()), "--config",
                str(self.config_path), *arguments]

    def notify(self, message):
        try:
            subprocess.run(
                [self.tools["notifySend"], "--app-name=Project contexts",
                 self.config["name"], message], check=False, timeout=5,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass  # Error reporting must not prevent the launcher from exiting.

    def wait_for_window(self, predicate, process=None, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            candidates = [c for c in self.hypr.clients() if predicate(c)]
            if len(candidates) == 1:
                self.hypr.move(candidates[0], self.config["workspace"])
                return candidates[0]
            if len(candidates) > 1:
                raise ContextError("More than one new matching window; cannot identify the context window.")
            if process is not None and process.poll() not in (None, 0):
                raise ContextError(f"Application exited with status {process.returncode} before opening a window.")
            time.sleep(0.1)
        raise ContextError("Timed out waiting for a context window.")

    def terminal(self, role, generation, environment):
        app_class = f"project-context-{self.name}-{role}"
        existing = next((c for c in self.hypr.clients() if c["class"] == app_class), None)
        if existing:
            self.hypr.move(existing, self.config["workspace"])
            return existing
        command = self.config["terminal"] + [
            "--class", app_class, "--title", f"{self.config['name']} — {role}",
            "--directory", str(self.directory),
        ] + self.helper("_run", self.name, role, generation)
        # A desktop terminal must not inherit the caller's pipes: otherwise a
        # CLI/launcher waiting for EOF appears hung for the terminal's lifetime.
        with (self.runtime / "launcher.log").open("a") as log:
            process = subprocess.Popen(
                command, env=environment, start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            )
        return self.wait_for_window(lambda c: c["class"] == app_class, process)

    def application(self, application, state, extra_arguments=()):
        existing = find_record(self.hypr.clients(), state["windows"].get(application["id"]))
        if existing:
            self.hypr.move(existing, self.config["workspace"])
            return existing
        # Firefox's remote command exits immediately, while the existing browser
        # process creates the new window. Compare window identities, not child PIDs.
        with locked(self.runtime_root / "application.lock"):
            before = {c["address"] for c in self.hypr.clients()}
            process = subprocess.Popen(
                application["command"] + list(extra_arguments), cwd=self.directory,
                env=state["desktopEnvironment"], start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return self.wait_for_window(
                lambda c: c["address"] not in before and c["class"] == application["class"], process
            )

    def launch(self):
        if not self.directory.is_dir():
            raise ContextError(f"Project directory does not exist: {self.directory}")
        with locked(self.lock_path):
            state = self.load()
            self.hypr.focus(self.config["workspace"])
            supervisor_class = f"project-context-{self.name}-supervisor"
            supervisor = next((c for c in self.hypr.clients() if c["class"] == supervisor_class), None)
            if not supervisor and not process_alive(state.get("supervisor")):
                state = {"windows": {}, "generation": uuid.uuid4().hex,
                         "desktopEnvironment": dict(os.environ)}
                self.save(state)
            generation = state["generation"]
            for role in ("supervisor", "shell"):
                if role == "supervisor" and not supervisor and process_alive(state.get("supervisor")):
                    # A detached supervisor must not be started a second time.
                    continue
                client = self.terminal(role, generation, state["desktopEnvironment"])
                state["windows"][role] = identity(client)
            for application in self.config.get("applications", []):
                state["windows"][application["id"]] = identity(self.application(application, state))
            if state.get("url") and process_alive(state.get("supervisor")):
                application = dict(self.config["browser"], id="browser")
                state["windows"]["browser"] = identity(self.application(application, state, [state["url"]]))
            self.save(state)

    def open_url(self, generation, url):
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            # Only the localhost notebook URL belongs to this workspace.
            state = self.load()
            subprocess.Popen(
                [self.tools["xdgOpen"], url], env=state["desktopEnvironment"],
                start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return
        with locked(self.lock_path):
            state = self.load()
            if generation != state.get("generation"):
                return
            state["url"] = url
            # Persist the URL even if Firefox fails, so the next launch can retry.
            self.save(state)
            application = dict(self.config["browser"], id="browser")
            state["windows"]["browser"] = identity(self.application(application, state, [url]))
            self.save(state)

    def run_terminal(self, role, generation):
        # A separate lock covers the entire supervisor lifetime, including direnv
        # setup. A rapid second launch cannot start another Process Compose.
        lock_path = self.runtime / f"{role}.lock"
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            with locked(self.lock_path):
                state = self.load()
                if generation != state.get("generation"):
                    return 0
                if role == "supervisor":
                    state["supervisor"] = process_identity(os.getpid())
                    self.save(state)
            os.chdir(self.directory)
            # Load direnv explicitly: shell prompt hooks don't run for nix run.
            result = subprocess.run(
                [self.tools["direnv"], "exec", str(self.directory), "env", "-0"],
                env=state["desktopEnvironment"], stdout=subprocess.PIPE,
            )
            if result.returncode:
                raise ContextError("direnv could not load the project environment. See the terminal output.")
            environment = dict(item.decode().split("=", 1) for item in result.stdout.split(b"\0") if item)
            if role == "shell":
                command = self.config["shell"]
            else:
                environment.update(self.config["supervisor"].get("environment", {}))
                if self.config.get("browser"):
                    opener_dir = self.runtime / generation / "bin"
                    opener_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                    opener = opener_dir / "xdg-open"
                    opener.write_text(
                        f"#!{self.tools['bash']}\nexec "
                        + shlex.join(self.helper("open-url", self.name, generation)) + ' "$@"\n'
                    )
                    opener.chmod(0o700)
                    environment["PATH"] = str(opener_dir) + os.pathsep + environment["PATH"]
                command = self.config["supervisor"]["command"]
            process = subprocess.Popen(command, env=environment)
            # The terminal's process group delivers Ctrl-C to both processes.
            # On terminal close, forward HUP/TERM too and reap the supervisor.
            def stop(signum, _frame):
                if process.poll() is None:
                    process.send_signal(signum)

            for signum in (signal.SIGHUP, signal.SIGTERM):
                signal.signal(signum, stop)
            try:
                code = process.wait()
            except KeyboardInterrupt:
                code = process.wait()
            if code and role == "supervisor":
                self.notify(f"Supervisor stopped (exit {code}). Relaunch the context to retry.")
            return code

    def status(self):
        state = self.load()
        clients = self.hypr.clients()
        result = {
            "context": self.name, "directory": str(self.directory),
            "workspace": self.config["workspace"],
            "supervisorRunning": process_alive(state.get("supervisor")),
            "windows": {role: bool(find_record(clients, record))
                        for role, record in state["windows"].items()},
        }
        if state.get("url"):
            result["notebookUrl"] = state["url"].split("?", 1)[0]
        print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
                                               / "project-contexts/contexts.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List available project contexts")
    for command in ("launch", "status"):
        commands.add_parser(command).add_argument("context")
    opener = commands.add_parser("open-url", help=argparse.SUPPRESS)
    opener.add_argument("context")
    opener.add_argument("generation")
    opener.add_argument("url")
    runner = commands.add_parser("_run", help=argparse.SUPPRESS)
    runner.add_argument("context")
    runner.add_argument("role", choices=("supervisor", "shell"))
    runner.add_argument("generation")
    args = parser.parse_args()
    os.umask(0o077)
    context = None
    try:
        if args.command == "list":
            manifest = json.loads(Path(args.config).read_text())
            for name, config in manifest["contexts"].items():
                print(f"{name}\t{config['name']}\t{config['directory']}")
            return 0
        context = Context(args.config, args.context)
        if args.command == "launch":
            context.launch()
        elif args.command == "status":
            context.status()
        elif args.command == "open-url":
            context.open_url(args.generation, args.url)
        else:
            return context.run_terminal(args.role, args.generation)
        return 0
    except (ContextError, OSError, ValueError, KeyError) as error:
        print(f"project-context: {error}", file=sys.stderr)
        if context is not None:
            context.notify(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
