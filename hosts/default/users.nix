# 💫 https://github.com/JaKooLit 💫 #
# Users - NOTE: Packages defined on this will be on current user only
{ config
, pkgs
, username
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
        opencode
        bun
        gh
        unityhub
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
      interactiveShellInit = "${pkgs.neofetch}/bin/neofetch";
      ohMyZsh = {
        enable = true;
        theme = "agnoster";
        plugins = [ "git" ];
      };
      # Enable zsh plugins via NixOS module options
      autosuggestions.enable = true;
      syntaxHighlighting.enable = true;
    };
  };
}
