import java.awt.image.BufferedImage;
import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import javax.imageio.ImageIO;
import net.runelite.cache.HighDetailMapImageDumper;
import net.runelite.cache.fs.Store;
import net.runelite.cache.region.Region;
import net.runelite.cache.region.RegionLoader;
import net.runelite.cache.util.XteaKeyManager;

/** Offline authoring tool. Renders native 8px/game-tile imagery, never enlarges zoom-2 images. */
public class RenderZoom3
{
	public static void main(String[] args) throws Exception
	{
		if (args.length < 3 || args.length > 4)
		{
			throw new IllegalArgumentException("Arguments: cache-directory key-file output-directory [region-id]");
		}
		Path output = Path.of(args[2]).toAbsolutePath();
		if (Files.exists(output))
		{
			throw new IllegalArgumentException("Output must be a new directory");
		}
		Files.createDirectories(output.resolve("0/3"));
		XteaKeyManager keys = new XteaKeyManager();
		try (FileInputStream in = new FileInputStream(args[1]))
		{
			keys.loadKeys(in);
		}
		int written = 0;
		try (Store store = new Store(Path.of(args[0]).toFile()))
		{
			store.load();
			RegionLoader loader = new RegionLoader(store, keys);
			loader.loadRegions();
			HighDetailMapImageDumper renderer = new HighDetailMapImageDumper(store, loader);
			renderer.setLabelRegions(false);
			renderer.setOutlineRegions(false);
			renderer.setRenderIcons(false);
			renderer.load();
			List<Region> regions = new ArrayList<>(loader.getRegions());
			regions.sort(Comparator.comparingInt(Region::getRegionID));
			int processed = 0;
			for (Region region : regions)
			{
				if (args.length == 4 && region.getRegionID() != Integer.parseInt(args[3]))
				{
					continue;
				}
				for (int plane = 0; plane < 4; plane++)
				{
					BufferedImage image = renderer.drawRegion(region, plane);
					if (image.getWidth() != 512 || image.getHeight() != 512)
					{
						throw new IllegalStateException("Renderer did not produce native zoom 3");
					}
					for (int x = 0; x < 2; x++)
					{
						for (int y = 0; y < 2; y++)
						{
							// Raster north is the top; world/tile Y increases northward.
							BufferedImage tile = image.getSubimage(x * 256, (1 - y) * 256, 256, 256);
							if (blank(tile))
							{
								continue;
							}
							Path path = output.resolve("0/3/" + plane + "_" + (region.getRegionX() * 2 + x)
								+ "_" + (region.getRegionY() * 2 + y) + ".png");
							ImageIO.write(tile, "png", path.toFile());
							written++;
						}
					}
				}
				if (++processed % 250 == 0)
				{
					System.out.printf("Rendered %d/%d regions; %d zoom-3 tiles%n", processed, regions.size(), written);
				}
			}
			System.out.printf("Finished: %d regions, %d native zoom-3 tiles%n", processed, written);
		}
	}

	private static boolean blank(BufferedImage image)
	{
		int[] pixels = image.getRGB(0, 0, 256, 256, null, 0, 256);
		for (int pixel : pixels)
		{
			if ((pixel & 0xffffff) != 0)
			{
				return false;
			}
		}
		return true;
	}
}
