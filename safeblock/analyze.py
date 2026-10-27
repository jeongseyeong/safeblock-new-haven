"""Snap crashes to OSM intersections, compute empirical-Bayes risk and KABCO crash cost.

Exposure proxy (no traffic counts available): each intersection gets
  exposure = sum over incident road classes of a class weight (motorway/trunk 5,
  primary 4, secondary 3, tertiary 2, other 1)  -- i.e. a degree x road-class proxy.
Safety performance function (SPF): Poisson/NB mean mu = exp(b0 + b1*log(exposure)),
fit by Poisson GLM (IRLS); overdispersion alpha by method of moments.
EB estimate (Hauer / HSM): w = 1/(1+alpha*mu); EB = w*mu + (1-w)*observed.
Score = EB - mu ("excess expected crashes", per year).

Costs: USDOT BCA Guidance 2025 Update II (May 2025), Appendix A Table A-1, 2023 $.
https://www.transportation.gov/sites/dot.gov/files/2025-05/Benefit%20Cost%20Analysis%20Guidance%202025%20Update%20II%20%28Final%29.pdf
Applied per crash at its MostSevereInjury level (one victim per crash -> conservative);
O / no-injury crashes use the PDO crash value.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox

KABCO_COST = {"K": 13_200_000, "A": 1_254_700, "B": 246_900, "C": 118_000, "U": 229_800, "O": 9_500}
CLASS_W = {"motorway": 5, "trunk": 5, "primary": 4, "secondary": 3, "tertiary": 2}
SNAP_M = 30.0


def kabco(s) -> str:
    if not isinstance(s, str):
        return "U"
    for k in "KABCO":
        if s.strip().endswith(f"({k})"):
            return k
    return "U"


def class_weight(hw) -> int:
    hw = hw[0] if isinstance(hw, list) else hw
    hw = str(hw).replace("_link", "")
    return CLASS_W.get(hw, 1)


def eb(obs: np.ndarray, x: np.ndarray):
    """Fit log-linear Poisson SPF on log(x); return mu, alpha, EB."""
    X = np.column_stack([np.ones_like(x), np.log(x)])
    b = np.zeros(2); b[0] = np.log(obs.mean() + 1e-9)
    for _ in range(50):
        mu = np.exp(X @ b)
        b_new = b + np.linalg.solve(X.T @ (mu[:, None] * X), X.T @ (obs - mu))
        if np.max(np.abs(b_new - b)) < 1e-9:
            b = b_new; break
        b = b_new
    mu = np.exp(X @ b)
    alpha = max(((obs - mu) ** 2 - obs).sum() / (mu ** 2).sum(), 1e-6)
    w = 1 / (1 + alpha * mu)
    return mu, alpha, w * mu + (1 - w) * obs, b


def main(raw="data/raw", out="data/processed", years=(2019, 2025)):
    raw, out = Path(raw), Path(out); out.mkdir(parents=True, exist_ok=True)
    c = pd.read_parquet(raw / "crashes.parquet")
    c = c[c.CrashDateYear.between(*years)].copy()
    nyears = years[1] - years[0] + 1
    p = pd.read_parquet(raw / "nonmotorist_persons.parquet")
    ped_ids = set(p.loc[p.PersonType.str.contains("Pedestrian"), "CrashID"])
    bike_ids = set(p.loc[p.PersonType.str.contains("cycl", case=False), "CrashID"])
    c["kabco"] = c.MostSevereInjury.map(kabco)
    c["cost"] = c.kabco.map(KABCO_COST)
    c["ped"] = c.CrashID.isin(ped_ids); c["bike"] = c.CrashID.isin(bike_ids)
    c["ksi"] = c.kabco.isin(["K", "A"])

    G = ox.load_graphml(raw / "new_haven_drive.graphml")
    Gu = ox.convert.to_undirected(G)
    nodes, edges = ox.graph_to_gdfs(Gu)
    nodes = nodes[nodes.street_count >= 3].copy()
    edges = edges.reset_index()
    edges["w"] = edges.highway.map(class_weight)
    names = edges.assign(name=edges["name"].map(lambda n: n[0] if isinstance(n, list) else n))
    expo = pd.concat([edges[["u", "w"]].rename(columns={"u": "node"}), edges[["v", "w"]].rename(columns={"v": "node"})])
    # Exclude freeway interchange nodes (motorway / ramps): not urban intersections.
    is_mw = edges.highway.map(lambda h: any(str(x).startswith("motorway") for x in (h if isinstance(h, list) else [h])))
    mw_nodes = set(edges.loc[is_mw, "u"]) | set(edges.loc[is_mw, "v"])
    nodes = nodes[~nodes.index.isin(mw_nodes)].copy()
    nodes["exposure"] = expo.groupby("node").w.sum().reindex(nodes.index).fillna(1)
    nm = pd.concat([names[["u", "name"]].rename(columns={"u": "node"}), names[["v", "name"]].rename(columns={"v": "node"})]).dropna()
    nodes["label"] = nm.groupby("node").name.agg(lambda s: " & ".join(sorted(set(s))[:3])).reindex(nodes.index).fillna("(unnamed)")

    crs = nodes.estimate_utm_crs()
    ng = nodes.to_crs(crs)[["geometry"]].reset_index()
    cg = gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(c.lon, c.lat), crs=4326).to_crs(crs)
    j = gpd.sjoin_nearest(cg, ng, how="left", max_distance=SNAP_M, distance_col="snap_m")
    j = j[~j.index.duplicated()]
    c["node"] = j["osmid"].values
    c["snap_m"] = j["snap_m"].values
    snapped = c.dropna(subset=["node"])
    print(f"snapped {len(snapped)}/{len(c)} crashes ({len(snapped)/len(c):.1%}) to intersections within {SNAP_M} m")

    agg = snapped.groupby("node").agg(crashes=("CrashID", "size"), ksi=("ksi", "sum"), ped=("ped", "sum"),
                                     bike=("bike", "sum"), fatal=("kabco", lambda s: (s == "K").sum()), cost=("cost", "sum"))
    n = nodes.join(agg).fillna({"crashes": 0, "ksi": 0, "ped": 0, "bike": 0, "fatal": 0, "cost": 0})
    obs = n.crashes.values / nyears
    mu, alpha, ebv, b = eb(obs * nyears, n.exposure.values.astype(float))
    n["spf_per_yr"] = mu / nyears; n["eb_per_yr"] = ebv / nyears; n["excess_per_yr"] = n.eb_per_yr - n.spf_per_yr
    n["cost_per_yr"] = n.cost / nyears
    n = n.sort_values("excess_per_yr", ascending=False)
    n["rank"] = range(1, len(n) + 1)
    summary = {"excluded_motorway_nodes": len(mw_nodes), "years": list(years), "n_crashes": int(len(c)), "n_snapped": int(len(snapped)),
               "total_cost_per_yr_all": float(c.cost.sum() / nyears),
               "snapped_cost_per_yr": float(snapped.cost.sum() / nyears),
               "spf_coef": b.tolist(), "alpha": float(alpha), "n_intersections": int(len(n)),
               "kabco_counts": c.kabco.value_counts().to_dict()}
    cols = ["rank", "label", "crashes", "ksi", "fatal", "ped", "bike", "exposure", "spf_per_yr", "eb_per_yr", "excess_per_yr", "cost_per_yr", "x", "y"]
    n[cols].to_csv(out / "intersections_ranked.csv", index_label="osmid")
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return n[cols], summary


if __name__ == "__main__":
    main()
