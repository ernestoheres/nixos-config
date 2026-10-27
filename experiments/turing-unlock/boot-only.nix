{ pkgs }:
let
  baseline = import ./baseline.nix;
  # Local immutable generation reuse needs --impure for builtins.storePath;
  # the address and its kernel/nixpkgs revision are pinned, not discovered at build time.
  baseSystem = builtins.storePath (toString baseline.system);
  baseBoot = (builtins.fromJSON (builtins.unsafeDiscardStringContext
    (builtins.readFile "${baseSystem}/boot.json")))."org.nixos.bootspec.v1";
  baselinePkgs = import (builtins.fetchTree baseline.nixpkgs).outPath {
    system = "x86_64-linux";
    config.allowUnfree = true;
  };
  kernel = baselinePkgs.linuxPackages.kernel;
  packages = import ./packages.nix { inherit pkgs kernel; };
  device = import ./device.nix;
  initrd = assert kernel.modDirVersion == baseline.kernelVersion;
    assert baseBoot.kernel == "${kernel}/bzImage";
    pkgs.runCommand "turing-experiment-initrd-${baseline.kernelVersion}" {
      nativeBuildInputs = [ pkgs.python3 pkgs.zstd pkgs.kmod ];
    } ''
      mkdir scripts
      cp ${./initrd_archive.py} scripts/initrd_archive.py
      cp ${./compose-boot-only.py} scripts/compose-boot-only.py
      python3 scripts/compose-boot-only.py ${baseSystem} ${packages.module} \
        ${packages.firmware} $out ${pkgs.writeText "turing-device.json" (builtins.toJSON device)}
    '';
  bundle = pkgs.runCommand "turing-experiment-boot-only" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    python3 - ${baseSystem}/boot.json ${initrd}/initrd <<'PY'
    import json, pathlib, sys
    boot = json.loads(pathlib.Path(sys.argv[1]).read_text())["org.nixos.bootspec.v1"]
    boot["initrd"] = sys.argv[2]
    pathlib.Path("bootspec.json").write_text(json.dumps(boot))
    PY
    python3 ${./make-boot-bundle.py} ${baseSystem} $out ${device.nvidia.pci} bootspec.json --boot-only
    cp ${initrd}/provenance.json $out/initrd-provenance.json
  '';
in {
  inherit initrd bundle baseSystem;
  inherit (packages) module firmware artifacts publishedChecksum;
}
