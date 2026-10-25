{
  description = "KooL's NixOS-Hyprland";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
    home-manager.url = "github:nix-community/home-manager/release-26.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    nixvim.url = "github:nix-community/nixvim/nixos-26.05";
    #hyprland.url = "github:hyprwm/Hyprland"; # hyprland development
    alejandra.url = "github:kamadorueda/alejandra";
    sops-nix.url = "github:Mic92/sops-nix";
    codex-desktop-linux.url = "github:ilysenko/codex-desktop-linux";
    opencode = {
      url = "github:anomalyco/opencode";
      #temp fix
    };
    ags = {
      type = "github";
      owner = "aylur";
      repo = "ags";
      ref = "v1";
    };

    catppuccin = {
      url = "github:catppuccin/nix/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    quickshell = {
      url = "git+https://git.outfoxxed.me/outfoxxed/quickshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Keep Caelestia's own Quickshell/Qt package set together.
    caelestia-shell.url = "github:caelestia-dots/shell/20e625d6bf1a9d0bb7625a4bb814797d187b075d";
  };

  outputs =
    inputs @ { self
    , nixpkgs
    , ags
    , alejandra
    , opencode
    , ...
    }:
    let
      system = "x86_64-linux";
      host = "default";
      username = "ernestoh";

      pkgs = import nixpkgs {
        inherit system;
        config = {
          allowUnfree = true;
        };
      };
    in
    {
      nixosConfigurations = {
        "${host}" = nixpkgs.lib.nixosSystem rec {
          specialArgs = {
            inherit system;
            inherit inputs;
            inherit username;
            inherit host;
          };
          modules = [
            ./hosts/${host}/config.nix
            ./modules/nvidia-drivers.nix
            # inputs.distro-grub-themes.nixosModules.${system}.default
            ./modules/overlays.nix # nixpkgs overlays (CMake policy fixes)
            ./modules/quickshell.nix # quickshell module
            ./modules/packages.nix # Software packages
            # Allow broken packages (temporary fix for broken CUDA in nixos-unstable)
            { nixpkgs.config.allowBroken = true; }
            ./modules/fonts.nix # Fonts packages
            ./modules/portals.nix # portal
            ./modules/theme.nix # Set dark theme
            ./modules/ly.nix # ly greater with matrix animation
            ./modules/nh.nix # nix helper
            inputs.codex-desktop-linux.nixosModules.default
            ./modules/codex-desktop.nix # Codex Desktop
            inputs.catppuccin.nixosModules.catppuccin
            inputs.sops-nix.nixosModules.sops
            # Integrate Home Manager as a NixOS module
            inputs.home-manager.nixosModules.home-manager
            {
              home-manager.useGlobalPkgs = true;
              home-manager.useUserPackages = true;
              home-manager.backupFileExtension = "hm-bak";

              # Ensure HM modules can access flake inputs (e.g., inputs.nixvim)
              home-manager.extraSpecialArgs = { inherit inputs system username host; };

              home-manager.users.${username} = {
                home.username = username;
                home.homeDirectory = "/home/${username}";
                home.stateVersion = "24.05";
                home.packages = [
                  (inputs.caelestia-shell.packages.${system}.with-cli.overrideAttrs (old: {
                    patches = (old.patches or [ ]) ++ [
                      ./modules/home/caelestia-workspace-shapes.patch
                      ./modules/home/caelestia-lock-no-notifs-gif.patch
                      ./modules/home/caelestia-lock-intro-gif.patch
                      ./modules/home/caelestia-notification-restore.patch
                    ];
                  }))
                  inputs.caelestia-shell.inputs.caelestia-cli.packages.${system}.default
                ];

                # Import your copied HM modules
                imports = [
                  ./modules/home/default.nix
                  inputs.sops-nix.homeManagerModules.sops
                ];
              };
            }
          ];
        };
      };
      # Code formatter
      formatter.x86_64-linux = alejandra.defaultPackage.x86_64-linux;
    };
}
