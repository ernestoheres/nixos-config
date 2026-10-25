#!/usr/bin/env python3
"""Validate the boot-only image against the preserved booted system; never load it."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

from initrd_archive import read_initrd, resolve_name

here = Path(__file__).resolve().parent
out = here / "results"
source = (out / "build-source").resolve()
baseline = json.loads(subprocess.check_output([
    "nix", "eval", "--json", "--file", str(source / "experiments/turing-unlock/baseline.nix"),
], text=True))
base = Path(baseline["system"])
assert base.resolve() == (out / "preserved-normal-system").resolve()
assert base.resolve() == Path("/run/booted-system").resolve()
assert (base / "init").is_file()
igpu_modules = list((base / "kernel-modules/lib/modules" / baseline["kernelVersion"]).glob(
    "kernel/drivers/gpu/drm/amd/amdgpu/amdgpu.ko*"))
assert igpu_modules, "The preserved baseline must retain the AMD iGPU driver"
original_boot = json.loads((base / "boot.json").read_text())["org.nixos.bootspec.v1"]
bundle = out / "boot-only"
provenance = json.loads((bundle / "provenance.json").read_text())
assert provenance["boot_only"] and not provenance["preview_only"]
boot = provenance["bootspec"]
assert boot["init"] == str(base / "init")
assert boot["kernel"] == original_boot["kernel"]
assert {k: v for k, v in boot.items() if k != "initrd"} == {
    k: v for k, v in original_boot.items() if k != "initrd"}
assert Path(boot["initrd"]).resolve() == (out / "boot-initrd/initrd").resolve()
assert not any(p.startswith("turing_unlock.targets=") for p in boot["kernelParams"])
inert_entry = (bundle / "turing-experiment-inert.conf").read_text()
active_entry = (bundle / "active-preview.conf").read_text()
discovery = json.loads((out / "discovery/hardware.json").read_text())
gpus = [gpu for gpu in discovery["drm"] if gpu["vendor"] == "0x10de"]
assert len(gpus) == 1
gpu = gpus[0]
target = gpu["pci"]
assert provenance["active_preview_targets"] == [target]
assert "turing_unlock.targets=" not in inert_entry
assert [p for p in active_entry.split() if p.startswith("turing_unlock.targets=")] == [
    "turing_unlock.targets=" + target]
for name, expected in [("linux.efi", boot["kernel"]), ("initrd", boot["initrd"])]:
    assert (bundle / provenance["esp_directory"] / name).resolve() == Path(expected).resolve()

early, entries = read_initrd(Path(boot["initrd"]))
original_early, original_entries = read_initrd(Path(original_boot["initrd"]))
assert early == original_early, "The early microcode archive must be byte-identical"
for name, entry in original_entries.items():
    actual = entries[name]
    assert entry.data == actual.data and entry.fields[:11] == actual.fields[:11], name
    assert entry.fields[12] == actual.fields[12], name
added = sorted(set(entries) - set(original_entries))
assert not any(re.search(r"/(?:nvidia(?:_drm|_modeset|_uvm)?|nouveau)\.ko", n) for n in entries)
fwroot = resolve_name(entries, "lib/firmware")
unitroot = resolve_name(entries, "etc/systemd/system")
assert all(n == fwroot or n.startswith(("turing-experiment", fwroot + "/turing-unlock", unitroot + "/"))
           for n in added)
manifest = json.loads((bundle / "initrd-provenance.json").read_text())
assert manifest["target"] == target
assert manifest["baseline_system"] == str(base)
for name, info in manifest["firmware"].items():
    data = entries[fwroot + "/turing-unlock/610.43.03/" + name].data
    assert len(data) == info["bytes"] and hashlib.sha256(data).hexdigest() == info["sha256"]
assert len(manifest["firmware"]) == 6
ko = Path(manifest["module"])
assert entries["turing-experiment/turing_unlock.ko"].data == ko.read_bytes()
modinfo = subprocess.check_output(["modinfo", str(ko)], text=True)
assert re.search(r"^vermagic:\s+" + re.escape(baseline["kernelVersion"]) + r"\s", modinfo, re.M)
(out / "boot-module-info.txt").write_text(modinfo)
unit = entries[unitroot + "/turing-unlock-gate.service"].data.decode()
before = set(re.search(r"^Before=(.*)$", unit, re.M)[1].split())
for name in ["systemd-udevd.service", "systemd-udevd-control.socket", "systemd-udevd-kernel.socket",
             "systemd-udev-trigger.service", "systemd-modules-load.service"]:
    assert name in before
    override = entries[unitroot + "/" + name + ".d/turing-experiment.conf"].data.decode()
    assert "Requires=turing-unlock-gate.service" in override
    assert "After=turing-unlock-gate.service" in override
gate = entries["turing-experiment/gate.sh"].data.decode()
assert "test \"$arg\" = 'turing_unlock.targets=" + target + "'" in gate
assert gpu["vendor"] in gate and gpu["device"] in gate
assert "test \"$count\" -le 1" in gate
assert "/bin/kmod insmod /turing-experiment/turing_unlock.ko targets=" + target in gate
assert "/bin/kmod insmod /turing-experiment/turing_unlock.ko\n" in gate

extract = out / "boot-initrd-root"
if extract.exists():
    shutil.rmtree(extract)  # Exclusively this validator's generated extraction.
extract.mkdir()
for name, entry in entries.items():
    path = extract / name
    if stat.S_ISDIR(entry.mode):
        path.mkdir(parents=True, exist_ok=True)
    elif stat.S_ISREG(entry.mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(entry.data)
        path.chmod(stat.S_IMODE(entry.mode))
for name, entry in entries.items():
    if stat.S_ISLNK(entry.mode):
        path = extract / name
        path.parent.mkdir(parents=True, exist_ok=True)
        target_path = entry.data.decode()
        # Keep offline inspection inside the extracted image even if an absolute
        # /nix/store target has since been garbage-collected on the running host.
        if target_path.startswith("/") and target_path.lstrip("/") in entries:
            target_path = os.path.relpath(extract / target_path.lstrip("/"), path.parent)
        path.symlink_to(target_path)
verify = subprocess.run(["systemd-analyze", "verify", "--root=" + str(extract),
                         "--generators=no", "--man=no", "initrd.target"],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(out / "boot-systemd-verify.log").write_text(verify.stdout)
assert verify.returncode == 0, "See results/boot-systemd-verify.log"
for name, text in [("boot-gate.service", unit), ("boot-gate.sh", gate),
                   ("boot-initrd-files.txt", "\n".join(entries) + "\n")]:
    (out / name).write_text(text)
report = {
    "mode": "boot-only", "baseline_system": str(base), "kernel": baseline["kernelVersion"],
    "nvidia_driver": "595.71.05 (unchanged baseline)", "desktop_rebuilt": False,
    "baseline_initrd_members_preserved": len(original_entries), "added_initrd_members": added,
    "microcode_unchanged": True, "firmware": manifest["firmware"],
    "inert_targets": [], "active_preview_targets": [target],
    "unit_verification_status": verify.returncode, "boot_bundle_validated": True,
    "kernel_sha256": hashlib.sha256(Path(boot["kernel"]).read_bytes()).hexdigest(),
    "igpu_module_available": str(igpu_modules[0]),
    "module_bytes": ko.stat().st_size,
    "baseline_initrd_bytes": Path(original_boot["initrd"]).stat().st_size,
    "experiment_initrd_bytes": Path(boot["initrd"]).stat().st_size,
    "initrd_sha256": hashlib.sha256(Path(boot["initrd"]).read_bytes()).hexdigest(),
    "booted_system_unchanged": os.path.realpath("/run/booted-system") == str(base),
}
(out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k not in ("added_initrd_members", "firmware")}, indent=2))
