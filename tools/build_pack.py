"""Build and verify a deterministic imagery pack; never upload or delete inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_entry(archive, name, data):
    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compresslevel=9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packed", type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--extra-packed", type=Path, help="Additional packed map-0 tiles, e.g. native zoom 3")
    parser.add_argument("--output", type=Path, help="Destination asset repository")
    args = parser.parse_args()
    tools_root = Path(__file__).resolve().parent
    root = args.output or tools_root.parent
    inputs = {}
    for folder in (args.packed, args.extra_packed):
        if folder is None:
            continue
        for path in sorted(folder.joinpath("0").rglob("*.png")):
            relative = path.relative_to(folder).as_posix()
            if relative in inputs:
                raise ValueError("Duplicate tile: " + relative)
            inputs[relative] = path
    paths = sorted(inputs)
    if not paths or len(paths) != len(set(paths)) or len(paths) > 49998:
        raise ValueError("Empty, duplicate, or oversized tile index")
    paths = sorted(paths)
    inventory = {"schemaVersion": 1, "compatibilityId": "better-map-tiles-v1", "coverage": {}, "files": {}}
    for relative in paths:
        match = re.fullmatch(r"(0)/(-[1-3]|[0-3])/([0-3])_(\d{1,5})_(\d{1,5})\.png", relative)
        if not match:
            raise ValueError("Unsupported tile path: " + relative)
        data = inputs[relative].read_bytes()
        if len(data) > 1048576 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or struct.unpack(">II", data[16:24]) != (256, 256):
            raise ValueError("Invalid PNG signature/dimensions/size: " + relative)
        name = "tiles/" + relative
        inventory["files"][name] = {"size": len(data), "sha256": digest(data)}
        key = "/".join(match.group(i) for i in (1, 2, 3))
        inventory["coverage"][key] = inventory["coverage"].get(key, 0) + 1
    index = ("\n".join(paths) + "\n").encode("utf-8")
    inventory["files"]["tiles/index.txt"] = {"size": len(index), "sha256": digest(index)}
    manifest = encoded(inventory)
    expanded = len(manifest) + sum(item["size"] for item in inventory["files"].values())
    if len(manifest) > 8 * 1048576 or expanded > 256 * 1048576:
        raise ValueError("Pack exceeds extracted limits")
    packs = root / "packs"
    packs.mkdir(exist_ok=True)
    temporary = packs / "building.zip.part"
    with temporary.open("xb") as output, zipfile.ZipFile(output, "w") as archive:
        write_entry(archive, "inventory.json", manifest)
        write_entry(archive, "tiles/index.txt", index)
        for relative in paths:
            write_entry(archive, "tiles/" + relative, inputs[relative].read_bytes())
    if temporary.stat().st_size > 128 * 1048576:
        raise ValueError("Archive exceeds transfer limit")
    with zipfile.ZipFile(temporary) as archive:
        expected = set(inventory["files"]) | {"inventory.json"}
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("Archive inventory mismatch")
        if archive.read("inventory.json") != manifest:
            raise ValueError("Inventory changed")
        for name, entry in inventory["files"].items():
            data = archive.read(name)
            if len(data) != entry["size"] or digest(data) != entry["sha256"]:
                raise ValueError("Archive verification failed: " + name)
    pack_hash = digest(temporary.read_bytes())
    target = packs / (pack_hash + ".zip")
    if target.exists():
        raise FileExistsError("Pack already exists; original preserved: " + target.name)
    temporary.rename(target)
    source = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    allowed = ("timestamp", "regionsRendered", "regionsWithDecryptedObjects")
    baseline = {}
    resources = args.plugin / "src/main/resources/com/bettermap"
    for category in ("data", "dungeons", "poi"):
        for path in sorted(resources.joinpath(category).rglob("*")):
            if path.is_file():
                baseline[path.relative_to(resources).as_posix()] = digest(path.read_bytes())
    metadata = {
        "schemaVersion": 1, "compatibilityId": "better-map-tiles-v1", "assetVersion": args.version,
        "pack": {"path": "packs/" + target.name, "sha256": pack_hash,
                 "compressedBytes": target.stat().st_size, "uncompressedBytes": expanded,
                 "fileCount": len(inventory["files"]) + 1},
        "tileCount": len(paths), "mapIds": sorted({int(path.split('/')[0]) for path in paths}),
        "sourceSummary": {key: source[key] for key in allowed if key in source},
        "provenanceStatus": "Map 0 only: cache-rendered imagery; zoom 3 rendered natively at 8 pixels per game tile",
        "companionBundledDataSha256": baseline,
        "packerSourceSha256": digest(tools_root.joinpath("TilePacker.java").read_bytes()),
        "rendererSourceSha256": digest(tools_root.joinpath("renderer/net/runelite/cache/HighDetailMapImageDumper.java").read_bytes()),
        "zoomLevels": sorted({int(path.split('/')[1]) for path in paths})
    }
    destination = root / "metadata" / (pack_hash + ".json")
    destination.parent.mkdir(exist_ok=True)
    with destination.open("xb") as output:
        output.write(encoded(metadata))
    print(json.dumps({"metadata": str(destination), "sha256": pack_hash, "tileCount": len(paths), "bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
