"""Build a static Leaflet web map (web/index.html) with the ranked top-25 list."""
import json
from pathlib import Path
import pandas as pd

def main(proc="data/processed", web="web", top=25):
    df = pd.read_csv(Path(proc) / "intersections_ranked.csv").head(top)
    s = json.loads((Path(proc) / "summary.json").read_text())
    rows = df[["rank","label","crashes","ksi","fatal","ped","bike","eb_per_yr","spf_per_yr","excess_per_yr","cost_per_yr","x","y"]].round(2).to_dict("records")
    html = TEMPLATE.replace("__DATA__", json.dumps(rows)).replace("__SUMMARY__", json.dumps(s))
    Path(web).mkdir(exist_ok=True); (Path(web) / "index.html").write_text(html)
    print(f"wrote {web}/index.html with {len(rows)} intersections")

TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SafeBlock New Haven</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>body{margin:0;font:13px system-ui,sans-serif;display:flex;height:100vh}#side{width:380px;overflow:auto;padding:10px;box-sizing:border-box}
#map{flex:1}table{border-collapse:collapse;width:100%}td,th{padding:3px;border-bottom:1px solid #ddd;text-align:right}td:nth-child(2),th:nth-child(2){text-align:left}
tr:hover{background:#fee;cursor:pointer}.note{color:#555;font-size:11px}@media(max-width:700px){body{flex-direction:column}#side{width:100%;height:45vh}}</style></head>
<body><div id="side"><h2 style="margin:4px 0">SafeBlock New Haven</h2><div id="sum"></div>
<table><thead><tr><th>#</th><th>Intersection</th><th>Crashes</th><th>KSI</th><th>Ped/Bike</th><th>Excess/yr</th><th>Cost/yr</th></tr></thead><tbody id="tb"></tbody></table>
<p class="note">Real data: UConn CT Crash Data Repository (police-reported crashes), snapped to OpenStreetMap intersections within 30 m.
Score = empirical-Bayes expected crashes/yr minus SPF prediction, where the SPF uses an exposure proxy (sum of road-class weights of incident streets) because no traffic counts are used.
Costs: USDOT BCA Guidance 2025 Update II, Table A-1 (2023 $), applied at each crash's most severe injury (one victim per crash), so they are rough.
KSI = killed or seriously injured.</p></div><div id="map"></div>
<script>const D=__DATA__,S=__SUMMARY__;const f=n=>'$'+(n/1e6).toFixed(2)+'M';
document.getElementById('sum').innerHTML=`${S.years[0]}–${S.years[1]}: ${S.n_crashes.toLocaleString()} crashes; ${S.n_snapped.toLocaleString()} snapped to intersections.<br>Estimated crash cost: <b>${f(S.total_cost_per_yr_all)}/yr</b> citywide (${f(S.snapped_cost_per_yr)}/yr at intersections).`;
const m=L.map('map').setView([41.305,-72.93],13);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(m);
const mk={};D.forEach(d=>{const c=L.circleMarker([d.y,d.x],{radius:5+d.excess_per_yr/2,color:'#b00',fillOpacity:.6}).addTo(m)
.bindPopup(`<b>#${d.rank} ${d.label}</b><br>${d.crashes} crashes (${d.ksi} KSI, ${d.fatal} fatal, ${d.ped} ped, ${d.bike} bike)<br>EB ${d.eb_per_yr}/yr vs expected ${d.spf_per_yr}/yr<br>Est. cost ${f(d.cost_per_yr)}/yr`);mk[d.rank]=c;
const r=document.createElement('tr');r.innerHTML=`<td>${d.rank}</td><td>${d.label}</td><td>${d.crashes}</td><td>${d.ksi}</td><td>${d.ped}/${d.bike}</td><td>${d.excess_per_yr.toFixed(1)}</td><td>${f(d.cost_per_yr)}</td>`;
r.onclick=()=>{m.setView([d.y,d.x],16);c.openPopup()};document.getElementById('tb').appendChild(r)});</script></body></html>"""

if __name__ == "__main__":
    main()
