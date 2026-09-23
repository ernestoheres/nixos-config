# Codex Desktop (github:ilysenko/codex-desktop-linux)
#
# The flake ships the packaged app itself, so no local bundle is needed.
# Options live under programs.codexDesktopLinux (enable, package, cliPackage,
# linuxFeatures, computerUseUi, remoteControl, remoteMobileControl).
#
# allowUnfree is already true globally (modules/packages.nix).
{ ... }: {
  programs.codexDesktopLinux = {
    enable = true;
  };
}
