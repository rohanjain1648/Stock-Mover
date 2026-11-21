// From data/csv/area_managers.csv. GET /api/stores does not carry the area manager.
export interface AreaManager {
  id: string;
  name: string;
  city: string;
  stores: string[];
}

export const AREA_MANAGERS: AreaManager[] = [
  { id: "AM-01", name: "Rakesh Srivastava", city: "Lucknow", stores: ["LKO-01", "LKO-02", "LKO-03", "LKO-04"] },
  { id: "AM-02", name: "Alok Tiwari", city: "Kanpur", stores: ["KNP-01", "KNP-02", "KNP-03"] },
  { id: "AM-03", name: "Nitin Sinha", city: "Patna", stores: ["PAT-01", "PAT-02", "PAT-03", "PAT-04"] },
  { id: "AM-04", name: "Pankaj Jha", city: "Muzaffarpur", stores: ["MZF-01", "MZF-02"] },
  { id: "AM-05", name: "Harish Gowda", city: "Bengaluru", stores: ["BLR-01", "BLR-02", "BLR-03", "BLR-04", "BLR-05"] },
  { id: "AM-06", name: "Mahesh Shetty", city: "Mysuru", stores: ["MYS-01", "MYS-02"] },
];

const BY_STORE: Record<string, AreaManager> = Object.fromEntries(
  AREA_MANAGERS.flatMap((am) => am.stores.map((s) => [s, am] as const)),
);

export function amForStore(storeId: string): AreaManager | undefined {
  return BY_STORE[storeId];
}

export const WAREHOUSE_ID = "WH-KOL";
