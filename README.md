# Better Map Assets

Asset repository and distribution channel for the [Better Map](https://github.com/n-oost/runelite-plugin-better-map-2) RuneLite plugin. Hosts immutable map tile packs and channel manifests used by the plugin's automatic map downloader.

## Layout

- `packs/<sha256>.zip` — Complete tile imagery pack containing `inventory.json`, `tiles/index.txt`, and PNG tiles.
- `metadata/<sha256>.json` — Pack metadata, tile counts, and build details.
- `channels/tiles-v1.json` — Channel manifest pointing to the active commit-pinned pack.
- `tools/` — Build and verification scripts for tile packing, ZIP creation, and integrity checks.

## Building a pack

1. **Pack tiles**:
   ```bash
   java tools/TilePacker.java <tile-source-dir> <packed-output-dir> 2
   ```

2. **Build and hash the ZIP archive**:
   ```bash
   python tools/build_pack.py <packed-output-dir> --source-manifest <tile-source-dir>/manifest.json --plugin <plugin-root> --version <version>
   ```

3. **Publish**:
   - Commit the generated `packs/<sha256>.zip` and `metadata/<sha256>.json`.
   - Update `channels/tiles-v1.json` with the new commit SHA and metadata.
   - Commit the channel update.

4. **Verify remote integrity**:
   ```bash
   python tools/verify_remote.py n-oost/better-map-assets
   ```

## Notes

- **Integrity**: Packs are content-addressed by SHA-256 and protected by per-file inventory hashes. Existing packs are immutable; updates publish a new archive hash.
- **Licensing & provenance**: Underlying game assets belong to Jagex. See [`ASSET-NOTICES.md`](ASSET-NOTICES.md) for provenance and attribution notes.
