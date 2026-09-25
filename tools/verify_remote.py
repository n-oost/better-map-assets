"""Developer-only authenticated GitHub verification; no credentials enter assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="owner/repository")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise ValueError("Invalid repository")
    base = "repos/" + args.repository + "/contents/"
    headers = ["-H", "Accept: application/vnd.github.raw+json"]
    channel = json.loads(subprocess.check_output(
        ["gh", "api", base + "channels/tiles-v1.json?ref=main", *headers], timeout=60))
    pack = channel["pack"]
    if not re.fullmatch(r"[0-9a-f]{40}", channel["commit"]) or not re.fullmatch(r"packs/[0-9a-f]{64}\.zip", pack["path"]):
        raise ValueError("Unexpected channel path/commit")
    with tempfile.TemporaryDirectory(prefix="better-map-remote-verify-") as folder:
        archive_path = Path(folder) / "pack.zip"
        checkout = Path(folder) / "remote"
        # Git transports binary bytes reliably even on gh installations whose
        # console transcoder rejects binary API response bodies on Windows.
        subprocess.run(["git", "clone", "--quiet", "--no-checkout",
                        "https://github.com/" + args.repository + ".git", str(checkout)],
                       check=True, timeout=300)
        with archive_path.open("wb") as output:
            subprocess.run(["git", "-C", str(checkout), "show", channel["commit"] + ":" + pack["path"]],
                           stdout=output, check=True, timeout=300)
        actual_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if archive_path.stat().st_size != pack["compressedBytes"] or actual_hash != pack["sha256"]:
            raise ValueError("Remote archive size/hash mismatch")
        with zipfile.ZipFile(archive_path) as archive:
            inventory = json.loads(archive.read("inventory.json"))
            if inventory["compatibilityId"] != channel["compatibilityId"]:
                raise ValueError("Compatibility mismatch")
            expected = set(inventory["files"]) | {"inventory.json"}
            if len(archive.namelist()) != pack["fileCount"] or len(expected) != pack["fileCount"] or set(archive.namelist()) != expected:
                raise ValueError("Remote file inventory mismatch")
            if sum(entry.file_size for entry in archive.infolist()) != pack["uncompressedBytes"]:
                raise ValueError("Expanded size mismatch")
            for name, metadata in inventory["files"].items():
                data = archive.read(name)
                if len(data) != metadata["size"] or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
                    raise ValueError("Remote payload mismatch: " + name)
            index = archive.read("tiles/index.txt").decode("utf-8").splitlines()
            if {"tiles/" + tile for tile in index} != expected - {"inventory.json", "tiles/index.txt"}:
                raise ValueError("Tile index mismatch")
        print(json.dumps({"repository": args.repository, "verifiedSha256": actual_hash,
                          "tileCount": len(index), "bytes": pack["compressedBytes"]}))


if __name__ == "__main__":
    main()
