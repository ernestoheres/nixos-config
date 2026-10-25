{
  config,
  lib,
  pkgs,
  ...
}: let
  # Add another entry here to expose another project in Caelestia's app search.
  contexts = {
    awl = {
      name = "AWL Context";
      description = "AWL workspace: Process Compose, project terminal, and Marimo notebook";
      directory = "${config.home.homeDirectory}/AWL-Material-Shape-Package-Cv";
      workspace = "AWL";
      terminal = ["${pkgs.kitty}/bin/kitty"];
      shell = ["${pkgs.zsh}/bin/zsh" "-i"];
      supervisor = {
        command = ["${pkgs.nix}/bin/nix" "run" ".#process-compose"];
        environment = {
          NOTEBOOK_FILE = "awl-cv.py";
          NOTEBOOK_PROJECT_ROOT = "${config.home.homeDirectory}/AWL-Material-Shape-Package-Cv";
        };
      };
      browser = {
        command = ["${lib.getExe pkgs.firefox}" "--new-window"];
        class = "firefox";
      };
      # Extra desktop applications can be added as { id; command; class; }.
      applications = [];
    };
  };
  manifest = pkgs.writeText "project-contexts.json" (builtins.toJSON {
    inherit contexts;
    tools = {
      hyprctl = "${pkgs.hyprland}/bin/hyprctl";
      direnv = "${pkgs.direnv}/bin/direnv";
      xdgOpen = "${pkgs.xdg-utils}/bin/xdg-open";
      notifySend = "${pkgs.libnotify}/bin/notify-send";
      bash = "${pkgs.bash}/bin/bash";
    };
  });
  launcher = pkgs.writeShellScriptBin "project-context" ''
    exec ${pkgs.python3}/bin/python3 ${./project-context.py} --config ${manifest} "$@"
  '';
in {
  home.packages = [launcher];
  xdg.configFile."project-contexts/contexts.json".source = manifest;
  xdg.desktopEntries = lib.mapAttrs' (id: context:
    lib.nameValuePair "project-context-${id}" {
      inherit (context) name;
      comment = context.description;
      exec = "${launcher}/bin/project-context launch ${id}";
      icon = "folder-development";
      terminal = false;
      categories = ["Development"];
      settings.Keywords = "${id};context;workspace;project;";
    })
  contexts;
}
