#!/usr/bin/env python3
"""Add the experiment to an existing initrd; preserve every existing archive member."""
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

from initrd_archive import add, read_initrd, resolve_name, serialize_newc

baseline, module, firmware, out, device_file = map(Path, sys.argv[1:6])
device = json.loads(device_file.read_text())["nvidia"]
target = device["pci"]
boot = json.loads((baseline / "boot.json").read_text())["org.nixos.bootspec.v1"]
assert boot["init"] == str(baseline / "init")
early, entries = read_initrd(Path(boot["initrd"]))
assert not any(re.search(r"/(?:nvidia(?:_drm|_modeset|_uvm)?|nouveau)\.ko", n) for n in entries)
for tool in ("/bin/sh", "/bin/kmod", "/bin/cat"):
    assert resolve_name(entries, tool) in entries, tool
module_files = list((module / "lib/modules").glob("*/extra/turing_unlock.ko"))
assert len(module_files) == 1
ko = module_files[0]
assert not subprocess.check_output(["modinfo", "-F", "depends", str(ko)], text=True).strip()
add(entries, "turing-experiment/turing_unlock.ko", ko.read_bytes())
fwroot = resolve_name(entries, "lib/firmware")
manifest = json.loads((firmware / "share/turing-unlock/firmware-hashes.json").read_text())
hashes = {}
for name, info in manifest.items():
    if not name.endswith(".bin"):
        continue
    data = (firmware / "lib/firmware/turing-unlock/610.43.03" / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == info["sha256"]
    add(entries, fwroot + "/turing-unlock/610.43.03/" + name, data)
    hashes[name] = info
assert len(hashes) == 6
gate = f'''#!/bin/sh
set -eu
count=0
for arg in $(cat /proc/cmdline); do
  case "$arg" in
    turing_unlock.targets=*)
      test "$arg" = 'turing_unlock.targets={target}'
      count=$((count + 1))
      ;;
  esac
done
test "$count" -le 1
test ! -d /sys/module/turing_unlock
if test "$count" -eq 1; then
  test "$(cat /sys/bus/pci/devices/{target}/vendor)" = '0x{device["vendor"]}'
  test "$(cat /sys/bus/pci/devices/{target}/device)" = '0x{device["device"]}'
  test ! -L /sys/bus/pci/devices/{target}/driver
fi
echo "turing-unlock gate: target count=$count; loading once before udev and modules-load"
if test "$count" -eq 1; then
  /bin/kmod insmod /turing-experiment/turing_unlock.ko targets={target}
else
  /bin/kmod insmod /turing-experiment/turing_unlock.ko
fi
echo "turing-unlock gate: module initialization completed"
'''
add(entries, "turing-experiment/gate.sh", gate.encode(), stat.S_IFREG | 0o755)
unitroot = resolve_name(entries, "etc/systemd/system")
before = ["systemd-udevd.service", "systemd-udevd-control.socket", "systemd-udevd-kernel.socket",
          "systemd-udev-trigger.service", "systemd-modules-load.service"]
unit = ("[Unit]\nDescription=Opt-in Turing experiment before GPU driver probing\n"
        "DefaultDependencies=no\nBefore=" + " ".join(before) + "\n"
        "[Service]\nType=oneshot\nRemainAfterExit=yes\n"
        "ExecStart=/bin/sh /turing-experiment/gate.sh\n")
add(entries, unitroot + "/turing-unlock-gate.service", unit.encode())
add(entries, unitroot + "/sysinit.target.wants/turing-unlock-gate.service",
    b"../turing-unlock-gate.service", stat.S_IFLNK | 0o777)
for name in before:
    assert resolve_name(entries, unitroot + "/" + name) in entries, name
    add(entries, unitroot + "/" + name + ".d/turing-experiment.conf",
        b"[Unit]\nRequires=turing-unlock-gate.service\nAfter=turing-unlock-gate.service\n")
out.mkdir()
main = serialize_newc(entries)
compressed = subprocess.check_output(["zstd", "-q", "-T1", "-10", "-c"], input=main)
(out / "initrd").write_bytes(early + compressed)
(out / "provenance.json").write_text(json.dumps({
    "baseline_system": str(baseline), "baseline_bootspec": boot,
    "firmware": hashes, "module": str(ko), "target": target,
    "baseline_initrd_sha256": hashlib.sha256(Path(boot["initrd"]).read_bytes()).hexdigest(),
    "initrd_sha256": hashlib.sha256(early + compressed).hexdigest(),
    "entry_count": len(entries),
}, indent=2) + "\n")
