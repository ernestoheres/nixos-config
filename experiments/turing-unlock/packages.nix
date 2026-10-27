{ pkgs, kernel }:
let
  rev = "1d379b724454d6fb7e8a7a8dd0ea359febc05ca3";
  upstream = pkgs.fetchFromGitHub {
    owner = "nlzy";
    repo = "turing-unlock";
    inherit rev;
    hash = "sha256-Vm/eg0p4M3CD633V/y2FYyy3UaTV/mlrw/nlFqPuXVY=";
  };
  source = pkgs.applyPatches {
    name = "turing-unlock-${rev}-tu106m-source";
    src = upstream;
    patches = [ ./tu106m.patch ];
  };
  manifest = builtins.fromJSON (builtins.readFile "${upstream}/firmware/artifacts-610.43.03.json");
  artifacts = map (a: pkgs.fetchurl {
    inherit (a) url;
    name = a.filename;
    sha256 = a.sha256;
  }) manifest.source_artifacts;
  # NVIDIA's separately published checksum is itself pinned. The build checks
  # its contents against the manifest as well as checking the archive bytes.
  publishedChecksum = pkgs.fetchurl {
    url = (builtins.head manifest.source_artifacts).checksum_url;
    hash = "sha256-S1nTb0kap5QX08BLKK23utedGWs7WQ6jDeNfieER3XQ=";
  };
  firmware = pkgs.stdenvNoCC.mkDerivation {
    pname = "turing-unlock-firmware";
    version = "610.43.03-${builtins.substring 0 12 rev}";
    src = source;
    nativeBuildInputs = [ pkgs.python3 pkgs.zstd pkgs.xz ];
    dontConfigure = true;
    buildPhase = ''
      runHook preBuild
      mkdir inputs assets
      ln -s ${builtins.elemAt artifacts 0} inputs/${(builtins.elemAt manifest.source_artifacts 0).filename}
      ln -s ${builtins.elemAt artifacts 1} inputs/${(builtins.elemAt manifest.source_artifacts 1).filename}
      cp ${publishedChecksum} inputs/source.sha256sum
      (cd inputs; sha256sum --check source.sha256sum)
      # No fetch_artifacts.py, make inputs, HOME cache, or network access here.
      tar -xf ${builtins.elemAt artifacts 0}
      # zstd deliberately ignores symlink arguments; pass the regular store file.
      python3 firmware/generate_v67.py ${builtins.elemAt artifacts 1} assets
      python3 firmware/extract_boot_assets.py NVIDIA-kernel-module-source-610.43.03 assets
      python3 ${./verify-firmware.py} firmware/artifacts-610.43.03.json assets > firmware-hashes.json
      runHook postBuild
    '';
    installPhase = ''
      mkdir -p $out/lib/firmware/turing-unlock/610.43.03 $out/share/turing-unlock $out/share/licenses/turing-unlock
      cp assets/*.bin $out/lib/firmware/turing-unlock/610.43.03/
      cp firmware-hashes.json firmware/artifacts-610.43.03.json $out/share/turing-unlock/
      cp assets/NVIDIA-LICENSE firmware/NOTICE.md licenses/* $out/share/licenses/turing-unlock/
    '';
    dontFixup = true;
    meta.license = pkgs.lib.licenses.unfree;
  };
  module = pkgs.stdenv.mkDerivation {
    pname = "turing-unlock";
    version = "2.0.0-${builtins.substring 0 12 rev}";
    src = source;
    nativeBuildInputs = kernel.moduleBuildDependencies;
    hardeningDisable = [ "pic" ];
    dontPatchELF = true; # .ko files are relocatable ELF, not dynamic executables.
    dontConfigure = true;
    buildPhase = ''
      runHook preBuild
      make -C ${kernel.dev}/lib/modules/${kernel.modDirVersion}/build \
        M=$PWD/kernel/turing_unlock modules
      runHook postBuild
    '';
    installPhase = ''
      install -Dm644 kernel/turing_unlock/turing_unlock.ko \
        $out/lib/modules/${kernel.modDirVersion}/extra/turing_unlock.ko
      install -Dm644 licenses/GPL-2.0.txt $out/share/licenses/turing-unlock/GPL-2.0.txt
    '';
    meta.license = pkgs.lib.licenses.gpl2Only;
  };
in {
  inherit rev upstream source artifacts publishedChecksum firmware module;
}
