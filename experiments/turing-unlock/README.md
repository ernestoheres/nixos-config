# Disposable Turing experiment

## Current status — 2026-10-25

**The boot-only module, firmware, initrd and inert boot bundle are built and
validated. No boot entry has been installed. The existing desktop is reused.**

The original full-specialisation build requested 8.8 GiB of downloads / 27.8 GiB
unpacked because the worktree's desktop configuration is newer than the booted
generation. It failed with `No space left on device` while packaging Codex Desktop,
not while building the exploit. `results/system.log` retains the failure evidence.
The build driver now uses the smallest alternative: a dedicated BLS entry with
an additive initrd based on the already installed generation 83. There is no
desktop, NVIDIA driver, or kernel replacement. After the local cleanup its plan
required about 287 MiB of kernel-header/build-tool downloads, not 8 GiB.

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
| `baseline.nix`, `boot-only.nix` | Exact installed generation and matching kernel-header pin; boot-only derivations |
| `initrd_archive.py`, `compose-boot-only.py` | Add files without replacing any existing initrd member |
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

That specialisation remains available as an optional full-flake configuration;
**the build driver does not build it**. The recommended boot-only entry instead
uses the exact preserved kernel and `init=` closure in `baseline.nix`: Linux
6.18.52 / NVIDIA 595.71.05. It reproduces the existing desktop/display settings
without evaluating or building its packages. The module is built against the
matching pinned kernel development output, with the kernel output path checked
against generation 83's bootspec, not just its version string.

The normal host evaluated to exactly the original derivations:

```
/nix/store/830n634x7x08d6qgb3fb997gz6h09qhv-nixos-system-default-26.05.20261010.6fcc160.drv
/nix/store/wbpchcvk8qns19ll7z8y3wsnw286y1rw-initrd-linux-6.18.55.drv
```

## Reproduce the non-activating build

From the repository root:

```sh
python3 experiments/turing-unlock/build.py --boot-only
python3 experiments/turing-unlock/validate.py
```

`build.py` snapshots the current worktree with `source-tree.nix`, excluding the
checkout, evidence and `.git`; this includes new files without staging user work.
The snapshot and all result symlinks are GC roots. The flake lock is not updated.
On a fresh checkout it also captures read-only hardware evidence and preserves
the booted system closure, so ignored local files are not prerequisites. This
experiment is intentionally specific to the hardware and pinned normal-host
baseline recorded here; changing the host requires reviewing that baseline.
`--boot-only` is the default; the old `--full-system` argument is retained as a
deprecated alias to this same small build, so it cannot trigger another desktop
rebuild. Nix uses `--impure` only to reference the exact immutable, locally
installed baseline store path. All source revisions and downloads are hash-pinned,
and all ordinary build derivations run in the network-isolated Nix sandbox.
Signed binary-cache substitutions remain available for build tools.

The standalone package target is:

```
packages.x86_64-linux.turing-unlock-boot-bundle
```

The result is `results/boot-only`; its inert BLS entry can be reviewed and, after
approval and recovery checks, copied to the ESP. `results/boot-initrd` is the new
image and `results/boot-assets` roots the module and firmware. Validation requires
an existing baseline `init`, an unchanged kernel and kernel parameters, every
original initrd member's data/metadata, exact firmware hashes, module vermagic,
correct targeting and a valid systemd unit graph. It records
`mode: boot-only`, `desktop_rebuilt: false` and `boot_bundle_validated: true`.
Old `results/boot-preview`, `results/boot-bundle` and 6.18.55 initrd outputs are
not part of this path; do not install them.

Measured artifacts: module **105,936 bytes**, baseline initrd **35,088,354 bytes**,
experimental initrd **50,579,546 bytes** (about 48.2 MiB total). The increase is
approximately 14.8 MiB, primarily the six firmware assets. Build-tool downloads
are separate from the size of the resulting boot image.

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
  The boot-only build uses the exact baseline Linux 6.18.52 development output.
  The optional full specialisation uses its configured kernel, currently 6.18.55.
* `main.c` returns before enumerating devices when `targets` is absent/empty.
  Explicit full PCI names are matched against supported NVIDIA devices. Bound
  devices are refused. Initialization waits for all scheduled unlock work.
* **Initialization returns success even when per-card work fails.** A successful
  oneshot/module insertion is not evidence of a successful unlock; inspect kernel logs.
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
`build.py` fetches these inputs separately before asset generation. The generators verify
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

Validated image: `results/boot-initrd/initrd`; the bundle records its immutable
store path, hashes and baseline bootspec. It has the original byte-identical
early microcode CPIO followed by a zstd-compressed systemd CPIO. The composer
adds 24 entries while preserving all 2,459 original members' data and metadata.
The old initrd, kernel, NVIDIA modules and stage-2 closure are never modified.

The module is at:

```
/turing-experiment/turing_unlock.ko
```

All six assets are added at the archive's resolved `/lib/firmware/turing-unlock/610.43.03/`
directory, as unmodified `.bin` bytes inside the compressed initrd. The original
AMD driver, firmware and display settings remain available in the unchanged
stage-2 system. No `nvidia`,
`nvidia_drm`, `nvidia_modeset`, `nvidia_uvm` or `nouveau` module is in this initrd.

The actual pinned NixOS implementation matters: `boot.initrd.kernelModules` is
an alphabetically enumerated **set**, not an ordering primitive. The boot-only
path adds an explicit oneshot gate with
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
the live vendor/device and absence of a bound driver before invoking `/bin/kmod
insmod` once. The module declares no module dependencies (verified via modinfo),
so no baseline module indexes or modprobe settings need modification. The gate
passes `targets=` only in active mode; an inert load passes no module arguments.
NVIDIA subsequently binds in stage 2; no initrd NVIDIA module can race it.

The generated service/drop-ins, script and module/firmware paths were checked
inside the actual image. `systemd-analyze verify --root=… --generators=no
--man=no initrd.target` returned **0 with no diagnostics**, checking the real
generated units for dependency/order cycles. This is build-time evidence;
observed boot chronology must still be checked before benchmarking.

Persistent evidence: `results/validation.json`, `boot-initrd-files.txt`,
`boot-gate.service`, `boot-gate.sh`, `boot-module-info.txt`, `boot-assets.log`,
`boot-systemd-verify.log`, `discovery/hardware.json`, and the
`*.json` build records. Nothing important relies on `/tmp`.
