{ config, lib, pkgs, ... }:
let
  device = import ./device.nix;
  packages = import ./packages.nix { inherit pkgs; kernel = config.boot.kernelPackages.kernel; };
  gateBefore = [
    "systemd-udevd.service"
    "systemd-udevd-control.socket"
    "systemd-udevd-kernel.socket"
    "systemd-udev-trigger.service"
    "systemd-modules-load.service"
  ];
in {
  system.nixos.tags = [ "turing-experiment" ];
  system.build.turingExperimentBootBundle = pkgs.runCommand "turing-experiment-boot-bundle" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    python3 ${./make-boot-bundle.py} ${config.system.build.toplevel} $out ${device.nvidia.pci}
  '';
  assertions = [
    { assertion = config.boot.initrd.systemd.enable;
      message = "The turing experiment ordering was audited only for the systemd initrd."; }
    { assertion = builtins.match "[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\\.[0-7]" device.nvidia.pci != null;
      message = "The experiment requires one full discovered PCI address."; }
    { assertion = !lib.any (p: lib.hasPrefix "turing_unlock.targets=" p) config.boot.kernelParams;
      message = "Keep the generated entry inert; active opt-in is a one-boot menu edit only."; }
    { assertion = !lib.any (m: lib.elem m [ "nvidia" "nvidia_drm" "nvidia_modeset" "nouveau" ])
        config.boot.initrd.kernelModules;
      message = "NVIDIA must not be explicitly loaded by initrd modules-load."; }
  ];

  boot.extraModulePackages = [ packages.module ];
  hardware.firmware = [ packages.firmware ];
  # availableKernelModules includes the module in the closure but does not
  # force-load it in the unordered modules-load set. An explicit gate does that.
  boot.initrd.availableKernelModules = [ "turing_unlock" device.igpu.driver ];
  boot.initrd.extraFirmwarePaths = [ "turing-unlock/610.43.03/*" ];
  boot.extraModprobeConfig = ''
    softdep nvidia pre: turing_unlock
    softdep nouveau pre: turing_unlock
  '';
  boot.initrd.systemd.services.turing-unlock-gate = {
    description = "One inert/explicitly targeted Turing experiment before GPU driver probing";
    wantedBy = [ "sysinit.target" ];
    before = gateBefore;
    unitConfig.DefaultDependencies = false;
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      set -eu
      count=0
      for arg in $(cat /proc/cmdline); do
        case "$arg" in
          turing_unlock.targets=*)
            test "$arg" = 'turing_unlock.targets=${device.nvidia.pci}'
            count=$((count + 1))
            ;;
        esac
      done
      test "$count" -le 1
      if test "$count" -eq 1; then
        test "$(cat /sys/bus/pci/devices/${device.nvidia.pci}/vendor)" = '0x${device.nvidia.vendor}'
        test "$(cat /sys/bus/pci/devices/${device.nvidia.pci}/device)" = '0x${device.nvidia.device}'
        test ! -L /sys/bus/pci/devices/${device.nvidia.pci}/driver
      fi
      echo "turing-unlock gate: target count=$count; loading once before udev and modules-load"
      /bin/modprobe turing_unlock
      echo "turing-unlock gate: module initialization completed"
    '';
  };
  # Requiring the gate prevents a failed identity/argument check from merely
  # being ignored by concurrently starting the GPU enumeration services.
  boot.initrd.systemd.services.systemd-udevd.requires = [ "turing-unlock-gate.service" ];
  boot.initrd.systemd.services.systemd-udev-trigger.requires = [ "turing-unlock-gate.service" ];
  boot.initrd.systemd.services.systemd-modules-load.requires = [ "turing-unlock-gate.service" ];
  boot.initrd.systemd.sockets.systemd-udevd-control.requires = [ "turing-unlock-gate.service" ];
  boot.initrd.systemd.sockets.systemd-udevd-kernel.requires = [ "turing-unlock-gate.service" ];
}
