# Better Map assets

Private development snapshot for Better Map's automatic full-map download architecture.

This repository is separate from the plugin code. It contains complete imagery packs and a channel document; it does not contain player data, credentials, raw game caches, or XTEA keys. The plugin's installed-pack loader uses this channel when downloads are enabled. Anonymous production access still requires a public endpoint.

## Layout

- `packs/<sha256>.zip`: immutable complete imagery pack.
- `metadata/<sha256>.json`: size, source limitations, and publication information.
- `channels/tiles-v1.json`: compatibility channel referencing a commit-pinned pack.
- `tools/build_pack.py`: deterministic ZIP builder and verifier, using Python's standard library.

The ZIP contains `inventory.json`, `tiles/index.txt`, and PNG tiles. The inventory records every payload file's exact size/hash and coverage. The outer archive hash protects the inventory. Pack identity does not depend on repository owner or name.

## Generate a snapshot

First run the plugin project's existing `TilePacker.java` with an explicit temporary output directory and maximum zoom 2. Never direct this publication operation at plugin resources.

```text
java <plugin>/tools/src/main/java/com/bettermap/tiles/TilePacker.java <local-tile-root> <packed-output> 2
python tools/build_pack.py <packed-output> --source-manifest <local-tile-root>/manifest.json --plugin <plugin-root> --version <snapshot-version>
```

The builder deliberately does not publish absolute local paths or raw keys. Source files remain untouched. Its metadata records bundled-data hashes to identify the companion dataset snapshot, not to certify compatibility automatically.

Commit the pack/metadata first. Then create the channel with the resulting full commit SHA and metadata fields, and commit it separately. Never rewrite an existing pack. Verify the remote archive bytes against the published SHA-256 before considering publication successful.

With `gh` authenticated, verify the actual remote pack and every inventory entry:

```text
python tools/verify_remote.py n-oost/better-map-assets
```

This helper reads the channel through authenticated `gh` and retrieves the commit-pinned binary through a fresh Git clone. It is not runtime plugin code or a substitute for the final anonymous public-endpoint test.

## Current limitations

The input is the existing local tile collection, not a fresh complete game-cache render. The generation manifest's `regionsFailedToDecrypt: 426` is a mislabeled count of empty object lists. The 2026-09-27 audit decoded all 426 successfully, with no missing keys or decode errors in the available cache. See [the investigation](INVESTIGATION.md). Additional map IDs correspond to separate Wiki dungeon maps; exact file provenance still needs review. A full archive means all indexed snapshot files, not verified completeness of the game's map.

This repository is private by user request. Authenticated developer downloads can validate transfer/integrity, but normal Plugin Hub installations cannot fetch private assets anonymously. Do not embed GitHub tokens in the plugin. Production requires a public asset endpoint plus the Hub installation warning.

Before public release, verify provenance/licensing, coverage, companion-data compatibility, and clean-cache rendering. See `ASSET-NOTICES.md`.

## Repository migration

The plugin-code repository can move independently. Its eventual downloader should hold owner/repository/channel configuration in one place. If this asset repository moves, publish the same pack bytes at the new location and update the plugin endpoint plus channel commit reference. Content hashes allow installed packs to be reused; channel ETags must remain scoped to their URL.
