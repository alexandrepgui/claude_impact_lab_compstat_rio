# -*- coding: utf-8 -*-
"""
Motor de zonas v3 — **unidade atômica = logradouros principais** (Arteriais).

Substitui o motor_bingo_semanal (que usava grade 250m + convex hull) por
uma versão onde:

  1) Score é calculado **por logradouro**, não por célula:
     para cada Arterial dentro do recorte, soma os pesos dos pontos
     (ocorrências, denúncias do Disque, fatores urbanos) que caem
     dentro de um buffer de 50 m do logradouro.
     Camadas temporais usam janela móvel de W semanas.

  2) Top-K logradouros por score → buffer + unary_union → clusters.

  3) Top-N clusters por score interno (N=8 default, como sh_area_forca)
     → closing morfológico + simplify → polígonos finais.

  4) Os 600 agentes são alocados proporcionalmente ao score do cluster.

Saída: distribuicao_fm/zonas_semanais.shp (substitui o do motor v2).

Polígonos resultantes têm áreas comparáveis às do `sh_area_forca`
(~0,3-1,7 km²) e bordas em ruas reais.

Uso:
    python motor_logradouros.py                     # só a última semana
    python motor_logradouros.py --todas-semanas     # 262 semanas (~horas)
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
import sys
from collections import defaultdict, Counter
from datetime import timedelta
from pathlib import Path

import shapefile
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely import make_valid

BASE = Path(__file__).resolve().parent
FM = BASE / "distribuicao_fm"
CONFIG = BASE / "config_pesos.json"
LOGR = BASE.parent / "dados_externo" / "Logradouros" / "Logradouros"
OUT_SHP = FM / "zonas_semanais"

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

RIO = dict(lat_min=-23.15, lat_max=-22.70, lon_min=-43.85, lon_max=-43.05)
ANO_MIN, ANO_MAX = 2020, 2024

# Grade do heatmap (lat/lon) — mesmo passo que o motor antigo (250 m)
GRADE_M = 250
LAT_REF = -22.9
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(abs(LAT_REF)))
DLAT_HEAT = GRADE_M / M_PER_DEG_LAT
DLON_HEAT = GRADE_M / M_PER_DEG_LON

# Buffer ao redor do logradouro para coletar pontos
BUFFER_PONTOS_M = 100
# Buffer ao redor do logradouro selecionado para formar o polígono final
# 200m → cobre 1-2 quadras laterais de cada lado da arterial
BUFFER_ZONA_M = 200
# Closing morfológico para conectar arteriais próximas
CLOSING_M = 250
# Tolerância simplify (m)
SIMPLIFY_M = 25
# K candidatos antes de agrupar (mais alto → clusters mais ricos)
TOP_K_LOGRADOUROS = 400
# Hierarquias consideradas
HIERARQUIAS = ("Arterial primária", "Arterial secundária")

LAYER_SPECS = {
    "ocorrencias": dict(path="ocorrencias/ocorrencias", encoding="utf-8",
                        temporal=True, date_field="data",
                        date_fmts=["%d/%m/%Y", "%Y-%m-%d"],
                        cat_field="desc_delit", only_rio=False),
    "disque": dict(path="disk_denuncia/disk_denuncia", encoding="latin-1",
                   temporal=True, date_field="dt_denun",
                   date_fmts=["%m/%d/%Y %H:%M:%S", "%m/%d/%Y"],
                   cat_field="tipo_pr", only_rio=True),
    "fatores": dict(path="fatores_urbanos/fatores_urbanos", encoding="latin-1",
                    temporal=False, date_field=None, date_fmts=[],
                    cat_field="tp_ocorr", only_rio=False),
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse_date(txt, fmts):
    for f in fmts:
        try:
            return dt.datetime.strptime(txt, f).date()
        except ValueError:
            continue
    return None


def fix_mojibake(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def carregar_logradouros(to_utm):
    """Devolve lista [(LineString_utm, nome, hierarquia)]."""
    print("Carregando logradouros principais...")
    r = shapefile.Reader(str(LOGR), encoding="utf-8")
    field_names = [f[0] for f in r.fields[1:]]
    idx_hier = field_names.index("hierarquia")
    idx_nome = field_names.index("completo")
    hier_set = set(HIERARQUIAS)
    out = []
    for i in range(len(r)):
        s = r.shape(i)
        if len(s.points) < 2:
            continue
        rec = r.record(i)
        h = (rec[idx_hier] or "").strip()
        if h not in hier_set:
            continue
        # filtra grosso por bbox do RIO em UTM
        pts = s.points
        if len(s.parts) <= 1:
            out.append((LineString(pts), rec[idx_nome] or "", h))
        else:
            parts = list(s.parts) + [len(pts)]
            for k in range(len(parts) - 1):
                seg = pts[parts[k]:parts[k+1]]
                if len(seg) >= 2:
                    out.append((LineString(seg), rec[idx_nome] or "", h))
    print(f"  {len(out)} segmentos de Arteriais (todas as hierarquias).")
    return out


def carregar_pontos(layer_name, cfg_cam, to_utm):
    """Devolve [(x_utm, y_utm, lon, lat, peso, data)] para a camada."""
    spec = LAYER_SPECS[layer_name]
    r = shapefile.Reader(str(BASE / spec["path"]), encoding=spec["encoding"])
    field_names = [f[0] for f in r.fields[1:]]
    cat_w = cfg_cam.get("pesos_categoria", {})
    cat_def = cfg_cam.get("peso_categoria_default", 1.0)
    cat_field = cfg_cam["campo_categoria"]
    out = []
    for s, rec in zip(r.iterShapes(), r.iterRecords()):
        if not s.points:
            continue
        if spec["only_rio"] and rec["dentro_rio"] != "S":
            continue
        lon, lat = s.points[0]
        if not (RIO["lon_min"] <= lon <= RIO["lon_max"]
                and RIO["lat_min"] <= lat <= RIO["lat_max"]):
            continue
        cat = fix_mojibake((rec[cat_field] or "").strip())
        peso = cat_w.get(cat, cat_def)
        data = None
        if spec["temporal"]:
            data = parse_date((rec[spec["date_field"]] or "").strip(),
                              spec["date_fmts"])
            if data is None or not (ANO_MIN <= data.year <= ANO_MAX):
                continue
        x, y = to_utm.transform(lon, lat)
        out.append((x, y, lon, lat, peso, data))
    return out


def construir_zonas_para_semana(logradouros, scores_logr, n_zonas,
                                 buffer_zona_m, closing_m, simplify_m):
    """Pega top-K logradouros por score, faz buffer+union, ranqueia clusters
    pelo score interno e devolve top-N clusters como polígonos."""
    # ordena logradouros por score desc
    ranked = sorted(
        ((idx, sc) for idx, sc in scores_logr.items() if sc > 0),
        key=lambda x: x[1], reverse=True
    )
    if not ranked:
        return []
    cands = ranked[:TOP_K_LOGRADOUROS]
    # buffer de cada um
    bufs_with_score = [
        (logradouros[idx][0].buffer(buffer_zona_m, cap_style=2,
                                     join_style=2, mitre_limit=2.0),
         sc, idx)
        for idx, sc in cands
    ]
    union = unary_union([b for b, _, _ in bufs_with_score])
    if not union.is_valid:
        union = make_valid(union)
    # extrair componentes
    if union.geom_type == "MultiPolygon":
        components = list(union.geoms)
    elif union.geom_type == "Polygon":
        components = [union]
    else:
        return []

    # score por componente: soma scores dos logradouros cujo buffer está
    # majoritariamente dentro do componente
    comp_score = []
    for c in components:
        s_total = 0.0
        for b, sc, idx in bufs_with_score:
            try:
                if c.intersects(b):
                    inter = c.intersection(b).area
                    if inter / b.area > 0.5:
                        s_total += sc
            except Exception:
                continue
        comp_score.append((c, s_total))

    # top-N por score
    comp_score.sort(key=lambda x: x[1], reverse=True)
    sel = comp_score[:n_zonas]
    # closing + simplify final
    final = []
    for c, sc in sel:
        if closing_m > 0:
            c2 = c.buffer(closing_m, cap_style=2, join_style=2,
                          mitre_limit=2.0)
            c2 = c2.buffer(-closing_m, cap_style=2, join_style=2,
                           mitre_limit=2.0)
            if not c2.is_empty and c2.is_valid:
                c = c2
        if simplify_m > 0:
            c = c.simplify(simplify_m, preserve_topology=True)
        # tampa buracos
        if c.geom_type == "Polygon" and c.interiors:
            c = Polygon(c.exterior.coords)
        elif c.geom_type == "MultiPolygon":
            c = unary_union([Polygon(p.exterior.coords) for p in c.geoms])
        if not c.is_valid:
            c = make_valid(c)
        final.append((c, sc))
    return final


def alocar_agentes(scores, n_total):
    """Devolve lista de agentes inteiros somando n_total."""
    soma = sum(scores)
    if soma <= 0:
        return [0] * len(scores)
    brutos = [n_total * s / soma for s in scores]
    base = [int(math.floor(b)) for b in brutos]
    resto = n_total - sum(base)
    ordem = sorted(range(len(scores)),
                   key=lambda i: brutos[i] - base[i], reverse=True)
    for i in ordem[:resto]:
        base[i] += 1
    return base


def bairro_dominante(geom_utm, cell_bairro_index, to_wgs):
    """Estima o bairro dominante via centróide reprojetado."""
    cx, cy = geom_utm.centroid.x, geom_utm.centroid.y
    lon, lat = to_wgs.transform(cx, cy)
    # busca grossa por proximidade nos shapes de bairro indexados
    # (não temos shapefile de bairro aqui; usa rótulo embutido nas camadas)
    return None  # rótulo será preenchido pelo nome do logradouro top


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todas-semanas", action="store_true",
                    help="Roda em TODAS as 262 semanas (caro).")
    ap.add_argument("--n-zonas", type=int, default=8,
                    help="Número de zonas a manter por semana. Default 8.")
    args = ap.parse_args()

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    W = cfg["janela_semanas"]
    n_ag = cfg["n_agentes"]
    cams = {n: c for n, c in cfg["camadas"].items() if c.get("ativa", True)}

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:31983", "EPSG:4326", always_xy=True)

    # 1) Logradouros
    logradouros = carregar_logradouros(to_utm)
    # STRtree dos buffers para query rápida de pontos
    print(f"Construindo STRtree (buffer {BUFFER_PONTOS_M}m)...")
    logr_buffs = [ls.buffer(BUFFER_PONTOS_M) for ls, _, _ in logradouros]
    tree = STRtree(logr_buffs)

    # 2) Pontos: lê todas as camadas (UTM, com peso e data)
    pontos_por_camada = {}
    print("Carregando pontos das camadas...")
    for nome, cfg_cam in cams.items():
        pontos_por_camada[nome] = carregar_pontos(nome, cfg_cam, to_utm)
        print(f"  {nome}: {len(pontos_por_camada[nome])} pontos")

    # 3) Atribui cada ponto ao logradouro mais próximo dentro do buffer.
    #    Estrutura: por_semana[(ano,sem)][logr_idx] += peso * peso_camada
    #    (camadas estáticas vão num bucket especial "static")
    print("Atribuindo pontos a logradouros...")
    score_temporal = defaultdict(lambda: defaultdict(float))  # (ano,sem) → idx → score
    score_estatico = defaultdict(float)                       # idx → score
    week_index = {}
    weeks = []
    d = dt.date.fromisocalendar(ANO_MIN, 1, 1)
    fim = dt.date(ANO_MAX, 12, 31)
    while d <= fim:
        iso = d.isocalendar()
        week_index[(iso[0], iso[1])] = len(weeks)
        weeks.append((iso[0], iso[1], d))
        d += timedelta(days=7)

    # heat_temporal[(ano,sem)][(ix,iy)] = score acumulado da célula
    heat_temporal = defaultdict(lambda: defaultdict(float))
    heat_estatico = defaultdict(float)

    for nome, pts in pontos_por_camada.items():
        peso_camada = cams[nome]["peso"]
        spec = LAYER_SPECS[nome]
        for x, y, lon, lat, peso, data in pts:
            p = Point(x, y)
            idxs = tree.query(p)
            hits = [int(i) for i in idxs if logr_buffs[int(i)].contains(p)]
            # Score por logradouro (mesma lógica de antes)
            if hits:
                share = (peso * peso_camada) / len(hits)
                if spec["temporal"]:
                    iso = data.isocalendar()
                    key = (iso[0], iso[1])
                    bucket = score_temporal[key]
                    for i in hits:
                        bucket[i] += share
                else:
                    for i in hits:
                        score_estatico[i] += share
            # Heatmap por célula 250 m (todos os pontos contribuem, não só
            # os perto de Arteriais)
            cell = (int((lon - RIO["lon_min"]) / DLON_HEAT),
                    int((lat - RIO["lat_min"]) / DLAT_HEAT))
            v = peso * peso_camada
            if spec["temporal"]:
                iso = data.isocalendar()
                heat_temporal[(iso[0], iso[1])][cell] += v
            else:
                heat_estatico[cell] += v
    print(f"  semanas com sinal: {len(score_temporal)}")

    # 4) Para cada semana selecionada: compõe score (janela móvel) e gera zonas
    if args.todas_semanas:
        semanas_alvo = list(week_index.keys())
    else:
        semanas_com_dado = sorted(score_temporal.keys())
        semanas_alvo = [semanas_com_dado[-1]] if semanas_com_dado else []
    print(f"Processando {len(semanas_alvo)} semana(s)...")

    # Writer (substitui o atual)
    w = shapefile.Writer(str(OUT_SHP), shapeType=shapefile.POLYGON,
                         encoding="utf-8")
    w.field("iso_ano", "N", 4)
    w.field("iso_sem", "N", 2)
    w.field("sem_ini", "D")
    w.field("zona_id", "N", 4)
    w.field("local", "C", 80)
    w.field("agentes", "N", 5)
    w.field("score", "N", 14, 4)
    w.field("pct", "N", 7, 2)
    w.field("n_cel", "N", 6)  # mantém schema; aqui = #logradouros usados (não usamos cells)

    # Pré-calcula p95 do heat (estabilizador do gradiente)
    print("Calculando escala do heatmap (p95)...")
    heat_amostra = []
    for sem in (semanas_alvo if len(semanas_alvo) <= 5 else semanas_alvo[::20]):
        idx_s = week_index[sem]
        compor = defaultdict(float)
        for j in range(max(0, idx_s - W + 1), idx_s + 1):
            wk = (weeks[j][0], weeks[j][1])
            for c, v in heat_temporal.get(wk, {}).items():
                compor[c] += v
        for c, v in heat_estatico.items():
            compor[c] += v
        heat_amostra.extend(v for v in compor.values() if v > 0)
    heat_amostra.sort()
    heatmax = heat_amostra[int(0.95 * (len(heat_amostra) - 1))] if heat_amostra else 1.0
    print(f"  heatmax (p95) = {heatmax:.2f}")

    total_features = 0
    weeks_html = []
    for semana in semanas_alvo:
        ano, isem = semana
        idx_sem = week_index[semana]
        seg = weeks[idx_sem][2]

        # score composto: temporais somam janela móvel + estáticos sempre
        scores = defaultdict(float)
        for j in range(max(0, idx_sem - W + 1), idx_sem + 1):
            wk = (weeks[j][0], weeks[j][1])
            for i, sc in score_temporal.get(wk, {}).items():
                scores[i] += sc
        for i, sc in score_estatico.items():
            scores[i] += sc

        zonas = construir_zonas_para_semana(
            logradouros, scores, args.n_zonas,
            BUFFER_ZONA_M, CLOSING_M, SIMPLIFY_M,
        )
        if not zonas:
            continue

        scores_clusters = [s for _, s in zonas]
        agentes = alocar_agentes(scores_clusters, n_ag)
        total_score = sum(scores_clusters)
        zonas_html_semana = []

        for zi, ((g_utm, sc), ag) in enumerate(zip(zonas, agentes), 1):
            # rótulo: logradouro top dentro do cluster
            best_name = ""; best_sc = 0
            for idx_log, score_log in scores.items():
                if score_log <= best_sc:
                    continue
                logr_geom = logradouros[idx_log][0]
                if g_utm.intersects(logr_geom):
                    best_sc = score_log
                    best_name = logradouros[idx_log][1]
            # reproject geom para WGS84
            if g_utm.geom_type == "Polygon":
                ring_wgs = [to_wgs.transform(x, y)
                            for x, y in g_utm.exterior.coords]
                rings = [ring_wgs]
                polys_extra = []
            else:
                rings = []
                polys_extra = list(g_utm.geoms)
                for pp in polys_extra:
                    rings.append([to_wgs.transform(x, y)
                                  for x, y in pp.exterior.coords])
            # primeiro polígono: feature normal
            primary = rings[0]
            # se houver mais polígonos (multi), grava como features extras
            # com mesmo zona_id (parts)
            pct = 100.0 * sc / total_score if total_score > 0 else 0.0
            n_logr = sum(1 for i in scores if scores[i] > 0
                         and g_utm.intersects(logradouros[i][0]))

            # garantir anel horário (ESRI)
            def horario(ring):
                a = 0.0
                for i in range(len(ring) - 1):
                    x1, y1 = ring[i]
                    x2, y2 = ring[i + 1]
                    a += x1 * y2 - x2 * y1
                return ring if a < 0 else ring[::-1]

            primary_h = [list(p) for p in horario(primary)]
            parts = [primary_h]
            if g_utm.geom_type == "MultiPolygon":
                for extra in rings[1:]:
                    parts.append([list(p) for p in horario(extra)])
            w.poly(parts)
            w.record(ano, isem, seg, zi, best_name, ag,
                     round(sc, 4), round(pct, 2), n_logr)
            total_features += 1

            # acumula para HTML (cada zona pode ter múltiplos polígonos)
            html_poly = []
            for ring in parts:
                # ring no shapefile é [lon, lat] horário; Leaflet quer [lat, lon]
                html_poly.append([[round(p[1], 6), round(p[0], 6)]
                                  for p in ring])
            zonas_html_semana.append({
                "l": best_name or f"Zona {zi}",
                "a": ag,
                "pct": round(pct, 2),
                "poly": html_poly,
            })

        # heat da semana (janela móvel para temporais + estáticos)
        heat_sem = defaultdict(float)
        for j in range(max(0, idx_sem - W + 1), idx_sem + 1):
            wk = (weeks[j][0], weeks[j][1])
            for c, v in heat_temporal.get(wk, {}).items():
                heat_sem[c] += v
        for c, v in heat_estatico.items():
            heat_sem[c] += v
        # Limiar pra cortar cauda (mantém HTML leve)
        thr = 0.10 * heatmax
        hp = [[ix, iy, round(v, 2)] for (ix, iy), v in heat_sem.items()
              if v >= thr]

        weeks_html.append({
            "l": f"{ano}-S{isem:02d}",
            "d": seg.isoformat(),
            "z": zonas_html_semana,
            "hp": hp,
        })

    w.close()
    with open(str(OUT_SHP) + ".prj", "w", encoding="utf-8") as f:
        f.write(PRJ_WGS84)
    with open(str(OUT_SHP) + ".cpg", "w", encoding="utf-8") as f:
        f.write("UTF-8")
    print(f"Total features escritas: {total_features}")
    print(f"-> {OUT_SHP}.shp")

    # HTML interativo
    grid = {
        "lon0": round(RIO["lon_min"], 8),
        "lat0": round(RIO["lat_min"], 8),
        "dlon": round(DLON_HEAT, 8),
        "dlat": round(DLAT_HEAT, 8),
    }
    escrever_html(weeks_html, W, grid, heatmax)


HTML_TMPL = r"""<!DOCTYPE html>
<html lang="pt-br"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>CompStat Rio — Zonas FM (logradouros)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:Arial,Helvetica,sans-serif}
 #map{position:absolute;inset:0}
 #painel{position:absolute;z-index:1000;left:10px;top:10px;background:rgba(255,255,255,.96);
  padding:12px 14px;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);width:360px}
 #painel h1{font-size:14px;margin:0 0 4px}#painel .sub{font-size:11px;color:#666;margin-bottom:6px}
 #semana{font-size:20px;font-weight:bold;color:#b00}
 #total{font-size:12px;color:#444;margin-bottom:8px}
 #slider{width:100%}
 .ctr{display:flex;gap:6px;align-items:center;margin-top:6px;flex-wrap:wrap}
 .ctr button{padding:5px 10px;border:0;border-radius:5px;background:#b00;color:#fff;cursor:pointer}
 .ctr button:hover{background:#900}.ctr select{padding:4px;border-radius:5px}
 .leg{position:absolute;z-index:1000;right:10px;bottom:18px;background:rgba(255,255,255,.95);
  padding:10px 12px;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:12px;max-width:280px}
 .swatch{display:inline-block;width:16px;height:10px;margin-right:6px;vertical-align:middle}
 .barra{height:10px;border-radius:5px;background:linear-gradient(90deg,#3b3,#ff3,#f80,#f00);margin:4px 0}
 .zlbl{background:rgba(0,0,0,.7);color:#fff;border-radius:4px;padding:1px 6px;font-size:11px;font-weight:bold;white-space:nowrap}
</style></head><body>
<div id="map"></div>
<div id="painel">
 <h1>Zonas FM (logradouros) — semanal</h1>
 <div class="sub">Motor v3: score por arterial · janela __JANELA__ semanas · pesos em config_pesos.json</div>
 <div id="semana">--</div><div id="total">--</div>
 <input id="slider" type="range" min="0" max="0" value="0"/>
 <div class="ctr">
  <button id="play">► Play</button><button id="prev">◀</button><button id="next">▶</button>
  <label>vel.<select id="vel"><option value="500">lento</option><option value="250" selected>médio</option><option value="100">rápido</option></select></label>
 </div>
</div>
<div class="leg">
 <b>Heatmap (bingo da semana)</b>
 <div class="barra"></div>
 <div style="display:flex;justify-content:space-between"><span>menor</span><span>maior</span></div>
 <hr/>
 <b>Zonas ótimas da FM</b><br/>
 <span class="swatch" style="background:rgba(180,30,30,.30);border:1.5px solid #700"></span>
 Polígono limitado por logradouros (Arteriais).<br/>
 Cor mais intensa = mais agentes.
</div>
<script>
const WEEKS=__WEEKS__, GRID=__GRID__, HEATMAX=__HEATMAX__, CENTER=[-22.93,-43.30];
const map=L.map('map').setView(CENTER,11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
const heat=L.heatLayer([],{radius:22,blur:18,minOpacity:.35,max:HEATMAX,
  gradient:{0.2:'#33aa33',0.45:'#ffff33',0.7:'#ff8800',1.0:'#ff0000'}}).addTo(map);
const zlayer=L.layerGroup().addTo(map);
function maxAg(z){return Math.max(1,...z.map(o=>o.a));}
function pts(i){return WEEKS[i].hp.map(([ix,iy,w])=>[GRID.lat0+(iy+0.5)*GRID.dlat,GRID.lon0+(ix+0.5)*GRID.dlon,w]);}
function desenha(i){
  heat.setLatLngs(pts(i));
  zlayer.clearLayers();
  const W=WEEKS[i], mx=maxAg(W.z);
  let total_ag=0;
  W.z.forEach(o=>{
    total_ag += o.a;
    const t=o.a/mx, col=`rgb(180,${Math.round(120*(1-t))},${Math.round(120*(1-t))})`;
    const pl=L.polygon(o.poly,{color:'#700',weight:1.8,fillColor:col,fillOpacity:.32}).addTo(zlayer);
    pl.bindTooltip(`<b>${o.l}</b><br/>${o.pct}% do índice<br/><b>${o.a} agentes</b>`,{sticky:true});
    L.marker(pl.getBounds().getCenter(),{icon:L.divIcon({
      className:'',html:`<span class="zlbl">${o.l}: ${o.a}</span>`,iconSize:[0,0]
    })}).addTo(zlayer);
  });
  document.getElementById('semana').textContent='Semana '+W.l;
  document.getElementById('total').textContent=`${W.d} — ${W.z.length} zonas | ${total_ag} agentes`;
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
desenha(WEEKS.length-1);   // começa na última semana
</script></body></html>
"""


def escrever_html(weeks, janela, grid, heatmax):
    out = FM / "visualizacao_semanal.html"
    html = HTML_TMPL
    html = html.replace("__WEEKS__", json.dumps(weeks, separators=(",", ":")))
    html = html.replace("__GRID__", json.dumps(grid))
    html = html.replace("__HEATMAX__", str(round(heatmax, 2)))
    html = html.replace("__JANELA__", str(janela))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML -> {out} ({os.path.getsize(out)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
