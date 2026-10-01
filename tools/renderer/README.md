# Native zoom-3 renderer

`net/runelite/cache/HighDetailMapImageDumper.java` derives from RuneLite cache
1.12.39's `net/runelite/cache/MapImageDumper.java`. The upstream BSD-2-Clause
copyright and license notice is retained in the file.

Changes from upstream:

1. Rename the class to avoid replacing RuneLite's normal renderer.
2. Set `MAP_SCALE` to 8, generating 512×512 pixels per 64×64-game-tile region.
3. Use `1 / scale` for sprite sampling. Upstream's `2 - scale` becomes zero at 2×.
4. Start clipped sprite sampling at the clipped source offset, preserving region-edge objects.

`RenderZoom3.java` splits each native region into four 256×256 tiles. Tile Y increases
northward, while image rows increase downward. Terrain masks and wall lines are
rendered at the new resolution; existing zoom-2 bitmaps are not enlarged. Map-scene
sprites remain limited by the resolution of their original game artwork.

The rendering tool is offline and requires explicit local cache and key arguments.
Neither input is included in the public repository or generated pack. The plugin
never loads or executes these authoring tools.
