"""Download the New Haven drivable street graph with OSMnx; save GraphML + GeoPackage."""
from pathlib import Path
import osmnx as ox

PLACE = "New Haven, Connecticut, USA"


def main(out="data/raw"):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    G = ox.graph_from_place(PLACE, network_type="drive", simplify=True)
    ox.save_graphml(G, out / "new_haven_drive.graphml")
    ox.save_graph_geopackage(G, out / "new_haven_drive.gpkg")
    print(f"nodes={G.number_of_nodes()} edges={G.number_of_edges()}")


if __name__ == "__main__":
    main()
