"""Verify an anonymous public download, including hashes, PNG chunks, map IDs and zooms."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request
import zipfile
from prepare_public import verify_png


def validate(pack_path, channel):
    pack = channel["pack"]
    if pack_path.stat().st_size != pack["compressedBytes"]:
        raise ValueError("Archive size mismatch")
    if hashlib.sha256(pack_path.read_bytes()).hexdigest() != pack["sha256"]:
        raise ValueError("Archive hash mismatch")
    counts = {}
    with zipfile.ZipFile(pack_path) as archive:
        inventory = json.loads(archive.read("inventory.json"))
        expected = set(inventory["files"]) | {"inventory.json"}
        if inventory["compatibilityId"] != channel["compatibilityId"]:
            raise ValueError("Compatibility mismatch")
        if len(archive.namelist()) != pack["fileCount"] or set(archive.namelist()) != expected:
            raise ValueError("Unexpected or duplicate files")
        if sum(item.file_size for item in archive.infolist()) != pack["uncompressedBytes"]:
            raise ValueError("Expanded size mismatch")
        for name, entry in inventory["files"].items():
            data = archive.read(name)
            if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("Payload mismatch")
            if name == "tiles/index.txt":
                continue
            match = re.fullmatch(r"tiles/0/(-[1-3]|[0-3])/[0-3]_\d+_\d+\.png", name)
            if not match:
                raise ValueError("Public pack contains an unexpected map or file")
            verify_png(data)
            zoom = int(match[1])
            counts[zoom] = counts.get(zoom, 0) + 1
        index = archive.read("tiles/index.txt").decode().splitlines()
        if len(index) != len(set(index)) or {"tiles/" + p for p in index} != expected - {"inventory.json", "tiles/index.txt"}:
            raise ValueError("Index mismatch")
    if set(counts) != set(range(-3, 4)):
        raise ValueError("Public pack must contain every zoom from -3 through 3")
    return {"sha256": pack["sha256"], "bytes": pack["compressedBytes"], "mapIds": [0], "tilesByZoom": counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", default="n-oost/better-map-assets")
    parser.add_argument("--local", type=Path, help="Validate a staged repository without network access")
    args = parser.parse_args()
    if args.local:
        channel = json.loads(args.local.joinpath("channels/tiles-v1.json").read_text())
        result = validate(args.local / channel["pack"]["path"], channel)
    else:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
            raise ValueError("Invalid repository")
        base = "https://raw.githubusercontent.com/" + args.repository + "/"
        with urllib.request.urlopen(base + "main/channels/tiles-v1.json", timeout=60) as response:
            channel = json.loads(response.read(16384))
        if not re.fullmatch(r"[0-9a-f]{40}", channel["commit"]) or not re.fullmatch(r"packs/[0-9a-f]{64}\.zip", channel["pack"]["path"]):
            raise ValueError("Invalid channel URL components")
        with tempfile.TemporaryDirectory(prefix="better-map-public-check-") as folder:
            path = Path(folder) / "pack.zip"
            size = 0
            with urllib.request.urlopen(base + channel["commit"] + "/" + channel["pack"]["path"], timeout=60) as response, path.open("xb") as output:
                while chunk := response.read(65536):
                    size += len(chunk)
                    if size > 128 * 1048576:
                        raise ValueError("Download exceeds limit")
                    output.write(chunk)
            result = validate(path, channel)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
