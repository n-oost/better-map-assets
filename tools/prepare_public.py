"""Verify a snapshot, archive unused maps locally, and stage only map 0 for publication."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_png(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG")
    cursor = 8
    kinds = []
    while cursor < len(data):
        size = struct.unpack(">I", data[cursor:cursor + 4])[0]
        kind = data[cursor + 4:cursor + 8]
        payload = data[cursor + 8:cursor + 8 + size]
        crc = struct.unpack(">I", data[cursor + 8 + size:cursor + 12 + size])[0]
        if kind not in (b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS"):
            raise ValueError("Unexpected PNG chunk: " + repr(kind))
        if zlib.crc32(kind + payload) != crc:
            raise ValueError("PNG CRC mismatch")
        if kind == b"IHDR" and struct.unpack(">II", payload[:8]) != (256, 256):
            raise ValueError("Unexpected dimensions")
        kinds.append(kind)
        cursor += size + 12
    if cursor != len(data) or kinds[0] != b"IHDR" or kinds[-1] != b"IEND":
        raise ValueError("Unexpected PNG structure or trailing payload")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("local_archive", type=Path)
    parser.add_argument("map0_output", type=Path)
    args = parser.parse_args()
    if args.local_archive.exists() or args.map0_output.exists():
        raise ValueError("Outputs must be new paths")
    args.local_archive.parent.mkdir(parents=True, exist_ok=True)
    args.map0_output.mkdir(parents=True)
    report = {"sourcePackSha256": sha(args.snapshot.read_bytes()), "files": {}}
    kept = []
    with zipfile.ZipFile(args.snapshot) as snapshot, zipfile.ZipFile(args.local_archive, "x", zipfile.ZIP_DEFLATED) as archive:
        inventory = json.loads(snapshot.read("inventory.json"))
        expected = set(inventory["files"]) | {"inventory.json"}
        if len(snapshot.namelist()) != len(expected) or set(snapshot.namelist()) != expected:
            raise ValueError("Snapshot inventory mismatch")
        for name, entry in inventory["files"].items():
            data = snapshot.read(name)
            if len(data) != entry["size"] or sha(data) != entry["sha256"]:
                raise ValueError("Snapshot hash mismatch")
            if name == "tiles/index.txt":
                continue
            if not re.fullmatch(r"tiles/\d+/(-[1-3]|[0-3])/[0-3]_\d+_\d+\.png", name):
                raise ValueError("Unexpected snapshot file")
            verify_png(data)
            relative = name.removeprefix("tiles/")
            if relative.startswith("0/"):
                target = args.map0_output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                kept.append(relative)
            else:
                archive.writestr(relative, data)
                report["files"][relative] = {"size": len(data), "sha256": sha(data)}
        archive.writestr("archive-inventory.json", json.dumps(report, indent=2) + "\n")
    with zipfile.ZipFile(args.local_archive) as archive:
        for name, entry in report["files"].items():
            data = archive.read(name)
            if len(data) != entry["size"] or sha(data) != entry["sha256"]:
                raise ValueError("Local archive verification failed")
    args.map0_output.joinpath("index.txt").write_text("\n".join(sorted(kept)) + "\n", encoding="utf-8")
    print(json.dumps({"map0Tiles": len(kept), "archivedTiles": len(report["files"]),
                      "archiveSha256": sha(args.local_archive.read_bytes()),
                      "pngMetadata": "Only image chunks; no text, EXIF, or trailing payload"}))


if __name__ == "__main__":
    main()
