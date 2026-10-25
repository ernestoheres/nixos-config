# Opt-in testing and recovery

**Instructions for later, after explicit approval. None of the installation,
boot, power-control, benchmark or shutdown commands below has been executed.**
Complete the full build first; previews are not bootable deliverables.

## 1. Preserve and verify normal recovery

Keep `results/preserved-normal-system` and generation 83. Do not garbage-collect
them or run a generation-pruning bootloader installation. With approval for
privileged read-only inspection, record:

```sh
E="$HOME/NixOS-Hyprland/experiments/turing-unlock"
mkdir -p "$E/results/recovery"
sudo bootctl status > "$E/results/recovery/bootctl-status.txt"
sudo bootctl list > "$E/results/recovery/bootctl-list.txt"
sudo nix-env --list-generations -p /nix/var/nix/profiles/system > "$E/results/recovery/generations.txt"
sudo cat /boot/loader/loader.conf > "$E/results/recovery/loader.conf"
sudo cat /boot/loader/entries/nixos-generation-83.conf > "$E/results/recovery/nixos-generation-83.conf"
```

Check that generation 83's `init=` points to the preserved store closure; read
its `linux` and every `initrd` path and verify each referenced ESP file exists
and is readable. Compare their hashes with the preserved system's `kernel` and
`initrd`. Back up the entry, loader.conf and referenced EFI files outside `/boot`.
Record the EFI default/one-shot selection as well as loader.conf.

The loader default must explicitly resolve to an existing **normal** entry.
If it is `@saved`, unset, or a wildcard that could select the experiment, stop
and discuss a default-preserving strategy before installing. Do not silently
rewrite defaults. The generic NixOS systemd-boot installer writes loader.conf
and prunes entries; that is why it is not used for this disposable entry.

Use the internal panel. Verify AMD's eDP connector is connected/enabled as in
`HARDWARE.md`; do not depend on NVIDIA HDMI/DP. Keep a NixOS rescue USB available.
Before active testing, use the inert entry to verify that an internal-panel TTY
is accessible, and record its configured-kernel/driver baseline.

## 2. Build and install only the inert entry

First, unprivileged and non-activating:

```sh
python3 experiments/turing-unlock/build.py --full-system
python3 experiments/turing-unlock/validate.py
```

Require `full_system_built: true`, `boot_bundle_validated: true` and a real
`results/boot-bundle` from the same build. Review its `provenance.json` and
`turing-experiment-inert.conf`; require **no `turing_unlock.targets` argument**.
Do not install `results/boot-preview` or `active-preview.conf`.

**Only after explicit approval to modify the ESP**, copy the bundle's
`EFI/turing-experiment-<store-hash>/linux.efi` and `initrd` to the identical paths
under `/boot`, dereferencing the source symlinks. Copy just
`turing-experiment-inert.conf` to `/boot/loader/entries/`. Refuse overwriting any
existing path. This needs no build/download command under sudo, no firmware
variable write, no `bootctl install/update`, and no `switch-to-configuration`.
Compare source/destination SHA-256 hashes. Verify loader.conf, normal entry,
normal EFI file hashes and EFI default are identical to the saved values.

Keep the experiment system GC root (`results/system`) and normal recovery root.
Do not run `nixos-rebuild switch`, `boot`, or `test`. These are not needed for
manual selection of a separately copied BLS entry.

## 3. Inert boot, then one-boot active opt-in

After separate approval to reboot, show the systemd-boot menu (hold Space during
startup), explicitly select **NixOS turing-experiment (INERT)** and boot it with
no target argument. Verify `/proc/cmdline` has no target, the gate finished,
`/sys/module/turing_unlock/parameters/targets` is empty or `(null)`, NVIDIA
initialized, and no `unlock result` / `unlocked` message exists. Save logs and
idle telemetry to a new directory under `results/`. This boot validates module
loading and recovery without executing the unlock path.

For a later **explicitly approved active boot**, select the same inert entry,
press `e`, and append exactly once:

```
turing_unlock.targets=0000:01:00.0
```

This is a transient menu edit. Do not use `all`, a comma list, modprobe options,
saved kernel parameters or a different address. The initrd gate refuses other
targets, duplicate target parameters, a changed vendor/device, or an already
bound GPU. The generated `active-preview.conf` is for inspection only.

## 4. Inspect before any workload

After the approved active boot, create a new persistent run directory and save:

```sh
E="$HOME/NixOS-Hyprland/experiments/turing-unlock"
RUN="$E/results/active-$(date +%Y%m%d-%H%M%S)"
mkdir "$RUN"
cat /proc/cmdline > "$RUN/cmdline.txt"
uname -a > "$RUN/kernel.txt"
sudo journalctl -k -b -o short-monotonic > "$RUN/kernel-before.txt"
sudo journalctl -b -u turing-unlock-gate.service > "$RUN/gate.txt"
lspci -Dnnk > "$RUN/pci.txt"
nvidia-smi -q > "$RUN/idle.txt"
```

Require all of the following before approval to run the benchmark:

* Exactly the one NVIDIA target in `/proc/cmdline` and module target readback.
* Gate chronology preceding NVIDIA initialization; `Kernel driver in use: nvidia`
  for the target, `nvidia-smi` functional, correct GPU identity and no Xid errors.
* Firmware/geometry/GFW completion; `FWSEC done: ret=0` when that path executes;
  `sec done: halted=1`, zero error mailbox and expected PLM; both staging
  readbacks `match=1`. Missing/unverified readbacks are stop conditions.
* `unlock result: ss0=0x88888888 ss1=0x8 readout=0`, `TU102 FEAT UNLOCKED`, and
  target-specific `turing_unlock: unlocked`. The TU102 label is upstream text.
* No firmware timeout, error-path FLR, retained DMA resources, failed unlock,
  unsupported/unmatched device, incorrect readback or unstable system behavior.

Do not treat a successful service or just the final `unlocked` line as sufficient.
Do not perform manual MMIO probing. On any anomaly: no benchmark, no reload,
no automated retry; collect available logs and fully power off.

## 5. One short correctness-checked WMMA benchmark

Reuse `~/cuda-experiment/tensor_bench.cu` and `run_benchmark.py`. No numerical
methodology changes: 480 blocks, 8 warps/block, 8192 WMMA operations/warp,
FP16 inputs `1/256`, FP32 accumulation; 4 chains expect exactly 0.5 in every
stored element. Full checks reject NaN/infinity and run before and after timing.
CUDA-event timing, SASS checks and concurrent clock/power telemetry stay intact.
Only duration and selected chain count change: **one 4-chain run, 0.25 s warm-up,
2 s measured GPU time** (the final 32-kernel batch can overshoot slightly).
There is no repeated sweep or retry.

Source SHA-256 values captured at discovery:

```
23dce2cdebfc5af174f3b7032770044f460f76b085e49d7494d0c4125b249d78  tensor_bench.cu
71d43d85821ea45f001dd8459b4b3867af4f0261c0011378b6432bde487a9747  run_benchmark.py
c6fae566e744d3e9afbd562bb1fc73d1e88fba021a3cc528a3f7a5ace788aaf5  flake.lock
```

Verify these before use; preserve any changed source and review rather than
replacing it. Compile beforehand in the existing pinned CUDA shell if needed:

```sh
nix develop "$HOME/cuda-experiment" --command bash -c \
  'cd "$HOME/cuda-experiment" && nvcc -O3 -std=c++17 -arch=sm_75 -Xptxas=-v tensor_bench.cu -o tensor_bench'
```

Before the approved workload, read `nvidia-smi --id=0000:01:00.0 -q -d POWER`.
If supported, choose a conservative limit **no greater than 40 W and no greater
than the current limit**, within the reported minimum/maximum. Save the original
values, apply that limit only to this GPU, and verify its readback. For the
discovered 80 W current / 1–100 W bounds, the proposed approved command is:

```sh
sudo nvidia-smi --id=0000:01:00.0 --power-limit=40
```

Do not execute it now. If unsupported, refused, unavailable or not verifiably
enforced, stop and ask whether to proceed at the existing cap; never silently
fall back or raise an existing lower limit. Leave voltage, clocks, fan curves,
thermal protections and maximum power limits alone. Let the idle GPU cool;
do not start a thermal-soaked test.

After explicit benchmark approval, use the UUID discovered for the PCI target
to constrain CUDA device selection:

```sh
GPU_UUID=$(nvidia-smi --id=0000:01:00.0 --query-gpu=uuid --format=csv,noheader)
CUDA_VISIBLE_DEVICES="$GPU_UUID" nix develop "$HOME/cuda-experiment" --command \
  python3 "$HOME/cuda-experiment/run_benchmark.py" \
    --binary "$HOME/cuda-experiment/tensor_bench" --device 0 --chains 4 \
    --seconds 2 --warmup 0.25 --output "$RUN/wmma"
```

Monitor for firmware/Xid errors and instability in a second terminal. Interrupt
on any anomaly or incorrect computation; do not repeat. The runner preserves
raw kernel times, SASS, correctness results, clocks, temperature and board power.
`summary.json` includes `approx_flops_per_sm_clock`:
`median_kernel_tflops * 1e6 / (SM_count * median_SM_MHz)`. This normalization of
separate medians is not a direct `clock64()` cycle measurement. Keep the before
and after exact-output checks and the live telemetry alongside any throughput
claim. Compare against the inert boot's kernel/driver baseline, not just the
older running-system numbers.

## 6. Full power-off and normal verification

Save `journalctl -k -b`, `nvidia-smi -q` and the complete results after the one
run. Then, after approval, use `systemctl poweroff` and wait for complete power
off; do not use a warm reboot as cleanup. Start the laptop and explicitly choose
the preserved normal generation 83 entry. Verify normal internal display,
`nvidia-smi`, expected driver/GPU, no Xid errors, no loaded `turing_unlock`, no
target argument, and normal/default power limits. A new baseline CUDA workload
requires its own approval; read-only `nvidia-smi` is not a compute correctness test.

## Recovery / removal

* At systemd-boot, select **generation 83**. To make the experiment inert, press
  `e` on its entry and remove the complete `turing_unlock.targets=…` token before
  booting. Confirm no duplicate token remains. With the intended procedure the
  saved entry is already inert; normal boot never includes the module.
* To recover a text console, transiently add `systemd.unit=multi-user.target`
  to the **normal** entry and, if necessary, a single combined
  `module_blacklist=nvidia,nvidia_drm,nvidia_modeset,nvidia_uvm,nouveau` token.
  Retain `amdgpu` and use the internal panel. Do not combine this with an active
  target parameter. This TTY fallback remains untested on this laptop.
* If firmware cannot stop or the GPU/system hangs, fully power off; do not
  repeatedly unload/reload, reset, benchmark or retry the exploit. Follow the
  laptop manufacturer's power-removal procedure if normal shutdown is impossible.
* If no local console works, boot rescue media, mount root and the ESP, preserve
  the logs, remove only `loader/entries/turing-experiment-inert.conf` and its
  uniquely named `EFI/turing-experiment-<store-hash>` directory, and use the saved
  normal entry/files. Do not delete `EFI/nixos`, other operating-system loaders,
  generation 83, or rewrite firmware/Secure Boot settings.
* After a normal boot and explicit removal approval, delete only those same
  experimental ESP paths. No system profile rollback is needed because the
  manual installation never changed it. If a separate NixOS rebuild was done
  outside this procedure, inspect generations before selecting the previous
  normal one; do not assume `--rollback` necessarily means generation 83.
* Keep evidence and both GC roots until recovery is confirmed. Later remove the
  experiment source/output additions and roots if desired. Removing Nix files
  alone does not remove an already copied ESP entry or reverse hardware damage.
