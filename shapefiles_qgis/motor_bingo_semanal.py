# -*- coding: utf-8 -*-
"""
Motor do "bingo" semanal — CONFIGURÁVEL.

Lê config_pesos.json e, para CADA semana, monta um índice composto ("bingo")
ponderado das camadas (ocorrências, Disque, fatores...) usando uma janela móvel,
e RECALCULA as zonas ótimas de atuação da FM (com alocação dos agentes).

Saídas (em distribuicao_fm/):
  - zonas_semanais.shp ........ zonas recalculadas por semana (animável no QGIS)
  - visualizacao_semanal.html . mapa animado: heatmap do bingo + zonas, por semana

Como adicionar uma nova camada de dados no futuro:
  1) gere o shapefile de pontos dela (em shapefiles_qgis/);
  2) acrescente uma entrada em LAYER_SPECS abaixo (arquivo, campo de data e de
     categoria, se é temporal);
  3) adicione o bloco de pesos correspondente em config_pesos.json.
"""
import os
import json
import math
import datetime as dt
from datetime import timedelta
from collections import defaultdict, Counter
import shapefile  # pyshp

BASE = os.path.dirname(os.path.abspath(__file__))
FM = os.path.join(BASE, "distribuicao_fm")
CONFIG = os.path.join(BASE, "config_pesos.json")

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)
RIO = dict(lat_min=-23.15, lat_max=-22.70, lon_min=-43.85, lon_max=-43.05)
ANO_MIN, ANO_MAX = 2020, 2024

# Plumbing de cada camada (onde está, como ler). Os PESOS ficam no JSON.
LAYER_SPECS = {
    "ocorrencias": dict(path="ocorrencias/ocorrencias", temporal=True,
                        date_field="data", date_fmts=["%d/%m/%Y", "%Y-%m-%d"],
                        cat_field="desc_delit", only_rio=False),
    "disque": dict(path="disk_denuncia/disk_denuncia", temporal=True,
                   date_field="dt_denun",
                   date_fmts=["%m/%d/%Y %H:%M:%S", "%m/%d/%Y"],
                   cat_field="tipo_pr", only_rio=True),
    "fatores": dict(path="fatores_urbanos/fatores_urbanos", temporal=False,
                    date_field=None, date_fmts=[],
                    cat_field="tp_ocorr", only_rio=False),
}


# --------------------------------------------------------------------------- #
# Helpers de grade
# --------------------------------------------------------------------------- #
def make_grid(grade_m):
    lat_ref = 22.9
    mlat = 110574.0
    mlon = 111320.0 * math.cos(math.radians(lat_ref))
    return grade_m / mlat, grade_m / mlon  # dlat, dlon


def cell_of(lon, lat, dlon, dlat):
    if not (RIO["lon_min"] <= lon <= RIO["lon_max"]
            and RIO["lat_min"] <= lat <= RIO["lat_max"]):
        return None
    return (int((lon - RIO["lon_min"]) / dlon),
            int((lat - RIO["lat_min"]) / dlat))


def cell_square(ix, iy, dlon, dlat):
    x0 = RIO["lon_min"] + ix * dlon
    y0 = RIO["lat_min"] + iy * dlat
    return [[x0, y0], [x0, y0 + dlat], [x0 + dlon, y0 + dlat],
            [x0 + dlon, y0], [x0, y0]]


def parse_date(txt, fmts):
    for f in fmts:
        try:
            return dt.datetime.strptime(txt, f).date()
        except ValueError:
            continue
    return None


def p_percentil(vals, p):
    if not vals:
        return 1.0
    sv = sorted(vals)
    return sv[min(len(sv) - 1, int(p / 100.0 * (len(sv) - 1)))] or 1.0


# --------------------------------------------------------------------------- #
# Carga das camadas
# --------------------------------------------------------------------------- #
def carregar_camada(nome, cfg_cam, dlon, dlat, week_index):
    """Devolve:
       - se temporal: dict {i_semana: {cell: peso_acumulado}} e contagem bruta/semana
       - se estático: dict {cell: peso_acumulado}
    """
    spec = LAYER_SPECS[nome]
    r = shapefile.Reader(os.path.join(BASE, spec["path"]), encoding="utf-8")
    cat_w = cfg_cam.get("pesos_categoria", {})
    cat_def = cfg_cam.get("peso_categoria_default", 1.0)
    cat_field = spec["cat_field"]

    if spec["temporal"]:
        por_semana = defaultdict(lambda: defaultdict(float))
        bruto = Counter()
        for s, rec in zip(r.iterShapes(), r.iterRecords()):
            if not s.points:
                continue
            if spec["only_rio"] and rec["dentro_rio"] != "S":
                continue
            d = parse_date((rec[spec["date_field"]] or "").strip(), spec["date_fmts"])
            if d is None or not (ANO_MIN <= d.year <= ANO_MAX):
                continue
            iso = d.isocalendar()
            i = week_index.get((iso[0], iso[1]))
            if i is None:
                continue
            c = cell_of(s.points[0][0], s.points[0][1], dlon, dlat)
            if c is None:
                continue
            w = cat_w.get((rec[cat_field] or "").strip(), cat_def)
            por_semana[i][c] += w
            bruto[i] += 1
        return por_semana, bruto
    else:
        estatico = defaultdict(float)
        for s, rec in zip(r.iterShapes(), r.iterRecords()):
            if not s.points:
                continue
            if spec["only_rio"] and rec["dentro_rio"] != "S":
                continue
            c = cell_of(s.points[0][0], s.points[0][1], dlon, dlat)
            if c is None:
                continue
            w = cat_w.get((rec[cat_field] or "").strip(), cat_def)
            estatico[c] += w
        return estatico, None


# --------------------------------------------------------------------------- #
# Geometria das zonas
# --------------------------------------------------------------------------- #
def convex_hull(points):
    pts = sorted(set(map(tuple, points)))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

    lo = []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def clusters_8viz(cells_set):
    visto = set()
    comps = []
    for cell in cells_set:
        if cell in visto:
            continue
        pilha = [cell]
        visto.add(cell)
        comp = []
        while pilha:
            ix, iy = pilha.pop()
            comp.append((ix, iy))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        v = (ix + dx, iy + dy)
                        if v in cells_set and v not in visto:
                            visto.add(v)
                            pilha.append(v)
        comps.append(comp)
    return comps


def zonas_da_semana(comp_cells, cfg, cell_bairro, n_agentes):
    """comp_cells: {cell: intensidade}. Devolve lista de zonas com geometria."""
    total = sum(comp_cells.values())
    if total <= 0:
        return []
    ordenadas = sorted(comp_cells.items(), key=lambda kv: kv[1], reverse=True)
    alvo = total * cfg["cobertura"]
    acc, hot = 0.0, set()
    for cell, v in ordenadas:
        if acc >= alvo:
            break
        hot.add(cell)
        acc += v

    zonas = []
    for comp in clusters_8viz(hot):
        score = sum(comp_cells.get(c, 0) for c in comp)
        if score < cfg["min_share_zona"] * total:
            continue
        zonas.append(dict(cells=comp, score=score))
    if not zonas:
        return []

    zonas.sort(key=lambda z: z["score"], reverse=True)
    soma = sum(z["score"] for z in zonas)
    brutos = [n_agentes * z["score"] / soma for z in zonas]
    base = [int(math.floor(b)) for b in brutos]
    for i in sorted(range(len(zonas)), key=lambda k: brutos[k]-base[k],
                    reverse=True)[:n_agentes - sum(base)]:
        base[i] += 1
    for i, z in enumerate(zonas):
        z["agentes"] = base[i]
        z["pct"] = 100.0 * z["score"] / total
        bairros = Counter()
        for c in z["cells"]:
            if c in cell_bairro:
                bairros.update(cell_bairro[c])
        z["local"] = bairros.most_common(1)[0][0] if bairros else "(s/ rótulo)"
    return zonas


def cell_bairro_map(dlon, dlat):
    cb = defaultdict(Counter)

    def add(path, campo, only_rio):
        r = shapefile.Reader(os.path.join(BASE, path), encoding="utf-8")
        for s, rec in zip(r.iterShapes(), r.iterRecords()):
            if only_rio and rec["dentro_rio"] != "S":
                continue
            if not s.points:
                continue
            c = cell_of(s.points[0][0], s.points[0][1], dlon, dlat)
            b = (rec[campo] or "").strip()
            if c and b:
                cb[c][b.title()] += 1

    add("disk_denuncia/disk_denuncia", "bairro", True)
    add("fatores_urbanos/fatores_urbanos", "bairro", False)
    return cb


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    dlat, dlon = make_grid(cfg["grade_m"])
    W = cfg["janela_semanas"]
    n_ag = cfg["n_agentes"]

    # Linha do tempo de semanas (segundas-feiras de 2020-W01 até fim de 2024)
    weeks = []
    week_index = {}
    d = dt.date.fromisocalendar(ANO_MIN, 1, 1)
    fim = dt.date(ANO_MAX, 12, 31)
    while d <= fim:
        iso = d.isocalendar()
        week_index[(iso[0], iso[1])] = len(weeks)
        weeks.append((iso[0], iso[1], d))
        d += timedelta(days=7)

    # Camadas ativas
    cams = {n: c for n, c in cfg["camadas"].items() if c.get("ativa", True)}
    temporais, estaticas, bruto_ocor = {}, {}, Counter()
    for nome, c in cams.items():
        if LAYER_SPECS[nome]["temporal"]:
            por_sem, bruto = carregar_camada(nome, c, dlon, dlat, week_index)
            temporais[nome] = por_sem
            if nome == "ocorrencias":
                bruto_ocor = bruto
        else:
            estaticas[nome] = carregar_camada(nome, c, dlon, dlat, week_index)[0]
    print(f"camadas ativas: temporais={list(temporais)} estaticas={list(estaticas)}")

    # Escala de normalizacao (p95) por camada — estavel no tempo
    p95 = {}
    for nome, por_sem in temporais.items():
        vals = []
        for i in range(len(weeks)):
            acc = defaultdict(float)
            for j in range(max(0, i - W + 1), i + 1):
                for c, v in por_sem.get(j, {}).items():
                    acc[c] += v
            vals.extend(acc.values())
        p95[nome] = p_percentil([v for v in vals if v > 0], 95)
    for nome, est in estaticas.items():
        p95[nome] = p_percentil([v for v in est.values() if v > 0], 95)
    print("escala p95 por camada:", {k: round(v, 2) for k, v in p95.items()})

    cell_bairro = cell_bairro_map(dlon, dlat)

    # Compõe o bingo por semana e recalcula zonas
    wz = shapefile.Writer(os.path.join(FM, "zonas_semanais"),
                          shapeType=shapefile.POLYGON, encoding="utf-8")
    wz.field("iso_ano", "N", 4)
    wz.field("iso_sem", "N", 2)
    wz.field("sem_ini", "D")
    wz.field("zona_id", "N", 4)
    wz.field("local", "C", 60)
    wz.field("agentes", "N", 5)
    wz.field("score", "N", 12, 4)
    wz.field("pct", "N", 7, 2)
    wz.field("n_cel", "N", 6)

    weeks_html = []
    heat_vals = []
    total_zonas = 0
    for i, (ano, sem, seg) in enumerate(weeks):
        composto = defaultdict(float)
        for nome, por_sem in temporais.items():
            esc = p95[nome]
            peso = cams[nome]["peso"]
            acc = defaultdict(float)
            for j in range(max(0, i - W + 1), i + 1):
                for c, v in por_sem.get(j, {}).items():
                    acc[c] += v
            for c, v in acc.items():
                composto[c] += peso * min(v / esc, 1.0)
        for nome, est in estaticas.items():
            esc = p95[nome]
            peso = cams[nome]["peso"]
            for c, v in est.items():
                composto[c] += peso * min(v / esc, 1.0)

        zonas = zonas_da_semana(composto, cfg, cell_bairro, n_ag)
        total_zonas += len(zonas)

        # heatmap (pontos) e zonas para o HTML — corta cauda ínfima p/ enxugar
        hp = [[ix, iy, round(val, 2)] for (ix, iy), val in composto.items()
              if val >= 0.10]
        heat_vals.extend(val for _, _, val in hp)
        z_html = []
        for zi, z in enumerate(zonas, 1):
            corners = []
            for (ix, iy) in z["cells"]:
                corners.extend(cell_square(ix, iy, dlon, dlat)[:4])
            hull = convex_hull(corners)
            ring = hull[::-1] + [hull[-1]]
            wz.poly([[list(p) for p in ring]])
            wz.record(ano, sem, seg, zi, z["local"], z["agentes"],
                      round(z["score"], 4), round(z["pct"], 2), len(z["cells"]))
            z_html.append({"l": z["local"], "a": z["agentes"],
                           "pct": round(z["pct"], 1),
                           "poly": [[round(y, 5), round(x, 5)] for x, y in hull]})
        weeks_html.append({"l": f"{ano}-S{sem:02d}", "d": seg.isoformat(),
                           "t": int(bruto_ocor.get(i, 0)),
                           "hp": hp, "z": z_html})
    wz.close()
    with open(os.path.join(FM, "zonas_semanais.prj"), "w", encoding="utf-8") as f:
        f.write(PRJ_WGS84)
    with open(os.path.join(FM, "zonas_semanais.cpg"), "w", encoding="utf-8") as f:
        f.write("UTF-8")

    heatmax = max(0.5, round(p_percentil([v for v in heat_vals if v > 0], 98), 2))
    grid = {"lon0": round(RIO["lon_min"], 8), "lat0": round(RIO["lat_min"], 8),
            "dlon": round(dlon, 8), "dlat": round(dlat, 8)}
    escrever_html(weeks_html, grid, heatmax, W)
    print(f"semanas={len(weeks)} zonas_total={total_zonas} heatmax={heatmax} "
          f"media_zonas/sem={total_zonas/len(weeks):.1f}")


def escrever_html(weeks, grid, heatmax, janela):
    out = os.path.join(FM, "visualizacao_semanal.html")
    html = HTML_TMPL
    html = html.replace("__GRID__", json.dumps(grid))
    html = html.replace("__WEEKS__", json.dumps(weeks, separators=(",", ":")))
    html = html.replace("__HEATMAX__", str(heatmax))
    html = html.replace("__JANELA__", str(janela))
    html = html.replace("__CENTER__", "[-22.93,-43.35]")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML -> {out} ({os.path.getsize(out)/1e6:.1f} MB)")


HTML_TMPL = r"""<!DOCTYPE html>
<html lang="pt-br"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>CompStat Rio — Bingo semanal + Zonas FM</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:Arial,Helvetica,sans-serif}
 #map{position:absolute;inset:0}
 #painel{position:absolute;z-index:1000;left:10px;top:10px;background:rgba(255,255,255,.95);
  padding:12px 14px;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);width:350px}
 #painel h1{font-size:14px;margin:0 0 4px}#painel .sub{font-size:11px;color:#666;margin-bottom:6px}
 #semana{font-size:20px;font-weight:bold;color:#b00}#total{font-size:12px;color:#444;margin-bottom:8px}
 #slider{width:100%}
 .ctr{display:flex;gap:6px;align-items:center;margin-top:6px}
 .ctr button{padding:5px 10px;border:0;border-radius:5px;background:#b00;color:#fff;cursor:pointer}
 .ctr button:hover{background:#900}.ctr select{padding:4px;border-radius:5px}
 .leg{position:absolute;z-index:1000;right:10px;bottom:18px;background:rgba(255,255,255,.95);
  padding:10px 12px;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:12px;max-width:240px}
 .barra{height:10px;border-radius:5px;background:linear-gradient(90deg,#3b3,#ff3,#f80,#f00);margin:4px 0}
 .zlbl{background:rgba(0,0,0,.65);color:#fff;border-radius:4px;padding:1px 5px;font-size:11px;font-weight:bold;white-space:nowrap}
</style></head><body>
<div id="map"></div>
<div id="painel">
 <h1>Bingo semanal &amp; zonas da FM</h1>
 <div class="sub">índice composto (janela de __JANELA__ semanas) — pesos em config_pesos.json</div>
 <div id="semana">--</div><div id="total">--</div>
 <input id="slider" type="range" min="0" max="0" value="0"/>
 <div class="ctr">
  <button id="play">► Play</button><button id="prev">◀</button><button id="next">▶</button>
  <label>vel.<select id="vel"><option value="500">lento</option><option value="250" selected>médio</option><option value="100">rápido</option></select></label>
 </div>
</div>
<div class="leg">
 <b>Índice bingo (semana)</b><div class="barra"></div>
 <div style="display:flex;justify-content:space-between"><span>menor</span><span>maior</span></div>
 <hr/><b>Zonas ótimas da FM</b><br/>Recalculadas a cada semana.<br/>Rótulo = bairro: nº de agentes.
</div>
<script>
const GRID=__GRID__, WEEKS=__WEEKS__, HEATMAX=__HEATMAX__, CENTER=__CENTER__;
const map=L.map('map').setView(CENTER,11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
let heat=L.heatLayer([],{radius:22,blur:18,minOpacity:.35,max:HEATMAX,
  gradient:{0.2:'#33aa33',0.45:'#ffff33',0.7:'#ff8800',1.0:'#ff0000'}}).addTo(map);
const zlayer=L.layerGroup().addTo(map);
function maxAg(z){return Math.max(1,...z.map(o=>o.a));}
function pts(i){return WEEKS[i].hp.map(([ix,iy,w])=>[GRID.lat0+(iy+0.5)*GRID.dlat,GRID.lon0+(ix+0.5)*GRID.dlon,w]);}
function desenha(i){
  heat.setLatLngs(pts(i));
  zlayer.clearLayers();
  const W=WEEKS[i], mx=maxAg(W.z);
  W.z.forEach(o=>{
    const t=o.a/mx, col=`rgb(200,${Math.round(120*(1-t))},${Math.round(120*(1-t))})`;
    const pl=L.polygon(o.poly,{color:'#700',weight:1.5,fillColor:col,fillOpacity:.18}).addTo(zlayer);
    pl.bindTooltip(`<b>${o.l}</b><br/>${o.pct}% do índice<br/><b>${o.a} agentes</b>`,{sticky:true});
    L.marker(pl.getBounds().getCenter(),{icon:L.divIcon({className:'',html:`<span class="zlbl">${o.l}: ${o.a}</span>`,iconSize:[0,0]})}).addTo(zlayer);
  });
  document.getElementById('semana').textContent='Semana '+W.l;
  document.getElementById('total').textContent=W.d+' — '+W.t+' ocorrências na semana | '+W.z.length+' zonas';
  document.getElementById('slider').value=i;
}
const sl=document.getElementById('slider'); sl.max=WEEKS.length-1;
sl.addEventListener('input',e=>desenha(+e.target.value));
let timer=null; const play=document.getElementById('play');
function toggle(){
  if(timer){clearInterval(timer);timer=null;play.textContent='► Play';return;}
  play.textContent='⏸ Pause';
  timer=setInterval(()=>{let i=(+sl.value+1)%WEEKS.length;desenha(i);},+document.getElementById('vel').value);
}
play.addEventListener('click',toggle);
document.getElementById('vel').addEventListener('change',()=>{if(timer){toggle();toggle();}});
document.getElementById('next').addEventListener('click',()=>desenha(Math.min(WEEKS.length-1,+sl.value+1)));
document.getElementById('prev').addEventListener('click',()=>desenha(Math.max(0,+sl.value-1)));
desenha(0);
</script></body></html>
"""


if __name__ == "__main__":
    main()
