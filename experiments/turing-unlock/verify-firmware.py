#!/usr/bin/env python3
"""Verify the exact six assets and license against the pinned upstream manifest."""
import hashlib
import json
from pathlib import Path
import sys

manifest = json.loads(Path(sys.argv[1]).read_text())
assets = Path(sys.argv[2])
expected = dict(manifest["derived_assets"])
gsp = manifest["source_artifacts"][1]["firmware"][0]
expected[Path(gsp["path"]).name] = gsp["sha256"]
expected["v67-tu102-610.43.03.bin"] = manifest["tu102_payload"]["sha256"]
assert len(expected) == 6
assert {p.name for p in assets.glob("*.bin")} == set(expected)
expected["NVIDIA-LICENSE"] = manifest["source_artifacts"][1]["notice"]["sha256"]
results = {}
for name, digest in expected.items():
    data = (assets / name).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != digest:
        raise SystemExit(f"SHA256 mismatch: {name}: {actual} != {digest}")
    results[name] = {"sha256": actual, "bytes": len(data)}
assert results["gsp_tu10x.bin"]["bytes"] == gsp["size"]
assert results["v67-tu102-610.43.03.bin"]["bytes"] == manifest["tu102_payload"]["size"]
print(json.dumps(results, indent=2, sort_keys=True))
