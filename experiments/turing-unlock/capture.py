#!/usr/bin/env python3
"""Read-only live discovery and evaluation, saved persistently beside this script."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

here = Path(__file__).resolve().parent
root = here.parent.parent
out = here / "results" / "discovery"
out.mkdir(parents=True, exist_ok=False)

def capture(name, command):
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (out / name).write_text(result.stdout)
    return {"command": command, "status": result.returncode, "output": result.stdout}

commands = {
    "lspci-display.txt": ["bash", "-c", "lspci -Dnn | grep -Ei 'vga|3d|display'"],
    "lspci-drivers.txt": ["bash", "-c", "lspci -Dnnk | grep -A 5 -Ei 'vga|3d|display'"],
    "nvidia-query.txt": ["nvidia-smi", "--query-gpu=name,pci.bus_id,power.limit", "--format=csv"],
    "nvidia-full.txt": ["nvidia-smi", "-q"],
    "bootctl.txt": ["bootctl", "status"],
    "bootctl-list.txt": ["bootctl", "list"],
    "generations.txt": ["nix-env", "--list-generations", "-p", "/nix/var/nix/profiles/system"],
    "kernel.txt": ["uname", "-r"],
    "monitors.json": ["hyprctl", "monitors", "-j"],
    "git-status.txt": ["git", "status", "--short"],
    "git-revision.txt": ["git", "rev-parse", "HEAD"],
    "normal-toplevel-drv.txt": ["nix", "eval", "--raw", "path:.#nixosConfigurations.default.config.system.build.toplevel.drvPath"],
    "normal-initrd-drv.txt": ["nix", "eval", "--raw", "path:.#nixosConfigurations.default.config.system.build.initialRamdisk.drvPath"],
}
results = {name: capture(name, command) for name, command in commands.items()}
cards = []
for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
    if "-" in card.name:
        continue
    dev = card / "device"
    cards.append({"card": card.name, "pci": dev.resolve().name,
                  "driver": (dev / "driver").resolve().name,
                  **{k: (dev / k).read_text().strip() for k in ["vendor", "device", "boot_vga"]},
                  "connectors": [{"name": c.name, **{
                      k: (c / k).read_text().strip() for k in ["status", "enabled", "modes"]
                      if (c / k).exists()}}
                      for c in sorted(Path("/sys/class/drm").glob(card.name + "-*"))]})
report = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "systems": {p: os.path.realpath(p) for p in ["/run/current-system", "/run/booted-system",
                      "/nix/var/nix/profiles/system", "/nix/var/nix/profiles/system-83-link"]},
          "cmdline": Path("/proc/cmdline").read_text().strip(), "drm": cards,
          "commands": results,
          "benchmark_hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path.home() / "cuda-experiment" / name
                        for name in ["tensor_bench.cu", "run_benchmark.py", "flake.nix", "flake.lock"]]}}
(out / "hardware.json").write_text(json.dumps(report, indent=2) + "\n")
print(out)
