# -*- coding: utf-8 -*-
"""
Cruza os pontos tratados (ocorrências + Disque Denúncia + fatores urbanos) e
"converge" em áreas, gerando duas camadas de análise para o QGIS:

  1) analise/grade_risco.shp     -> grade (~250 m) com contagem por célula e
                                    índice de coincidência (risco)
  2) analise/areas_fm_risco.shp  -> as áreas da Força Municipal com as mesmas
                                    contagens e índice agregados por área

Índice de coincidência (0–1), que premia a SOBREPOSIÇÃO das camadas:

    risco = média(nrm_ocor, nrm_disq, nrm_fator) * (n_camadas_presentes / 3)

onde cada nrm_* é a contagem da camada normalizada (0–1) e n_camadas_presentes
é quantas das 3 camadas têm pelo menos 1 ponto na área. Assim, uma célula com
muito crime mas sem fator/denúncia pontua baixo; o valor alto aparece onde
crime + dinâmica + fator urbano se encontram.

Lê os shapefiles já gerados por gerar_shapefiles.py (dados limpos).
"""
import os
import math
import shapefile  # pyshp

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "analise")
os.makedirs(OUT, exist_ok=True)

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

# Município do Rio (recorte da grade)
RIO = dict(lat_min=-23.15, lat_max=-22.70, lon_min=-43.85, lon_max=-43.05)

CELL_M = 250.0  # tamanho da célula em metros
LAT_REF = -22.9
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(abs(LAT_REF)))
DLAT = CELL_M / M_PER_DEG_LAT
DLON = CELL_M / M_PER_DEG_LON


def write_aux(path_base):
    with open(path_base + ".prj", "w", encoding="utf-8") as f:
        f.write(PRJ_WGS84)
    with open(path_base + ".cpg", "w", encoding="utf-8") as f:
        f.write("UTF-8")


def read_points(name, only_dentro_rio=False):
    """Lê (lon, lat) de um shapefile de pontos já gerado."""
    path = os.path.join(BASE, name)
    r = shapefile.Reader(path, encoding="utf-8")
    pts = []
    if only_dentro_rio:
        for shp, rec in zip(r.iterShapes(), r.iterRecords()):
            if rec["dentro_rio"] == "S" and shp.points:
                pts.append(tuple(shp.points[0]))
    else:
        for shp in r.iterShapes():
            if shp.points:
                pts.append(tuple(shp.points[0]))
    return pts


def percentil(vals, p):
    if not vals:
        return 1.0
    sv = sorted(vals)
    k = max(0, min(len(sv) - 1, int(round((p / 100.0) * (len(sv) - 1)))))
    return sv[k] or 1.0


def risco(nrm_oc, nrm_dd, nrm_fu, n_camadas):
    return round((nrm_oc + nrm_dd + nrm_fu) / 3.0 * (n_camadas / 3.0), 6)


# ---------------------------------------------------------------------------
# 1) GRADE ~250 m
# ---------------------------------------------------------------------------
def gerar_grade(p_oc, p_dd, p_fu):
    cells = {}  # (ix, iy) -> [n_oc, n_dd, n_fu]

    def bin_pts(pts, idx):
        for lon, lat in pts:
            if not (RIO["lon_min"] <= lon <= RIO["lon_max"]
                    and RIO["lat_min"] <= lat <= RIO["lat_max"]):
                continue
            ix = int((lon - RIO["lon_min"]) / DLON)
            iy = int((lat - RIO["lat_min"]) / DLAT)
            c = cells.setdefault((ix, iy), [0, 0, 0])
            c[idx] += 1

    bin_pts(p_oc, 0)
    bin_pts(p_dd, 1)
    bin_pts(p_fu, 2)

    p95_oc = percentil([c[0] for c in cells.values() if c[0]], 95)
    p95_dd = percentil([c[1] for c in cells.values() if c[1]], 95)
    p95_fu = percentil([c[2] for c in cells.values() if c[2]], 95)

    out = os.path.join(OUT, "grade_risco")
    w = shapefile.Writer(out, shapeType=shapefile.POLYGON, encoding="utf-8")
    w.field("cell_id", "C", 20)
    w.field("n_ocor", "N", 9)
    w.field("n_disque", "N", 9)
    w.field("n_fator", "N", 9)
    w.field("nrm_ocor", "N", 12, 6)
    w.field("nrm_disq", "N", 12, 6)
    w.field("nrm_fator", "N", 12, 6)
    w.field("n_camadas", "N", 2)
    w.field("risco", "N", 12, 6)

    for (ix, iy), (n_oc, n_dd, n_fu) in cells.items():
        nrm_oc = min(n_oc / p95_oc, 1.0)
        nrm_dd = min(n_dd / p95_dd, 1.0)
        nrm_fu = min(n_fu / p95_fu, 1.0)
        n_cam = (n_oc > 0) + (n_dd > 0) + (n_fu > 0)
        x0 = RIO["lon_min"] + ix * DLON
        y0 = RIO["lat_min"] + iy * DLAT
        x1, y1 = x0 + DLON, y0 + DLAT
        # anel no sentido horário (convenção ESRI para anel externo)
        w.poly([[[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]])
        w.record(f"{ix}_{iy}", n_oc, n_dd, n_fu,
                 round(nrm_oc, 6), round(nrm_dd, 6), round(nrm_fu, 6),
                 n_cam, risco(nrm_oc, nrm_dd, nrm_fu, n_cam))
    w.close()
    write_aux(out)
    print(f"[grade] celulas={len(cells)} p95(oc/dd/fu)={p95_oc}/{p95_dd}/{p95_fu} "
          f"cell~{CELL_M:.0f}m (dlon={DLON:.6f}, dlat={DLAT:.6f})")
    return len(cells)


# ---------------------------------------------------------------------------
# 2) ÁREAS DA FORÇA MUNICIPAL
# ---------------------------------------------------------------------------
def point_in_polygon(x, y, points, parts):
    parts = list(parts) + [len(points)]
    inside = False
    for pi in range(len(parts) - 1):
        ring = points[parts[pi]:parts[pi + 1]]
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if ((yi > y) != (yj > y)) and \
               (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
    return inside


def gerar_areas_fm(p_oc, p_dd, p_fu):
    src = os.path.join(BASE, "..", "sh_area_forca", "areas_forca_municipal")
    r = shapefile.Reader(os.path.normpath(src), encoding="utf-8")
    shapes = r.shapes()
    recs = r.records()

    bboxes = [s.bbox for s in shapes]           # (xmin, ymin, xmax, ymax)
    cont = [[0, 0, 0] for _ in shapes]          # contagens por área

    def conta(pts, idx):
        for lon, lat in pts:
            for ai, bb in enumerate(bboxes):
                if bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]:
                    if point_in_polygon(lon, lat, shapes[ai].points, shapes[ai].parts):
                        cont[ai][idx] += 1
                        break

    conta(p_oc, 0)
    conta(p_dd, 1)
    conta(p_fu, 2)

    max_oc = max((c[0] for c in cont), default=1) or 1
    max_dd = max((c[1] for c in cont), default=1) or 1
    max_fu = max((c[2] for c in cont), default=1) or 1

    out = os.path.join(OUT, "areas_fm_risco")
    w = shapefile.Writer(out, shapeType=shapefile.POLYGON, encoding="utf-8")
    w.field("fid", "N", 10)
    w.field("nome_area", "C", 254)
    w.field("n_ocor", "N", 9)
    w.field("n_disque", "N", 9)
    w.field("n_fator", "N", 9)
    w.field("nrm_ocor", "N", 12, 6)
    w.field("nrm_disq", "N", 12, 6)
    w.field("nrm_fator", "N", 12, 6)
    w.field("n_camadas", "N", 2)
    w.field("risco", "N", 12, 6)

    for ai, shp in enumerate(shapes):
        n_oc, n_dd, n_fu = cont[ai]
        nrm_oc = n_oc / max_oc
        nrm_dd = n_dd / max_dd
        nrm_fu = n_fu / max_fu
        n_cam = (n_oc > 0) + (n_dd > 0) + (n_fu > 0)
        w.poly([list(p) for p in _rings(shp)])
        fid = recs[ai]["fid"]
        nome = recs[ai]["nome_subar"]
        w.record(fid, nome, n_oc, n_dd, n_fu,
                 round(nrm_oc, 6), round(nrm_dd, 6), round(nrm_fu, 6),
                 n_cam, risco(nrm_oc, nrm_dd, nrm_fu, n_cam))
        print(f"  area fid={fid:>3} oc={n_oc:>5} dd={n_dd:>4} fu={n_fu:>4} "
              f"risco={risco(nrm_oc, nrm_dd, nrm_fu, n_cam):.3f}  {nome}")
    w.close()
    write_aux(out)
    print(f"[areas_fm] areas={len(shapes)} max(oc/dd/fu)={max_oc}/{max_dd}/{max_fu}")
    return len(shapes)


def _rings(shp):
    """Devolve a lista de anéis (partes) de um shape de polígono."""
    parts = list(shp.parts) + [len(shp.points)]
    return [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]


if __name__ == "__main__":
    print("Lendo pontos tratados...")
    p_oc = read_points("ocorrencias/ocorrencias")
    p_dd = read_points("disk_denuncia/disk_denuncia", only_dentro_rio=True)
    p_fu = read_points("fatores_urbanos/fatores_urbanos")
    print(f"  ocorrencias={len(p_oc)} disque(RJ)={len(p_dd)} fatores={len(p_fu)}")
    print("Gerando grade ~250 m...")
    gerar_grade(p_oc, p_dd, p_fu)
    print("Agregando por area da FM...")
    gerar_areas_fm(p_oc, p_dd, p_fu)
    print("Concluído.")
