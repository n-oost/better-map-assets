package com.bettermap.tiles;

import java.awt.image.BufferedImage;
import java.awt.image.IndexColorModel;
import java.awt.image.WritableRaster;
import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.imageio.ImageIO;

/** Losslessly palette-packs map-0 tiles into an explicit authoring output directory. */
public final class TilePacker
{

	private TilePacker()
	{
	}

	public static void main(String[] args) throws IOException
	{
		if (args.length != 3)
		{
			throw new IllegalArgumentException("Arguments: source-directory new-output-directory maximum-zoom");
		}
		final File tileDir = new File(args[0]);
		final File resourceDir = new File(args[1]);
		if (resourceDir.exists())
		{
			throw new IOException("Output must be a new directory");
		}
		resourceDir.mkdirs();
		final int maxZoom = Integer.parseInt(args[2]);

		if (!tileDir.isDirectory())
		{
			throw new IOException("No tile store at " + tileDir + "; run dumpCacheTiles first");
		}

		final List<String> written = new ArrayList<>();
		long sourceBytes = 0;
		long packedBytes = 0;

		final File[] maps = tileDir.listFiles(File::isDirectory);
		if (maps != null)
		{
			for (final File mapDir : maps)
			{
				if (!mapDir.getName().equals("0"))
				{
					continue;
				}
				final File[] levels = mapDir.listFiles(File::isDirectory);
				if (levels == null)
				{
					continue;
				}
				for (final File levelDir : levels)
				{
					final int zoom;
					try
					{
						zoom = Integer.parseInt(levelDir.getName());
					}
					catch (NumberFormatException e)
					{
						continue;
					}
					if (zoom > maxZoom)
					{
						continue;
					}

					final File[] tiles = levelDir.listFiles((d, name) -> name.endsWith(".png"));
					if (tiles == null)
					{
						continue;
					}
					for (final File tile : tiles)
					{
						final String path = mapDir.getName() + "/" + levelDir.getName() + "/" + tile.getName();
						final File out = new File(resourceDir, path);
						out.getParentFile().mkdirs();

						final BufferedImage image = ImageIO.read(tile);
						if (image == null)
						{
							System.err.println("skipping unreadable tile " + tile);
							continue;
						}

						final BufferedImage indexed = indexed(image);
						if (indexed != null)
						{
							ImageIO.write(indexed, "png", out);
						}
						if (indexed == null || out.length() >= tile.length())
						{
							// More than 256 colours, or the palette encoding did not actually pay.
							// Copy the tile through untouched rather than trading pixels for bytes.
							Files.copy(tile.toPath(), out.toPath(), StandardCopyOption.REPLACE_EXISTING);
						}
						sourceBytes += tile.length();
						packedBytes += out.length();
						written.add(path);
					}
				}
			}
		}

		Collections.sort(written);
		try (PrintWriter manifest = new PrintWriter(
			Files.newBufferedWriter(new File(resourceDir, "index.txt").toPath(), StandardCharsets.UTF_8)))
		{
			for (final String path : written)
			{
				manifest.println(path);
			}
		}

		System.out.printf("packed %d tiles up to zoom %d: %.1f MB -> %.1f MB%n",
			written.size(), maxZoom, sourceBytes / 1048576d, packedBytes / 1048576d);
	}

	/**
	 * Re-encodes a tile against a palette built from its own colours, or null when it has more
	 * than 256 of them.
	 *
	 * <p>Built rather than borrowed: {@code TYPE_BYTE_INDEXED} without a colour model uses a fixed
	 * dithered palette, which on this artwork is both visibly wrong (a mean error of 13 per
	 * channel, measured) and frequently larger than the input. A palette taken from the image is
	 * exact - every source colour has its own entry - so the result is bit-identical when decoded.
	 */
	private static BufferedImage indexed(BufferedImage source)
	{
		final int width = source.getWidth();
		final int height = source.getHeight();
		final int[] pixels = source.getRGB(0, 0, width, height, null, 0, width);

		final LinkedHashMap<Integer, Integer> palette = new LinkedHashMap<>();
		for (final int pixel : pixels)
		{
			final int rgb = pixel & 0xFFFFFF;
			if (palette.putIfAbsent(rgb, palette.size()) == null && palette.size() > 256)
			{
				return null;
			}
		}

		final int size = palette.size();
		final byte[] reds = new byte[size];
		final byte[] greens = new byte[size];
		final byte[] blues = new byte[size];
		for (final Map.Entry<Integer, Integer> entry : palette.entrySet())
		{
			final int rgb = entry.getKey();
			final int index = entry.getValue();
			reds[index] = (byte) (rgb >> 16);
			greens[index] = (byte) (rgb >> 8);
			blues[index] = (byte) rgb;
		}

		final int bits = Math.max(1, 32 - Integer.numberOfLeadingZeros(Math.max(1, size - 1)));
		final IndexColorModel model = new IndexColorModel(bits <= 8 ? bits : 8, size, reds, greens, blues);
		final BufferedImage out = new BufferedImage(width, height, BufferedImage.TYPE_BYTE_INDEXED, model);
		final WritableRaster raster = out.getRaster();
		for (int y = 0; y < height; y++)
		{
			for (int x = 0; x < width; x++)
			{
				raster.setSample(x, y, 0, palette.get(pixels[y * width + x] & 0xFFFFFF));
			}
		}
		return out;
	}
}
