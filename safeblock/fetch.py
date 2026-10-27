"""Page the UConn CT Crash Data Repository ArcGIS FeatureServer and save Parquet.

Layers (inspected 2026-10-23): 0=Crash, 1=Person, 2=Vehicle; maxRecordCount=2000.
Fields used: CrashTownName (town), CrashDate/CrashDateYear (date), CrashSeverity and
MostSevereInjury (KABCO severity), FirstHarmfulEvent (crash-level ped/bike flag),
Person.PersonType (Pedestrian / Bicyclist / Other Pedestrian / Other Cyclist).
"""
from __future__ import annotations
import argparse, time
from pathlib import Path
import pandas as pd
import requests

BASE = "https://gis.cti.uconn.edu/arcgis/rest/services/Crash_Dashboards/ConnecticutCrash/FeatureServer"
PAGE = 2000
NONMOTORIST_TYPES = ("Pedestrian", "Bicyclist", "Other Cyclist",
    "Other Pedestrian (wheelchair, person in a building, skater, pedestrian conveyance)")


def build_where(town: str, start_year: int) -> str:
    return f"CrashTownName='{town.replace(chr(39), chr(39)*2)}' AND CrashDateYear>={int(start_year)}"


def _get(url, params, tries=5):
    for i in range(tries):
        try:
            r = requests.post(url, data=params, timeout=120)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"])
            return d
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def count(layer: int, where: str) -> int:
    return _get(f"{BASE}/{layer}/query", {"where": where, "returnCountOnly": "true", "f": "json"})["count"]


def page_layer(layer: int, where: str, out_fields="*", geometry=True) -> pd.DataFrame:
    url, rows, offset = f"{BASE}/{layer}/query", [], 0
    while True:
        d = _get(url, {"where": where, "outFields": out_fields, "returnGeometry": str(geometry).lower(),
                       "outSR": 4326, "orderByFields": "OBJECTID", "resultOffset": offset,
                       "resultRecordCount": PAGE, "f": "json"})
        feats = d.get("features", [])
        for f in feats:
            a = dict(f["attributes"])
            g = f.get("geometry") or {}
            if geometry:
                a["lon"], a["lat"] = g.get("x"), g.get("y")
            rows.append(a)
        offset += len(feats)
        print(f"  layer {layer}: {offset} rows", flush=True)
        if not feats or not d.get("exceededTransferLimit", len(feats) == PAGE):
            break
    df = pd.DataFrame(rows)
    if "CrashDate" in df:
        df["CrashDate"] = pd.to_datetime(df["CrashDate"], unit="ms", utc=True)
    return df


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--town", default="New Haven")
    p.add_argument("--start-year", type=int, default=2019)
    p.add_argument("--out", default="data/raw")
    a = p.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    where = build_where(a.town, a.start_year)
    n = count(0, where)
    print(f"server count (crash layer): {n}")
    crashes = page_layer(0, where)
    assert len(crashes) == n, f"paged {len(crashes)} != server count {n}"
    crashes.to_parquet(out / "crashes.parquet", index=False)
    types = ",".join("'" + t + "'" for t in NONMOTORIST_TYPES)
    persons = page_layer(1, f"{where} AND PersonType IN ({types})", geometry=False)
    persons.to_parquet(out / "nonmotorist_persons.parquet", index=False)
    print(f"saved {len(crashes)} crashes, {len(persons)} non-motorist person rows")


if __name__ == "__main__":
    main()
