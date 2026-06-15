{pkgs, ...}: {
  # Extra Portal Configuration
  xdg.portal = {
    enable = true;
    xdgOpenUsePortal = true;
    extraPortals = [
      pkgs.xdg-desktop-portal-gtk
      pkgs.xdg-desktop-portal-hyprland
    ];
    config = {
      common.default = [ "hyprland" "gtk" ];
      hyprland.default = [ "hyprland" "gtk" ];
    };
  };
}
