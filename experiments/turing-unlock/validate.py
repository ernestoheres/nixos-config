#!/usr/bin/env python3
"""Offline validation of built initrd bytes, firmware, unit ordering and Nix isolation."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess

here = Path(__file__).resolve().parent
out = here / "results"
source = (out / "build-source").resolve()
flake = "path:" + str(source)
special = "nixosConfigurations.default-turing-experiment.config.specialisation.turing-experiment.configuration"
discovery = json.loads((out / "discovery/hardware.json").read_text())
detected = [c for c in discovery["drm"] if c["vendor"] == "0x10de"]
assert len(detected) == 1
gpu = detected[0]
target = gpu["pci"]
device = json.loads(subprocess.check_output([
    "nix", "eval", "--json", "--file",
    str(source / "experiments/turing-unlock/device.nix"),
], text=True))
assert device["nvidia"] == {"pci": target, "vendor": gpu["vendor"][2:], "device": gpu["device"][2:]}

def evaluate(attr, apply=None):
    command = ["nix", "eval", "--json", flake + "#" + attr]
    if apply:
        command += ["--apply", apply]
    return json.loads(subprocess.check_output(command, text=True))

info = evaluate(special, '''c: {
  kernel = c.boot.kernelPackages.kernel.modDirVersion;
  kernelPath = toString c.boot.kernelPackages.kernel;
  kernelFile = c.system.boot.loader.kernelFile;
  initrdFile = c.system.boot.loader.initrdFile;
  system = toString c.system.build.toplevel;
  params = c.boot.kernelParams;
  systemdInitrd = c.boot.initrd.systemd.enable;
  modules = c.boot.initrd.kernelModules;
  availableModules = c.boot.initrd.availableKernelModules;
  nvidiaVersion = c.hardware.nvidia.package.version;
  driverConfig = c.hardware.nvidia.prime;
  videoDrivers = c.services.xserver.videoDrivers;
}''')
normal = evaluate("nixosConfigurations.default.config", '''c: {
  systemDrv = c.system.build.toplevel.drvPath;
  initrdDrv = c.system.build.initialRamdisk.drvPath;
  params = c.boot.kernelParams;
  extraModules = map toString c.boot.extraModulePackages;
  specialisations = builtins.attrNames c.specialisation;
  videoDrivers = c.services.xserver.videoDrivers;
  driverConfig = c.hardware.nvidia.prime;
}''')
assert normal["systemDrv"] == "/nix/store/830n634x7x08d6qgb3fb997gz6h09qhv-nixos-system-default-26.05.20261010.6fcc160.drv"
assert normal["initrdDrv"] == "/nix/store/wbpchcvk8qns19ll7z8y3wsnw286y1rw-initrd-linux-6.18.55.drv"
assert not normal["specialisations"]
assert not any("turing" in m for m in normal["extraModules"])
assert normal["params"] == info["params"]
assert normal["driverConfig"] == info["driverConfig"]
assert normal["videoDrivers"] == info["videoDrivers"]
assert not any(p.startswith("turing_unlock.targets=") for p in info["params"])

blob = (out / "initrd" / "initrd").read_bytes()
files = {}
offset = 0
archives = 0
while offset < len(blob):
    if blob[offset:offset + 6] in (b"070701", b"070702"):
        archives += 1
        while True:
            assert blob[offset:offset + 6] in (b"070701", b"070702")
            values = [int(blob[offset+i:offset+i+8], 16) for i in range(6, 110, 8)]
            mode, size, namesize = values[1], values[6], values[11]
            name = blob[offset+110:offset+110+namesize-1].decode().lstrip("./")
            offset = (offset + 110 + namesize + 3) & ~3
            data = blob[offset:offset+size]
            offset = (offset + size + 3) & ~3
            if name == "TRAILER!!!":
                break
            files[name] = (mode, data)
        while offset < len(blob) and blob[offset] == 0:
            offset += 1
    elif blob[offset:offset+4] == b"\x28\xb5\x2f\xfd":
        blob = subprocess.check_output(["zstd", "-dc"], input=blob[offset:])
        offset = 0
    else:
        raise RuntimeError(f"Unknown initrd archive header at {offset}: {blob[offset:offset+8]!r}")

def resolve(name):
    name = name.lstrip("/")
    for _ in range(40):
        parts = PurePosixPath(name).parts
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            if prefix in files and stat.S_ISLNK(files[prefix][0]):
                target = files[prefix][1].decode()
                base = "/" if target.startswith("/") else "/" + "/".join(parts[:i-1])
                name = os.path.normpath(base + "/" + target + "/" + "/".join(parts[i:])).lstrip("/")
                break
        else:
            return files[name][1]
    raise RuntimeError("symlink loop: " + name)

listing = sorted(files)
(out / "initrd-files.txt").write_text("\n".join(listing) + "\n")
modules = [n for n in listing if re.search(r"/turing_unlock\.ko(?:\.(?:zst|xz))?$", n)]
assert len(modules) == 1, modules
amdgpu = [n for n in listing if re.search(r"/amdgpu\.ko(?:\.(?:zst|xz))?$", n)]
assert amdgpu
assert not [n for n in listing if re.search(r"/(?:nvidia(?:_drm|_modeset|_uvm)?|nouveau)\.ko", n)]
assets = json.loads((out / "assets.json").read_text())["outputs"]
for asset in assets:
    log = subprocess.check_output(["nix", "log", asset["drvPath"]], text=True)
    name = "firmware-build.log" if "firmware" in asset["drvPath"] else "module-build.log"
    (out / name).write_text(log)
module = next(Path(x["outputs"]["out"]) for x in assets if "firmware" not in x["drvPath"])
modinfo = subprocess.check_output(["modinfo", str(module / "lib/modules" / info["kernel"] / "extra/turing_unlock.ko")], text=True)
assert re.search(r"^vermagic:\s+" + re.escape(info["kernel"]) + r"\s", modinfo, re.M)
(out / "module-info.txt").write_text(modinfo)
firmware = next(Path(x["outputs"]["out"]) for x in assets if "firmware" in x["drvPath"])
expected = json.loads((firmware / "share/turing-unlock/firmware-hashes.json").read_text())
hashes = {}
for name, entry in expected.items():
    if not name.endswith(".bin"):
        continue
    path = "lib/firmware/turing-unlock/610.43.03/" + name
    try:
        data = resolve(path)
    except KeyError:
        data = subprocess.check_output(["zstd", "-dc"], input=resolve(path + ".zst"))
        path += ".zst"
    assert hashlib.sha256(data).hexdigest() == entry["sha256"], name
    hashes[name] = {**entry, "initrd_path": path}
assert len(hashes) == 6
unitdir = "etc/systemd/system/"
gate = resolve(unitdir + "turing-unlock-gate.service").decode()
(out / "gate.service").write_text(gate)
before = set(re.search(r"^Before=(.*)$", gate, re.M)[1].split())
for name in ["systemd-udevd.service", "systemd-udevd-control.socket", "systemd-udevd-kernel.socket",
             "systemd-udev-trigger.service", "systemd-modules-load.service"]:
    assert name in before
    text = resolve(unitdir + name).decode()
    try:
        text += "\n" + resolve(unitdir + name + ".d/overrides.conf").decode()
    except KeyError:
        pass
    assert "turing-unlock-gate.service" in " ".join(re.findall(r"^Requires=(.*)$", text, re.M)).split()
script_path = re.search(r"^ExecStart=(.*)$", gate, re.M)[1].strip()
script = resolve(script_path).decode()
assert "/bin/modprobe turing_unlock" in script
assert "turing_unlock.targets=" + target in script
assert gpu["device"] in script and gpu["vendor"] in script
(out / "gate-script.sh").write_text(script)
assert "turing_unlock" not in resolve("etc/modules-load.d/nixos.conf").decode()
assert "softdep nvidia pre: turing_unlock" in resolve("etc/modprobe.d/nixos.conf").decode()

# Extract the generated image for systemd's own offline dependency/cycle verifier.
extract = out / "initrd-root"
if extract.exists():
    # This directory is exclusively this validator's generated archive extraction.
    # Recreate it instead of following stale image symlinks or rewriting 0444 files.
    shutil.rmtree(extract)
extract.mkdir()
for name in listing:
    assert ".." not in PurePosixPath(name).parts
    mode, data = files[name]
    p = extract / name
    if stat.S_ISDIR(mode):
        p.mkdir(parents=True, exist_ok=True)
    elif stat.S_ISREG(mode):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        p.chmod(stat.S_IMODE(mode))
for name in listing:
    mode, data = files[name]
    if stat.S_ISLNK(mode):
        p = extract / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_symlink():
            p.symlink_to(data.decode())
verify = subprocess.run(["systemd-analyze", "verify", "--root=" + str(extract),
                         "--generators=no", "--man=no", "initrd.target"],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(out / "systemd-verify.log").write_text(verify.stdout)
if verify.returncode:
    raise SystemExit("systemd unit verification failed; see results/systemd-verify.log")

preview = out / "boot-preview"
metadata = {"kernel": info["kernelPath"] + "/" + info["kernelFile"],
            "initrd": str((out / "initrd").resolve()) + "/" + info["initrdFile"],
            "init": info["system"] + "/init", "kernelParams": info["params"]}
(out / "preview-bootspec.json").write_text(json.dumps(metadata, indent=2) + "\n")
if preview.exists():
    shutil.rmtree(preview)
subprocess.run(["python3", str(here / "make-boot-bundle.py"), info["system"],
                str(preview), target, str(out / "preview-bootspec.json")], check=True)
inert_entry = (preview / "turing-experiment-inert.conf").read_text()
active_entry = (preview / "active-preview.conf").read_text()
assert "turing_unlock.targets=" not in inert_entry
assert [p for p in active_entry.split() if p.startswith("turing_unlock.targets=")] == ["turing_unlock.targets=" + target]
full_system_built = (Path(info["system"]) / "init").is_file()
bundle_validated = False
bundle = out / "boot-bundle"
if bundle.exists():
    provenance = json.loads((bundle / "provenance.json").read_text())
    if provenance["system"] == info["system"]:
        assert full_system_built and not provenance["preview_only"]
        assert provenance["bootspec"]["kernelParams"] == info["params"]
        assert "turing_unlock.targets=" not in (bundle / "turing-experiment-inert.conf").read_text()
        assert [p for p in (bundle / "active-preview.conf").read_text().split()
                if p.startswith("turing_unlock.targets=")] == ["turing_unlock.targets=" + target]
        for name, expected in [("linux.efi", metadata["kernel"]), ("initrd", metadata["initrd"])]:
            assert (bundle / provenance["esp_directory"] / name).resolve() == Path(expected).resolve()
        bundle_validated = True
report = {"normal": normal, "experiment": info, "cpio_archives": archives,
          "module_in_initrd": modules, "amdgpu_in_initrd": amdgpu,
          "firmware": hashes, "unit_verification_status": verify.returncode,
          "normal_drv_unchanged": True, "inert_targets": [],
          "active_preview_targets": [target],
          "full_system_built": full_system_built, "boot_bundle_validated": bundle_validated,
          "booted_system_unchanged": os.path.realpath("/run/booted-system") == os.path.realpath(out / "preserved-normal-system")}
(out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
