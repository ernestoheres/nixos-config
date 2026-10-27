#!/usr/bin/env python3
"""Generate reviewable BLS entries from the built bootspec; never install them."""
import json
import hashlib
from pathlib import Path
import re
import sys

system, out = map(Path, sys.argv[1:3])
target = sys.argv[3]
preview = len(sys.argv) == 5
boot = json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) >= 5 else json.loads(
    (system / "boot.json").read_text())["org.nixos.bootspec.v1"]
params = ["init=" + boot["init"], *boot["kernelParams"]]
assert not any(p.startswith("turing_unlock.targets=") for p in params)
assert re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", target)
if not preview:
    assert (system / "init").is_file(), "The complete system must be built first"
directory = "EFI/turing-experiment-" + hashlib.sha256(
    json.dumps(boot, sort_keys=True).encode()).hexdigest()[:32]
(out / directory).mkdir(parents=True)
for key, name in [("kernel", "linux.efi"), ("initrd", "initrd")]:
    (out / directory / name).symlink_to(boot[key])
entry = ("title NixOS turing-experiment (INERT)\n"
         "sort-key zzzz-turing-experiment\n"
         f"linux /{directory}/linux.efi\ninitrd /{directory}/initrd\n"
         "options " + " ".join(params) + "\n")
if preview:
    entry = entry.replace("(INERT)", "(INERT PREVIEW - SYSTEM BUILD REQUIRED)")
(out / "turing-experiment-inert.conf").write_text(entry)
# Preview only. Install the inert entry; use a transient boot-menu edit for active testing.
active = re.sub(r"^title .*$", "title NixOS turing-experiment (ACTIVE PREVIEW - DO NOT INSTALL)",
                entry, count=1, flags=re.M)
active = active.rstrip() + f" turing_unlock.targets={target}\n"
assert active.count("turing_unlock.targets=") == 1
(out / "active-preview.conf").write_text(active)
(out / "provenance.json").write_text(json.dumps({
    "system": str(system), "bootspec": boot, "esp_directory": directory,
    "inert_targets": [], "active_preview_targets": [target], "preview_only": preview,
    "boot_only": len(sys.argv) == 6 and sys.argv[5] == "--boot-only",
}, indent=2) + "\n")
