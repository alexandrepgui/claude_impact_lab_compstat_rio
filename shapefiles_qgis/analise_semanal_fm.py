# -*- coding: utf-8 -*-
"""
Refino do CompStat Rio — duas entregas:

  1) distribuicao_fm/heatmap_semanal.shp
     Mapa de calor SEMANAL das ocorrências em grade ~250 m.
     Cada feição = (célula × semana ISO), com data de início da semana para
     animar no Controlador Temporal do QGIS.

  2) distribuicao_fm/zonas_recomendadas.shp  +  zonas_celulas.shp
     Proposta de NOVAS zonas de atuação da Força Municipal, desenhadas do zero
     a partir dos hotspots de crime, com alocação dos 600 agentes proporcional
     ao volume de crime de cada zona.

Usa a MESMA grade (origem/célula) da análise grade_risco, para manter o "bingo"
consistente. Lê os shapefiles de pontos já tratados.
"""
import os
import math
import datetime as dt
import shapefile  # pyshp

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "distribuicao_fm")

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

# Grade (idêntica à de grade_risco.shp)
RIO = dict(lat_min=-23.15, lat_max=-22.70, lon_min=-43.85, lon_max=-43.05)
CELL_M = 250.0
LAT_REF = -22.9
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(abs(LAT_REF)))
DLAT = CELL_M / M_PER_DEG_LAT
DLON = CELL_M / M_PER_DEG_LON

# Período válido das ocorrências
ANO_MIN, ANO_MAX = 2020, 2024

# Parâmetros das zonas
COBERTURA_CRIME = 0.50   # hotspots = células que somam 50% do crime
MIN_SHARE_ZONA = 0.01    # mantém zonas com >=1% do crime total
N_AGENTES = 600


def write_aux(path_base):
    with open(path_base + ".prj", "w", encoding="utf-8") as f:
        f.write(PRJ_WGS84)
    with open(path_base + ".cpg", "w", encoding="utf-8") as f:
        f.write("UTF-8")


def cell_of(lon, lat):
    if not (RIO["lon_min"] <= lon <= RIO["lon_max"]
            and RIO["lat_min"] <= lat <= RIO["lat_max"]):
        return None
    return (int((lon - RIO["lon_min"]) / DLON),
            int((lat - RIO["lat_min"]) / DLAT))


def cell_square(ix, iy):
    x0 = RIO["lon_min"] + ix * DLON
    y0 = RIO["lat_min"] + iy * DLAT
    x1, y1 = x0 + DLON, y0 + DLAT
    # anel horário (convenção ESRI p/ anel externo)
    return [[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]


def read_point_cells(name, only_dentro_rio=False):
    """Lê um shapefile de pontos e devolve a contagem por célula."""
    r = shapefile.Reader(os.path.join(BASE, name), encoding="utf-8")
    cont = {}
    if only_dentro_rio:
        it = ((s, rec) for s, rec in zip(r.iterShapes(), r.iterRecords()))
        for s, rec in it:
            if rec["dentro_rio"] != "S" or not s.points:
                continue
            c = cell_of(*s.points[0])
            if c:
                cont[c] = cont.get(c, 0) + 1
    else:
        for s in r.iterShapes():
            if s.points:
                c = cell_of(*s.points[0])
                if c:
                    cont[c] = cont.get(c, 0) + 1
    return cont


def read_cell_bairro():
    """Mapa célula -> contagem de bairros (denúncias + fatores) p/ rotular zonas."""
    from collections import Counter
    cb = {}

    def add(name, campo, only_rio):
        r = shapefile.Reader(os.path.join(BASE, name), encoding="utf-8")
        for s, rec in zip(r.iterShapes(), r.iterRecords()):
            if only_rio and rec["dentro_rio"] != "S":
                continue
            if not s.points:
                continue
            c = cell_of(*s.points[0])
            b = (rec[campo] or "").strip()
            if c and b:
                cb.setdefault(c, Counter())[b.title()] += 1

    add("disk_denuncia/disk_denuncia", "bairro", True)
    add("fatores_urbanos/fatores_urbanos", "bairro", False)
    return cb


# ---------------------------------------------------------------------------
# 1) HEATMAP SEMANAL
# ---------------------------------------------------------------------------
def gerar_heatmap_semanal():
    r = shapefile.Reader(os.path.join(BASE, "ocorrencias", "ocorrencias"),
                         encoding="utf-8")
    # (cell, iso_ano, iso_sem) -> contagem
    cont = {}
    sem_total = {}     # contagem total por célula (todo o período)
    usados = ignorados = 0
    for s, rec in zip(r.iterShapes(), r.iterRecords()):
        if not s.points:
            continue
        data_txt = (rec["data"] or "").strip()
        d = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                d = dt.datetime.strptime(data_txt, fmt).date()
                break
            except ValueError:
                continue
        if d is None or not (ANO_MIN <= d.year <= ANO_MAX):
            ignorados += 1
            continue
        c = cell_of(*s.points[0])
        if c is None:
            ignorados += 1
            continue
        iso = d.isocalendar()  # (ano_iso, semana_iso, dia)
        key = (c, iso[0], iso[1])
        cont[key] = cont.get(key, 0) + 1
        sem_total[c] = sem_total.get(c, 0) + 1
        usados += 1

    out = os.path.join(OUT, "heatmap_semanal")
    w = shapefile.Writer(out, shapeType=shapefile.POLYGON, encoding="utf-8")
    w.field("cell_id", "C", 20)
    w.field("iso_ano", "N", 4)
    w.field("iso_sem", "N", 2)
    w.field("sem_ini", "D")       # segunda-feira da semana (p/ Controlador Temporal)
    w.field("n_ocor", "N", 9)

    for (c, ia, isem), n in cont.items():
        ix, iy = c
        # segunda-feira da semana ISO
        seg = dt.date.fromisocalendar(ia, isem, 1)
        w.poly([cell_square(ix, iy)])
        w.record(f"{ix}_{iy}", ia, isem, seg, n)
    w.close()
    write_aux(out)
    n_semanas = len({(ia, isem) for (_, ia, isem) in cont})
    print(f"[heatmap_semanal] ocor_usadas={usados} ignoradas={ignorados} "
          f"celulas-semana={len(cont)} semanas={n_semanas}")
    return sem_total


# ---------------------------------------------------------------------------
# 2) ZONAS ÓTIMAS + ALOCAÇÃO DE AGENTES
# ---------------------------------------------------------------------------
def convex_hull(points):
    pts = sorted(set(map(tuple, points)))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def shoelace_km2(ring):
    a = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        a += x1 * y2 - x2 * y1
    area_deg2 = abs(a) / 2.0
    return area_deg2 * M_PER_DEG_LAT * M_PER_DEG_LON / 1e6


def clusters_8viz(cells_set):
    """Componentes conectados (vizinhança 8) sobre um conjunto de células."""
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
                    if dx == 0 and dy == 0:
                        continue
                    viz = (ix + dx, iy + dy)
                    if viz in cells_set and viz not in visto:
                        visto.add(viz)
                        pilha.append(viz)
        comps.append(comp)
    return comps


def gerar_zonas(crime_cells, disque_cells, fator_cells, cell_bairro):
    from collections import Counter
    total_crime = sum(crime_cells.values())

    # 1) hotspots = células que, somadas, cobrem COBERTURA_CRIME do crime
    ordenadas = sorted(crime_cells.items(), key=lambda kv: kv[1], reverse=True)
    alvo = total_crime * COBERTURA_CRIME
    acc = 0
    hot = set()
    for cell, n in ordenadas:
        if acc >= alvo:
            break
        hot.add(cell)
        acc += n

    # 2) agrupa hotspots adjacentes em zonas
    comps = clusters_8viz(hot)

    # 3) métricas por zona e filtro por participação no crime
    zonas = []
    for comp in comps:
        crime = sum(crime_cells.get(c, 0) for c in comp)
        if crime < MIN_SHARE_ZONA * total_crime:
            continue
        disque = sum(disque_cells.get(c, 0) for c in comp)
        fator = sum(fator_cells.get(c, 0) for c in comp)
        zonas.append(dict(cells=comp, crime=crime, disque=disque, fator=fator))

    zonas.sort(key=lambda z: z["crime"], reverse=True)
    crime_zonas = sum(z["crime"] for z in zonas)

    # 4) alocação dos agentes (maior resto p/ fechar exatamente N_AGENTES)
    brutos = [N_AGENTES * z["crime"] / crime_zonas for z in zonas]
    base = [int(math.floor(b)) for b in brutos]
    resto = N_AGENTES - sum(base)
    ordem_resto = sorted(range(len(zonas)), key=lambda i: brutos[i] - base[i],
                         reverse=True)
    for i in range(resto):
        base[ordem_resto[i]] += 1
    for i, z in enumerate(zonas):
        z["agentes"] = base[i]

    # 5) grava zonas (envoltória convexa) e células com zona_id
    out_z = os.path.join(OUT, "zonas_recomendadas")
    wz = shapefile.Writer(out_z, shapeType=shapefile.POLYGON, encoding="utf-8")
    wz.field("zona_id", "N", 4)
    wz.field("local", "C", 60)
    wz.field("prioridade", "N", 4)
    wz.field("n_celulas", "N", 6)
    wz.field("n_ocor", "N", 9)
    wz.field("n_disque", "N", 9)
    wz.field("n_fator", "N", 9)
    wz.field("pct_crime", "N", 7, 2)
    wz.field("agentes", "N", 5)
    wz.field("area_km2", "N", 10, 3)

    out_c = os.path.join(OUT, "zonas_celulas")
    wc = shapefile.Writer(out_c, shapeType=shapefile.POLYGON, encoding="utf-8")
    wc.field("zona_id", "N", 4)
    wc.field("cell_id", "C", 20)
    wc.field("n_ocor", "N", 9)

    print(f"  zonas mantidas: {len(zonas)} | crime coberto: "
          f"{crime_zonas} ({100*crime_zonas/total_crime:.1f}% do total)")
    for zi, z in enumerate(zonas, start=1):
        corners = []
        bairros = Counter()
        for (ix, iy) in z["cells"]:
            sq = cell_square(ix, iy)[:4]
            corners.extend(sq)
            wc.poly([cell_square(ix, iy)])
            wc.record(zi, f"{ix}_{iy}", crime_cells.get((ix, iy), 0))
            if (ix, iy) in cell_bairro:
                bairros.update(cell_bairro[(ix, iy)])
        local = bairros.most_common(1)[0][0] if bairros else "(sem rótulo)"
        hull = convex_hull(corners)
        ring = hull[::-1] + [hull[-1]]  # fecha; sentido horário
        pct = 100.0 * z["crime"] / total_crime
        wz.poly([[list(p) for p in ring]])
        wz.record(zi, local, zi, len(z["cells"]), z["crime"], z["disque"],
                  z["fator"], round(pct, 2), z["agentes"],
                  round(shoelace_km2(hull), 3))
        print(f"    zona {zi:>2} [{local}]: ocor={z['crime']:>5} ({pct:4.1f}%) "
              f"agentes={z['agentes']:>3} celulas={len(z['cells'])}")
    wz.close()
    wc.close()
    write_aux(out_z)
    write_aux(out_c)
    return zonas, total_crime


if __name__ == "__main__":
    print("1) Heatmap semanal...")
    crime_cells = gerar_heatmap_semanal()
    print("2) Lendo denúncias e fatores (contexto das zonas)...")
    disque_cells = read_point_cells("disk_denuncia/disk_denuncia", only_dentro_rio=True)
    fator_cells = read_point_cells("fatores_urbanos/fatores_urbanos")
    cell_bairro = read_cell_bairro()
    print("3) Zonas ótimas + alocação de agentes...")
    gerar_zonas(crime_cells, disque_cells, fator_cells, cell_bairro)
    print("Concluído.")
