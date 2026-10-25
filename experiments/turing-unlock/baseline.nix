# Exact generation 83 boot closure. Reuse it; do not rebuild the desktop flake.
{
  system = /nix/store/8yvfyf1fdw5ablx168lk5nrc2ps4ff9n-nixos-system-default-26.05.20260921.1e8bc65;
  kernelVersion = "6.18.52";
  nixpkgs = {
    type = "github";
    owner = "NixOS";
    repo = "nixpkgs";
    rev = "1e8bc658fc985ef27ccd66d107d767b32bb7ef98";
    narHash = "sha256-62XMQD4WLdMAfdT0/8gJmPH2dKeTw908ryNloAplTr8=";
  };
}
