#!/usr/bin/env python3
"""Non-activating build driver. No sudo, installation, module loading or GPU execution."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--boot-only", action="store_true",
                    help="build a separate initrd/entry using the existing desktop (default)")
parser.add_argument("--full-system", action="store_true",
                    help="deprecated alias for --boot-only; never rebuilds the desktop")
args = parser.parse_args()
if args.full_system:
    print("--full-system now uses the boot-only build; the desktop will not be rebuilt.", flush=True)
here = Path(__file__).resolve().parent
root = here.parent.parent
out = here / "results"
out.mkdir(exist_ok=True)
if not (out / "discovery/hardware.json").exists():
    subprocess.run(["python3", str(here / "capture.py")], cwd=root, check=True)
if not (out / "preserved-normal-system").exists():
    subprocess.run(["nix-store", "--realise", "/run/booted-system", "--add-root",
                    str(out / "preserved-normal-system")], check=True)
source = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--file", str(here / "source-tree.nix")],
    cwd=root, text=True).strip()
flake = "path:" + source
subprocess.run(["nix-store", "--realise", source, "--add-root", str(out / "build-source")], check=True)

def build(name, attrs):
    command = ["nix", "build", "--impure", *[flake + "#" + a for a in attrs],
               "--out-link", str(out / name), "--json", "-L"]
    print("Building " + name + "; log: " + str(out / (name + ".log")), flush=True)
    with (out / (name + ".log")).open("w") as log:
        result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=log)
    if result.returncode:
        raise SystemExit(f"Build failed ({result.returncode}); inspect {out / (name + '.log')}")
    outputs = json.loads(result.stdout)
    (out / (name + ".json")).write_text(json.dumps({"command": command, "outputs": outputs}, indent=2) + "\n")
    return outputs

# Fetch and verify exact archives separately; all asset generation is offline.
build("inputs", ["turing-unlock-nvidia-source", "turing-unlock-nvidia-utils",
                 "turing-unlock-published-checksum"])
build("boot-assets", ["turing-unlock-boot-module", "turing-unlock-firmware"])
# Keep signed binary-cache substitution available for missing build tools.
# The derivations themselves remain network-isolated by Nix's sandbox.
build("boot-initrd", ["turing-unlock-boot-initrd"])
build("boot-only", ["turing-unlock-boot-bundle"])
print("Non-activating builds completed. Nothing installed.", flush=True)
