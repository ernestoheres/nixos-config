# Project contexts

Search for **AWL Context** in Caelestia and press Enter. This focuses a named
`AWL` workspace and opens:

- A Kitty terminal running `nix run .#process-compose`, with `NOTEBOOK_FILE=awl-cv.py`.
- A normal Zsh terminal in `~/AWL-Material-Shape-Package-Cv`.
- A new Firefox window for the notebook, once Marimo starts.

Both terminals explicitly load the project's direnv environment. Marimo supplies
its actual browser URL (including the selected port and access token) through a
context-scoped `xdg-open` wrapper. Firefox and other desktop applications use the
original desktop environment rather than the project's CUDA/Python environment.

Selecting the context again reuses its terminals and browser. Missing windows
are restored; a running supervisor is never started twice. Closing the supervisor
terminal stops its processes. Closing the browser leaves the supervisor running;
select the context again to reopen the notebook.

## Configuration

Define contexts in `contexts.nix`. Each entry produces a desktop entry and is
available to the command-line helper:

```sh
project-context list
project-context launch awl
project-context status awl
```

The generated manifest is `~/.config/project-contexts/contexts.json`. Terminal
commands currently use Kitty's `--class`, `--title`, and `--directory` options.
Browser commands must create a new window (Firefox uses `--new-window`).

Additional standard applications can be configured per context:

```nix
applications = [
  {
    id = "files";
    command = [ "${pkgs.thunar}/bin/thunar" directory ];
    class = "thunar";
  }
];
```

An application's `class` must match its Hyprland client class. The launcher tracks
the particular window it opened, so it does not move unrelated existing windows.
Applications that reuse an existing window instead of creating one need an
appropriate new-window flag.

Apply the Home Manager configuration with a NixOS rebuild. From the repository
root, the explicit path form also includes newly added, untracked module files:

```sh
sudo nixos-rebuild switch --flake "path:$PWD#default"
```

If direnv reports that the project's `.envrc` is blocked, allow it from the project
directory with `direnv allow` and launch the context again.

## Verification

```sh
python3 -B -m unittest discover -s modules/home -p 'test_project_context.py' -v
```

Session state lives under `$XDG_RUNTIME_DIR/project-contexts/` and expires with the
desktop session. Its files are private because the browser URL contains a token.
`status` omits the token from its output. Terminal-launch diagnostics are written
to the context's `launcher.log` there, so desktop windows do not keep the calling
command's output streams open. Lock waits and Hyprland requests have timeouts.
