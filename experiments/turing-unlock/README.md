# Disposable Turing experiment

## Current status — 2026-10-25

**Module, firmware and inert initrd built and validated. The full desktop system
build is pending. No boot entry has been installed. Do not boot the preview
artifacts.**

The remaining full build requested 622 derivations and 8.8 GiB of downloads /
27.8 GiB unpacked, mostly unrelated desktop packages. `results/system.log`
records the interrupted attempt. It is not an exploit/module build failure.

No reboot, exploit/module loading, benchmark, power-limit change, installed-driver
modification, firmware flash, bootloader write, or NixOS activation was performed.
The generated firmware files are build assets; they have not been uploaded to
the GPU. Explicit approval is required before installing a boot entry and again
before active testing. A software rollback cannot guarantee recovery from
physical hardware damage.

## Files and isolation

| File | Purpose |
|---|---|
| `device.nix` | PCI identifiers discovered on this machine |
| `packages.nix` | Pinned upstream source, fixed-output NVIDIA downloads, offline asset generation and kernel build |
| `tu106m.patch` | One allowlist addition: detected device `0x1f15` |
| `source/` | Local detached, patched checkout; ignored by the outer repository |
| `specialisation.nix`, `experiment.nix` | Isolated `turing-experiment` specialisation |
| `build.py`, `validate.py` | Non-activating builds and validation of actual initrd bytes |
| `make-boot-bundle.py` | Generate BLS files without installing them |
| `HARDWARE.md` | Both GPUs, display topology and recovery limitations |
| `PROCEDURE.md` | Approval-gated boot, one-shot benchmark, shutdown and recovery |
| `results/` | Persistent local logs, hashes, GC roots and build outputs; ignored |

The existing `nixosConfigurations.default` is untouched. The extra flake output
`nixosConfigurations.default-turing-experiment` extends that host solely to add
the specialisation. Only its child installs the module/firmware, initrd gate and
softdeps. The parent inherits the host's normal GPU/display configuration.
There is no persistent target parameter or automatic workload.

The normal host evaluated to exactly the original derivations:

```
/nix/store/830n634x7x08d6qgb3fb997gz6h09qhv-nixos-system-default-26.05.20261010.6fcc160.drv
/nix/store/wbpchcvk8qns19ll7z8y3wsnw286y1rw-initrd-linux-6.18.55.drv
```

## Reproduce the non-activating build

From the repository root:

```sh
# Defaults to the small module/firmware/initrd build.
python3 experiments/turing-unlock/build.py
python3 experiments/turing-unlock/validate.py

# Remaining, large step: explicitly request the complete system and boot bundle.
# Still build-only; no sudo or installation. Allow sufficient space/time.
python3 experiments/turing-unlock/build.py --full-system
python3 experiments/turing-unlock/validate.py
```

`build.py` snapshots the current worktree with `source-tree.nix`, excluding the
checkout, evidence and `.git`; this includes new files without staging user work.
The snapshot and all result symlinks are GC roots. The flake lock is not updated.
On a fresh checkout it also captures read-only hardware evidence and preserves
the booted system closure, so ignored local files are not prerequisites. This
experiment is intentionally specific to the hardware and pinned normal-host
baseline recorded here; changing the host or lock requires reviewing that baseline.
The specialisation's ordinary build target is:

```
nixosConfigurations.default-turing-experiment.config.specialisation.turing-experiment.configuration.system.build.toplevel
```

The full build also generates `results/boot-bundle`; its inert BLS entry can be
reviewed and, after approval and recovery checks, copied to the ESP. In contrast,
`results/boot-preview` demonstrates the future command line but references an
unbuilt stage-2 system. The validator records `full_system_built: false` until
the real system closure exists. Merely evaluating its store path is insufficient.

## Pinned provenance and review

Upstream: <https://github.com/nlzy/turing-unlock>

Commit: `1d379b724454d6fb7e8a7a8dd0ea359febc05ca3` (version 2.0.0).
Unpacked source hash: `sha256-Vm/eg0p4M3CD633V/y2FYyy3UaTV/mlrw/nlFqPuXVY=`.

Recreate the convenience checkout, if needed, without running its Makefile:

```sh
git clone https://github.com/nlzy/turing-unlock experiments/turing-unlock/source
git -C experiments/turing-unlock/source checkout --detach 1d379b724454d6fb7e8a7a8dd0ea359febc05ca3
git -C experiments/turing-unlock/source apply ../tu106m.patch
```

The derivations fetch that same commit and apply the same patch independently;
the mutable local checkout is never a build input. The patch adds only `0x1f15`
to `supported_ids` in `main.c`. It does not change firmware code or the installed
NVIDIA driver. The source README, all three firmware scripts, Kbuild, module
initialization and cleanup paths were reviewed:

* Kbuild links `main`, `gfw_eval`, `prep`, `layout`, `vbios`, `boot`, `unlock`.
  Kbuild runs against `config.boot.kernelPackages.kernel.dev`, Linux 6.18.55.
* `main.c` returns before enumerating devices when `targets` is absent/empty.
  Explicit full PCI names are matched against supported NVIDIA devices. Bound
  devices are refused. Initialization waits for all scheduled unlock work.
* **Initialization returns success even when per-card work fails.** A successful
  oneshot/modprobe is not evidence of a successful unlock; inspect kernel logs.
* `unlock.c` requests six versioned assets, prepares coherent DMA, may perform
  PCIe FLR, runs FWSEC and SEC2, writes selectors, and checks their readbacks.
  This is volatile GPU firmware execution, not a VBIOS flash.
* Normal cleanup unmaps BARs, restores DMA masks, frees buffers, releases firmware
  and restores PCI state. Failure after firmware execution attempts FLR. If the
  engines cannot be quiesced, DMA resources and a module reference are retained
  until power-off. The empty module-exit function does **not** undo selectors.
  Module removal, a runtime rollback or warm reboot is not a reset procedure.
* Upstream's staging readback mismatch is only logged, not fatal. Our procedure
  treats it as a stop condition regardless of upstream's eventual success text.

The two exact NVIDIA input archives were fetched and verified separately:

| Input | SHA-256 |
|---|---|
| `NVIDIA-kernel-module-source-610.43.03.tar.xz` | `7e118923c7a23edc36114d63273a46e3e04e9af98695a42203e7ac2dfe9fc1dc` |
| `nvidia-utils-610.43.03-1-x86_64_v3.pkg.tar.zst` | `e17e7c92eeffa178b0fe1f40eb17a47095f8fc3ce4a77bf115cf5bd5a4df86e9` |

URLs are taken from the pinned upstream manifest. NVIDIA's separately published
`.sha256sum` file was fetched, pinned with
`sha256-S1nTb0kap5QX08BLKK23utedGWs7WQ6jDeNfieER3XQ=`, and checked
against the source archive.

Asset generation uses only Nix-store inputs in a sandboxed derivation; no
`make inputs`, home cache, distribution installer, or privileged download hook.
`build.py` invokes the asset build offline after fetching. The generators verify
the package metadata, three generated NVIDIA C inputs, all derived firmware,
GSP size/hash, generated V67 size/hash and NVIDIA license notice. The final
verifier repeats all six asset hashes. The first build's `zstd` symlink rejection
was fixed by passing the regular verified store file, without weakening checks.

| Firmware under `lib/firmware/turing-unlock/610.43.03/` | Bytes | SHA-256 |
|---|---:|---|
| `booter_load_tu102.bin` | 59224 | `51507de61777cf46f3703a084cdfa896c21f6bc0c8af8f245bd09b2e9c49bf54` |
| `gsp_tu10x.bin` | 29352832 | `73065619db9ec921d19fc4e519dd04d91a9199b525eaca9b257b89fb8c5ec52c` |
| `gsp_boot_tu102.bin` | 4096 | `8765694cd38beaa4e2b8b1b83a31fb7aee6cb9d8b7c6bc7a86e6d931a3a056c2` |
| `gsp_boot_desc_tu102.bin` | 76 | `9e7cca2cfdc5ce601b0adba39967850046108df6c2d23fff95578ca3f0ccbe01` |
| `sec2_bl_tu102.bin` | 768 | `f21f1cfbb8fffa8067685314367fc4c50f3f84dd99eda7c19db4292d9269b9d9` |
| `v67-tu102-610.43.03.bin` | 64000 | `b0ec90294d1de3c67e024631c0a11000f281470d76eed806fc24c66b7fd1ef41` |

The NVIDIA license notice hash is
`c692fb14ad4f499c6aee1b9e144e6905148c420e6225b17cb2937366c1e507ad`.
Licenses and notices are installed with the firmware derivation. No firmware
binaries are committed; personal local generation does not assert permission
to redistribute NVIDIA firmware. See the pinned source's `firmware/NOTICE.md`.

## Placement and ordering evidence

Validated image: `/nix/store/zfsf4nfw74087iigb53m2p357c6xac1m-initrd-linux-6.18.55/initrd`.
It has an early microcode CPIO followed by a zstd-compressed systemd CPIO.
`validate.py` reads both archives, resolves symlinks within their virtual root,
decompresses each firmware asset and verifies its actual bytes.

The module is at:

```
/lib/modules/6.18.55/extra/turing_unlock.ko
```

The initrd `/lib` resolves into
`/nix/store/fsc7zq4wkkjpiljkxi0h6rakn0055hq3-linux-6.18.55-modules-shrunk/lib`.
All six assets are present as `.bin.zst`; NixOS's existing firmware compression
is retained. `amdgpu.ko.xz` and its firmware are included too. No `nvidia`,
`nvidia_drm`, `nvidia_modeset`, `nvidia_uvm` or `nouveau` module is in this initrd.

The actual pinned NixOS implementation matters: `boot.initrd.kernelModules` is
an alphabetically enumerated **set**, not an ordering primitive. We instead use
`availableKernelModules` for placement and an explicit oneshot gate with
`DefaultDependencies=false`, before all of:

```
systemd-udevd.service
systemd-udevd-control.socket
systemd-udevd-kernel.socket
systemd-udev-trigger.service
systemd-modules-load.service
```

Each also requires the gate. The gate validates zero target parameters (inert)
or exactly one parameter equal to the detected dGPU. In active mode it checks
the live vendor/device and absence of a bound driver before invoking modprobe
once. NVIDIA subsequently binds in stage 2; no initrd NVIDIA module can race it.
The `softdep nvidia pre: turing_unlock` is an additional stage-2 ordering hint.

The generated service/drop-ins, script and module/firmware paths were checked
inside the actual image. `systemd-analyze verify --root=… --generators=no
--man=no initrd.target` returned **0 with no diagnostics**, checking the real
generated units for dependency/order cycles. This is build-time evidence;
observed boot chronology must still be checked before benchmarking.

Persistent evidence: `results/validation.json`, `initrd-files.txt`,
`gate.service`, `gate-script.sh`, `module-info.txt`, `module-build.log`,
`firmware-build.log`, `systemd-verify.log`, `discovery/hardware.json`, and the
`*.json` build records. Nothing important relies on `/tmp`.
