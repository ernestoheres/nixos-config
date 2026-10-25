# Hardware detection and unresolved assumptions

Detected using the five requested commands, DRM sysfs, `hyprctl monitors -j`
and read-only Nix evaluation. Raw output is in `results/discovery/`.

| Device | PCI address | Vendor:device | Bound driver |
|---|---|---|---|
| NVIDIA TU106M / RTX 2060 Mobile | `0000:01:00.0` | `10de:1f15` | `nvidia` |
| AMD Renoir / Radeon Vega iGPU | `0000:06:00.0` | `1002:1636` | `amdgpu` |

Both have HP subsystem `103c:8787`. NVIDIA's audio function `0000:01:00.1`
(`10de:10f9`) is not a target. NVIDIA reports the GPU as `00000000:01:00.0`;
this is the same address with an eight-digit domain, not another GPU.

## Actual display wiring

* AMD is DRM `card1`, `boot_vga=1`. Its **eDP-1 internal panel is connected and
  enabled**. Hyprland is displaying 1920×1080 at approximately 144 Hz on that
  LG Display panel. This directly establishes an AMD-driven scanout path.
* NVIDIA is `card0`, `boot_vga=0`; `DP-1`, `DP-2`, `HDMI-A-1` are all disconnected
  and disabled. `nvidia-smi` reports no attached/active display.
* Thus use the **internal panel**, not an external NVIDIA-wired output, for
  recovery. The experiment includes amdgpu and leaves its display configuration
  intact. A console boot with NVIDIA unavailable has not been exercised; a GPU
  or shared-platform hang can still prevent an iGPU console. Recovery is not
  inferred solely from the iGPU's presence.

## Software/boot facts

* Host output: `default`; platform `x86_64-linux`.
* Booted kernel **6.18.52**, NVIDIA **595.71.05**, proprietary kernel module;
  configured kernel **6.18.55**, configured NVIDIA **595.84**, also proprietary.
  Firmware inputs 610.43.03 are exploit assets, not a driver upgrade to 610.
* Pinned root nixpkgs: `6fcc160353f63555b560f25588925133c8f61f2a`.
* Systemd initrd, systemd-boot enabled, `/boot` vfat ESP, five-second timeout.
  Live loader reports version 260.4, UEFI 2.70, Secure Boot already disabled
  (setup mode). This experiment changes no Secure Boot settings.
* Firmware-selected boot entry: **`nixos-generation-83.conf`**. `/run/booted-system`,
  `/run/current-system`, system profile and `system-83-link` all resolve to:
  `/nix/store/8yvfyf1fdw5ablx168lk5nrc2ps4ff9n-nixos-system-default-26.05.20260921.1e8bc65`.
  That closure has a new persistent GC root at `results/preserved-normal-system`.
* ESP permissions prevent reading entry contents or `loader.conf` without sudo;
  `sudo -n` requires a password. The **installed normal entry's referenced files
  and loader default remain unverified**. Do not install/test until the operator
  verifies and backs them up using `PROCEDURE.md`.
* Normal host uses PRIME offload, AMD+NVIDIA video drivers, no NVIDIA initrd
  force-loading. Its existing PRIME `intelBusId=PCI:4:0:0` is stale relative to
  this AMD topology; `amdgpuBusId` is empty. Xserver is disabled and the live
  Wayland internal-panel path works. The experiment preserves these settings;
  they are not evidence of a correct Xorg recovery configuration.
* Existing host kernel parameters already include `lockdown=none`, `iomem=relaxed`,
  MSR-write enabling and watchdog blacklists. No such setting was added or
  weakened by this experiment; normal and experimental parameter lists match.
* Requested CSV `power.limit` reports `[N/A]`, but full `nvidia-smi -q` reports
  current/default **80 W**, minimum 1 W, maximum 100 W. These readouts do not prove
  writable power-limit support. It has not been tested. Idle samples were around
  5–6 W, 300 MHz and 54–56 °C; see raw logs for exact capture timestamps.

## Remaining unsupported assumptions

1. The user reports independently confirming the shared TU102-named firmware
   modules in NVIDIA artifacts/documentation. This supports the firmware choice,
   but does not establish payload/register/FLR/VBIOS compatibility on this TU106M.
   Upstream README only reports a Dell RTX 2080 Ti / driver 575.51.03 test.
2. The allowlist addition is permission to attempt testing, not proof of support.
   The laptop VBIOS (reported `90.06.58.40.73`), FWSEC geometry, protected memory
   layout, and pre-driver power state have not been validated by live execution.
3. The configured kernel/driver pair differs from the live baseline. First boot
   the **inert** experiment successfully and capture its baseline before any
   active test, so an ordinary kernel/driver regression is distinguishable.
4. Independent AMD scanout is observed, but cold recovery, TTY operation without
   NVIDIA, and response to a shared PCI/platform hang remain untested.
5. Writable conservative power limiting, selector persistence through driver
   initialization, and reset behavior across complete laptop power-off remain
   unproven. No thermal/power protections are bypassed to compensate.
6. Full stage-2 system closure and installable boot bundle are not yet built.
   Full normal boot-entry verification also needs privileged read access.
