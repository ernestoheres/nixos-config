"""Read/write the existing NixOS early-CPIO + zstd newc initrd, without executing it."""
from dataclasses import dataclass
import os
from pathlib import PurePosixPath
import stat
import subprocess


@dataclass
class Entry:
    fields: list[int]
    data: bytes

    @property
    def mode(self):
        return self.fields[1]


def parse_newc(blob):
    entries = {}
    offset = 0
    while True:
        if blob[offset:offset + 6] != b"070701":
            raise ValueError(f"Invalid newc header at {offset}")
        fields = [int(blob[offset + i:offset + i + 8], 16) for i in range(6, 110, 8)]
        size, namesize = fields[6], fields[11]
        raw_name = blob[offset + 110:offset + 110 + namesize]
        if not namesize or not raw_name.endswith(b"\0"):
            raise ValueError("Invalid CPIO name")
        name = raw_name[:-1].decode().removeprefix("./").lstrip("/")
        if ".." in PurePosixPath(name).parts:
            raise ValueError("CPIO path traversal")
        offset = (offset + 110 + namesize + 3) & ~3
        data = blob[offset:offset + size]
        if len(data) != size:
            raise ValueError("Truncated CPIO data")
        offset = (offset + size + 3) & ~3
        if name == "TRAILER!!!":
            return entries, offset
        if name in entries:
            raise ValueError(f"Duplicate CPIO member: {name}")
        entries[name] = Entry(fields, data)


def read_initrd(path):
    blob = path.read_bytes()
    offset = 0
    if blob.startswith(b"070701"):
        _, offset = parse_newc(blob)
        while offset < len(blob) and blob[offset] == 0:
            offset += 1
    if blob[offset:offset + 4] != b"\x28\xb5\x2f\xfd":
        raise ValueError("Expected the pinned baseline's zstd-compressed main archive")
    main = subprocess.check_output(["zstd", "-dc"], input=blob[offset:])
    entries, _ = parse_newc(main)
    return blob[:offset], entries


def resolve_name(entries, name):
    name = name.lstrip("/")
    for _ in range(40):
        parts = PurePosixPath(name).parts
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            if prefix in entries and stat.S_ISLNK(entries[prefix].mode):
                target = entries[prefix].data.decode()
                parent = "/" if target.startswith("/") else "/" + "/".join(parts[:i - 1])
                name = os.path.normpath(parent + "/" + target + "/" + "/".join(parts[i:])).lstrip("/")
                break
        else:
            return name
    raise ValueError("CPIO symlink loop")


def add(entries, name, data=b"", mode=stat.S_IFREG | 0o644):
    if name in entries:
        raise ValueError(f"Refusing to replace a baseline initrd member: {name}")
    parent = str(PurePosixPath(name).parent)
    if parent != "." and parent not in entries:
        add(entries, parent, mode=stat.S_IFDIR | 0o755)
    inode = max((e.fields[0] for e in entries.values()), default=0) + 1
    entries[name] = Entry([inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, 0, 0], data)


def serialize_newc(entries):
    result = bytearray()
    members = list(entries.items()) + [("TRAILER!!!", Entry([0] * 13, b""))]
    for name, entry in members:
        encoded = name.encode() + b"\0"
        fields = entry.fields.copy()
        fields[6], fields[11] = len(entry.data), len(encoded)
        result.extend(b"070701" + b"".join(f"{v:08x}".encode() for v in fields))
        result.extend(encoded)
        result.extend(b"\0" * (-len(result) % 4))
        result.extend(entry.data)
        result.extend(b"\0" * (-len(result) % 4))
    result.extend(b"\0" * (-len(result) % 512))
    return bytes(result)
