import com.google.gson.GsonBuilder;
import java.io.File;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.runelite.cache.IndexType;
import net.runelite.cache.fs.Store;
import net.runelite.cache.region.RegionLoader;
import net.runelite.cache.util.XteaKeyManager;

/** Read-only developer audit: distinguishes empty regions from missing keys and decode errors. */
class AuditRegions
{
	public static void main(String[] args) throws Exception
	{
		if (args.length != 2)
		{
			throw new IllegalArgumentException("Arguments: cache-directory xtea-file (no keys are printed)");
		}
		XteaKeyManager keys = new XteaKeyManager();
		try (FileInputStream in = new FileInputStream(args[1]))
		{
			keys.loadKeys(in);
		}
		Map<String, List<Integer>> groups = new LinkedHashMap<>();
		for (String name : new String[]{"objectsDecoded", "emptyObjectsDecoded", "noLocationArchive", "missingKey", "locationDecodeError", "terrainDecodeError"})
		{
			groups.put(name, new ArrayList<>());
		}
		try (Store store = new Store(new File(args[0])))
		{
			store.load();
			RegionLoader loader = new RegionLoader(store, keys);
			for (int id = 0; id < 25287; id++)
			{
				try
				{
					if (loader.loadMapDef(id) == null)
					{
						continue;
					}
				}
				catch (Exception e)
				{
					groups.get("terrainDecodeError").add(id);
					continue;
				}
				if (store.getIndex(IndexType.MAPS).isNamed())
				{
					if (store.getIndex(IndexType.MAPS).findArchiveByName("l" + (id >> 8) + "_" + (id & 255)) == null)
					{
						groups.get("noLocationArchive").add(id);
						continue;
					}
					if (keys.getKey(id) == null)
					{
						groups.get("missingKey").add(id);
						continue;
					}
				}
				try
				{
					var locations = loader.loadLocDef(id);
					String category = locations == null ? "noLocationArchive"
						: locations.getLocations().isEmpty() ? "emptyObjectsDecoded" : "objectsDecoded";
					groups.get(category).add(id);
				}
				catch (Exception e)
				{
					groups.get("locationDecodeError").add(id);
				}
			}
		}
		Map<String, Object> report = new LinkedHashMap<>();
		Map<String, Integer> counts = new LinkedHashMap<>();
		groups.forEach((name, ids) -> counts.put(name, ids.size()));
		report.put("counts", counts);
		groups.remove("objectsDecoded");
		report.put("regionIds", groups);
		System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(report));
	}
}
