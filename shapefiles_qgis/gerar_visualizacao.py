# -*- coding: utf-8 -*-
"""
Gera uma visualização HTML interativa (autocontida) que mostra:
  - o heatmap SEMANAL das ocorrências, com slider + botão play (efeito "gif");
  - as 8 zonas ótimas de atuação da FM sobrepostas (fixas).

Lê distribuicao_fm/heatmap_semanal.shp e zonas_recomendadas.shp e escreve
distribuicao_fm/visualizacao_semanal.html (abrir no navegador).

Usa Leaflet + Leaflet.heat via CDN (precisa de internet para o mapa base).
"""
import os
import json
import datetime as dt
import shapefile  # pyshp

BASE = os.path.dirname(os.path.abspath(__file__))
FM = os.path.join(BASE, "distribuicao_fm")

# Mesma grade da análise
RIO = dict(lat_min=-23.15, lon_min=-43.85)
import math
CELL_M = 250.0
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(22.9))
DLAT = CELL_M / M_PER_DEG_LAT
DLON = CELL_M / M_PER_DEG_LON


def carregar_semanas():
    r = shapefile.Reader(os.path.join(FM, "heatmap_semanal"), encoding="utf-8")
    semanas = {}      # (ano,sem) -> {'d':date,'pts':[[ix,iy,w]],'t':total}
    pesos = []
    for rec in r.iterRecords():
        ix, iy = map(int, rec["cell_id"].split("_"))
        ano, sem, n = rec["iso_ano"], rec["iso_sem"], rec["n_ocor"]
        d = rec["sem_ini"]
        ds = d.isoformat() if isinstance(d, dt.date) else str(d)
        key = (ano, sem)
        s = semanas.setdefault(key, {"d": ds, "pts": [], "t": 0})
        s["pts"].append([ix, iy, n])
        s["t"] += n
        pesos.append(n)
    # p98 dos pesos por célula-semana (intensidade do heat estável e vívida)
    pesos.sort()
    p98 = pesos[min(len(pesos) - 1, int(0.98 * len(pesos)))]
    ordenadas = sorted(semanas.items(), key=lambda kv: kv[1]["d"])
    weeks = []
    for (ano, sem), s in ordenadas:
        weeks.append({"l": f"{ano}-S{sem:02d}", "d": s["d"],
                      "t": s["t"], "p": s["pts"]})
    return weeks, p98


def carregar_zonas():
    r = shapefile.Reader(os.path.join(FM, "zonas_recomendadas"), encoding="utf-8")
    feats = []
    for shp, rec in zip(r.shapes(), r.records()):
        parts = list(shp.parts) + [len(shp.points)]
        rings = [[[round(x, 6), round(y, 6)] for x, y in shp.points[parts[i]:parts[i+1]]]
                 for i in range(len(parts) - 1)]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": rings},
            "properties": {
                "zona": rec["zona_id"], "local": rec["local"],
                "agentes": rec["agentes"], "ocor": rec["n_ocor"],
                "pct": rec["pct_crime"], "prio": rec["prioridade"],
            },
        })
    return {"type": "FeatureCollection", "features": feats}


HTML = r"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>CompStat Rio - Heatmap semanal + Zonas FM</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
  html,body{margin:0;height:100%;font-family:Arial,Helvetica,sans-serif}
  #map{position:absolute;top:0;bottom:0;left:0;right:0}
  #painel{position:absolute;z-index:1000;left:10px;top:10px;background:rgba(255,255,255,.95);
    padding:12px 14px;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);width:340px}
  #painel h1{font-size:15px;margin:0 0 6px}
  #semana{font-size:20px;font-weight:bold;color:#b00}
  #total{font-size:12px;color:#444;margin-bottom:8px}
  #slider{width:100%}
  .controles{display:flex;gap:6px;align-items:center;margin-top:6px}
  .controles button{padding:5px 10px;border:0;border-radius:5px;background:#b00;color:#fff;cursor:pointer;font-size:13px}
  .controles button:hover{background:#900}
  .controles select{padding:4px;border-radius:5px}
  .legenda{position:absolute;z-index:1000;right:10px;bottom:18px;background:rgba(255,255,255,.95);
    padding:10px 12px;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:12px;max-width:230px}
  .legenda b{font-size:12px}
  .barra{height:10px;border-radius:5px;background:linear-gradient(90deg,#3b3,#ff3,#f80,#f00);margin:4px 0}
  .zlbl{background:rgba(0,0,0,.6);color:#fff;border:0;border-radius:4px;padding:1px 5px;font-size:11px;font-weight:bold}
</style>
</head>
<body>
<div id="map"></div>
<div id="painel">
  <h1>Ocorrências por semana &amp; zonas da FM</h1>
  <div id="semana">--</div>
  <div id="total">--</div>
  <input id="slider" type="range" min="0" max="0" value="0"/>
  <div class="controles">
    <button id="btnPlay">► Play</button>
    <button id="btnPrev">◀</button>
    <button id="btnNext">▶</button>
    <label>vel.
      <select id="vel">
        <option value="400">lento</option>
        <option value="200" selected>médio</option>
        <option value="80">rápido</option>
      </select>
    </label>
  </div>
</div>
<div class="legenda">
  <b>Mancha criminal (semana)</b>
  <div class="barra"></div>
  <div style="display:flex;justify-content:space-between"><span>menos</span><span>mais</span></div>
  <hr/>
  <b>Zonas ótimas da FM</b><br/>
  Polígonos vermelhos = onde a Força deve atuar.<br/>
  Passe o mouse para ver bairro e nº de agentes.
</div>

<script>
const GRID = __GRID__;
const WEEKS = __WEEKS__;
const HEATMAX = __HEATMAX__;
const ZONES = __ZONES__;
const CENTER = __CENTER__;

const map = L.map('map').setView(CENTER, 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19, attribution:'© OpenStreetMap'}).addTo(map);

// Zonas ótimas (fixas)
const maxAg = Math.max(...ZONES.features.map(f=>f.properties.agentes));
function corZona(ag){
  const t = ag/maxAg;                       // 0..1
  const r = 200, g = Math.round(120*(1-t)), b = Math.round(120*(1-t));
  return `rgb(${r},${g},${b})`;
}
L.geoJSON(ZONES, {
  style: f => ({color:'#700', weight:1.5, fillColor:corZona(f.properties.agentes), fillOpacity:.18}),
  onEachFeature: (f,l)=>{
    const p=f.properties;
    l.bindTooltip(`<b>${p.local}</b><br/>prioridade ${p.prio}<br/>${p.ocor} ocorrências (${p.pct}%)<br/><b>${p.agentes} agentes</b>`,{sticky:true});
    const c=l.getBounds().getCenter();
    L.marker(c,{icon:L.divIcon({className:'',html:`<span class="zlbl">${p.local}: ${p.agentes}</span>`,iconSize:[0,0]})}).addTo(map);
  }
}).addTo(map);

// Heatmap semanal
let heat = L.heatLayer([], {radius:22, blur:18, minOpacity:.35, max:HEATMAX,
  gradient:{0.2:'#33aa33',0.45:'#ffff33',0.7:'#ff8800',1.0:'#ff0000'}}).addTo(map);

function pontosSemana(i){
  return WEEKS[i].p.map(([ix,iy,w])=>[
    GRID.lat0 + (iy+0.5)*GRID.dlat,
    GRID.lon0 + (ix+0.5)*GRID.dlon,
    w
  ]);
}
function mostrar(i){
  heat.setLatLngs(pontosSemana(i));
  document.getElementById('semana').textContent = 'Semana ' + WEEKS[i].l;
  document.getElementById('total').textContent = WEEKS[i].d + ' — ' + WEEKS[i].t + ' ocorrências na semana';
  document.getElementById('slider').value = i;
}

const slider = document.getElementById('slider');
slider.max = WEEKS.length - 1;
slider.addEventListener('input', e => mostrar(+e.target.value));

let timer=null, idx=0;
function step(){ idx=(idx+1)%WEEKS.length; mostrar(idx); }
const btnPlay=document.getElementById('btnPlay');
function play(){
  if(timer){clearInterval(timer);timer=null;btnPlay.textContent='► Play';return;}
  btnPlay.textContent='⏸ Pause';
  const vel=+document.getElementById('vel').value;
  timer=setInterval(()=>{ idx=+slider.value; step(); }, vel);
}
btnPlay.addEventListener('click', play);
document.getElementById('vel').addEventListener('change',()=>{ if(timer){play();play();} });
document.getElementById('btnNext').addEventListener('click',()=>{ idx=Math.min(WEEKS.length-1,+slider.value+1); mostrar(idx); });
document.getElementById('btnPrev').addEventListener('click',()=>{ idx=Math.max(0,+slider.value-1); mostrar(idx); });

mostrar(0);
</script>
</body>
</html>
"""


def main():
    weeks, p98 = carregar_semanas()
    zones = carregar_zonas()
    grid = {"lon0": round(RIO["lon_min"], 8), "lat0": round(RIO["lat_min"], 8),
            "dlon": round(DLON, 8), "dlat": round(DLAT, 8)}
    # 'max' do heat baseado na p98 (a grande maioria das células tem 1-3/semana)
    heatmax = max(3, int(p98) + 1)
    center = [-22.93, -43.35]

    html = (HTML
            .replace("__GRID__", json.dumps(grid))
            .replace("__WEEKS__", json.dumps(weeks, separators=(",", ":")))
            .replace("__HEATMAX__", str(heatmax))
            .replace("__ZONES__", json.dumps(zones, separators=(",", ":")))
            .replace("__CENTER__", json.dumps(center)))

    out = os.path.join(FM, "visualizacao_semanal.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    mb = os.path.getsize(out) / 1e6
    print(f"OK -> {out}")
    print(f"semanas={len(weeks)} heatmax={heatmax} "
          f"zonas={len(zones['features'])} tamanho={mb:.1f} MB")


if __name__ == "__main__":
    main()
