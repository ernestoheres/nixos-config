# 💫 https://github.com/JaKooLit 💫 #
# Users - NOTE: Packages defined on this will be on current user only
{ config
, pkgs
, username
, inputs
, ...
}:
let
  inherit (import ./variables.nix) gitUsername;
in
{
  users = {
    mutableUsers = true;
    users."${username}" = {
      homeMode = "755";
      isNormalUser = true;
      description = "${gitUsername}";
      extraGroups = [
        "networkmanager"
        "wheel"
        "libvirtd"
        "scanner"
        "lp"
        "video"
        "input"
        "audio"
      ];

      # define user packages here
      packages = with pkgs; [
        inputs.opencode.packages.${pkgs.system}.default
        bun
        gh
        vscode
        unityhub
        discord
        gimp
        krabby
        notion
        firefox
        spotify
        jetbrains.dataspell
        jetbrains.rider
        jetbrains.webstorm
        httpie
      ];
    };

    defaultUserShell = pkgs.zsh;
  };
  services.openssh.enable = true;
  environment.shells = with pkgs; [ zsh ];
  environment.systemPackages = with pkgs; [ lsd fzf git ];
  programs.ssh.startAgent = true;
  programs = {
    zsh = {
      promptInit = ''
        krabby random --no-mega --no-gmax --no-regional --no-title -s;
      '';
      ohMyZsh = {
        enable = true;
        theme = "agnoster";
        plugins = [ "git" ];
      };

      # Enable zsh plugins via NixOS module options
      autosuggestions.enable = true;
      syntaxHighlighting.enable = true;
    };
    zoxide = {
      enable = true;
    };
    direnv = {
      enable = true;
    };
  };
}
