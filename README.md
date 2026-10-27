# SafeBlock New Haven

Crash hot-spot ranking and safety cost estimates for New Haven, CT, built on real police-reported crash data.

## Pipeline
```
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
scripts/run_all.sh            # fetch -> network -> analyze -> build_map
python -m http.server 8765 -d web
pytest -q
```
1. `safeblock.fetch` pages the [UConn crash FeatureServer](https://gis.cti.uconn.edu/arcgis/rest/services/Crash_Dashboards/ConnecticutCrash/FeatureServer) (layer 0 Crash, layer 1 Person; 2,000 rows/request) for `CrashTownName='New Haven' AND CrashDateYear>=2019` and saves `data/raw/*.parquet`.
2. `safeblock.network` downloads the OSM drive network (OSMnx) as GraphML and GeoPackage.
3. `safeblock.analyze` snaps crashes to intersections within 30 m (street_count>=3; freeway interchange nodes are excluded) and fits an empirical-Bayes model. The exposure proxy is the sum of road-class weights for each incident street, since no traffic counts are used. Crash costs come from USDOT BCA Guidance 2025 Update II, Table A-1 (2023 $).
4. `safeblock.build_map` writes the Leaflet map `web/index.html` with the top 25.

## Fields used
CrashTownName, CrashDate, CrashDateYear, MostSevereInjury (KABCO), CrashSeverity, FirstHarmfulEvent, TypeOfIntersection; Person.PersonType (Pedestrian/Bicyclist/Other*).

## Caveats
- The 2019-2024 count from this source (40,463) is higher than the city's quoted "~33,000". The definitions differ, and we have not reconciled them yet.
- Costs apply one victim per crash at the crash's most severe injury, so this is a rough estimate.
- The exposure proxy is not traffic volume. Add AADT data (CTDOT) next.
