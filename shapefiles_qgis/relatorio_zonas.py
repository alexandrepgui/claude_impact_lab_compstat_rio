# -*- coding: utf-8 -*-
"""
Relatório de zonas — compilado por polígono da ÚLTIMA semana do bingo.

Lê zonas_semanais.shp (saída do motor_bingo_semanal.py), pega a semana mais
recente e, para cada polígono daquela semana, compila um dossiê de tudo o
que está acontecendo dentro dele: ocorrências, denúncias do Disque, fatores
urbanos, câmeras, CPSR e domínio territorial.

Gera 4 arquivos em distribuicao_fm/:

  relatorio_zonas_compacto.json   ← insumo principal pra IA escrever RELINT
  relatorio_zonas_compacto.md
  relatorio_zonas_rico.json       ← versão com séries temporais e + relatos
  relatorio_zonas_rico.md

Rode:
    python relatorio_zonas.py
"""
from __future__ import annotations
import os
import json
import math
import datetime as dt
from collections import Counter, defaultdict
import shapefile  # pyshp

BASE = os.path.dirname(os.path.abspath(__file__))
FM = os.path.join(BASE, "distribuicao_fm")
ZONAS_SHP = os.path.join(FM, "zonas_semanais")

# Quantos relatos do Disque pegar como amostra (compacto / rico).
AMOSTRAS_RELATO = {"compacto": 3, "rico": 10}
TOP_N_COMPACTO = 5
TOP_N_RICO = 15

# As camadas de pontos a serem cruzadas com os polígonos.
# Usa-se latin-1 universalmente (aceita qualquer byte sem erro) e depois
# fix_mojibake() reconstrói a string correta — funciona pra DBFs que misturam
# linhas em cp1252 com linhas em utf-8, comum nesses datasets.
# (nome, path sem extensão, encoding do DBF, tipo de geometria)
LAYERS = [
    ("ocorrencias",         "ocorrencias/ocorrencias",                 "latin-1", "point"),
    ("disque",              "disk_denuncia/disk_denuncia",             "latin-1", "point"),
    ("fatores_urbanos",     "fatores_urbanos/fatores_urbanos",         "latin-1", "point"),
    ("cameras",             "cameras/cameras",                         "latin-1", "point"),
    ("cpsr",                "cpsr/cpsr",                               "latin-1", "point"),
    ("dominio_territorial", "dominio_territorial/dominio_territorial", "latin-1", "polygon"),
]

# Pra área (km²) das zonas.
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON_22_9 = 111320.0 * math.cos(math.radians(22.9))


# --------------------------------------------------------------------------- #
# Geometria
# --------------------------------------------------------------------------- #
def point_in_ring(x, y, ring):
    """Ray-casting clássico. ring = lista de [x,y] com primeiro = último."""
    inside = False
    n = len(ring) - 1
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def bbox_of_ring(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def centroid_of_ring(ring):
    a = cx = cy = 0.0
    n = len(ring) - 1
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a /= 2.0
    if abs(a) < 1e-12:  # degenerate — usa média
        return sum(p[0] for p in ring[:-1]) / n, sum(p[1] for p in ring[:-1]) / n
    return cx / (6 * a), cy / (6 * a)


def area_km2(ring):
    a = 0.0
    n = len(ring) - 1
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        a += x0 * y1 - x1 * y0
    deg2 = abs(a) / 2.0
    return deg2 * M_PER_DEG_LAT * M_PER_DEG_LON_22_9 / 1e6


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse_data_ocor(txt):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def parse_data_disq(txt):
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def parse_hora(txt):
    if not txt:
        return None
    txt = txt.strip()
    if not txt:
        return None
    try:
        if ":" in txt:
            return int(txt.split(":")[0])
        return int(txt[:2])
    except ValueError:
        return None


def topk(counter, k):
    return [{"valor": v, "n": n} for v, n in counter.most_common(k)]


def fix_mojibake(s):
    """Conserta strings de DBFs com encoding misto.

    Lemos tudo como latin-1 (bijetivo, aceita qualquer byte). Se a string
    original era utf-8, ela aparece como mojibake (ex.: "situaÃ§Ã£o") e o
    round-trip .encode('latin-1').decode('utf-8') a restaura ("situação").
    Se a string já era latin-1/cp1252 legítima (ex.: "Estação"), o decode
    utf-8 falha — mantemos o original.
    """
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def carregar_pontos(layer):
    """Devolve lista de (lon, lat, rec_dict) para cada feição utilizável."""
    nome, path, enc, tipo = layer
    r = shapefile.Reader(os.path.join(BASE, path), encoding=enc)
    field_names = [f[0] for f in r.fields[1:]]
    saida = []
    for s, rec in zip(r.iterShapes(), r.iterRecords()):
        if not s.points:
            continue
        if tipo == "point":
            lon, lat = s.points[0]
        else:
            # polygon: usa centróide do bbox
            x0, y0, x1, y1 = s.bbox
            lon, lat = (x0 + x1) / 2, (y0 + y1) / 2
        d = {k: fix_mojibake(rec[k]) for k in field_names}
        saida.append((lon, lat, d))
    return saida


# --------------------------------------------------------------------------- #
# Compila o dossiê de uma zona
# --------------------------------------------------------------------------- #
def dossie_zona(ring, agentes_total, score, pct, polos, n_cel, local, n_zonas_sem,
                pontos_camadas, n_amostras, top_n):
    bbox = bbox_of_ring(ring)
    cx, cy = centroid_of_ring(ring)
    dossie = {
        "local_rotulo": local,
        "centroide": {"lat": round(cy, 6), "lon": round(cx, 6)},
        "bbox": {
            "lat_min": round(bbox[1], 6), "lat_max": round(bbox[3], 6),
            "lon_min": round(bbox[0], 6), "lon_max": round(bbox[2], 6),
        },
        "area_km2": round(area_km2(ring), 3),
        "n_celulas": n_cel,
        "agentes_alocados": agentes_total,
        "score": round(score, 4),
        "pct_indice_semana": round(pct, 2),
    }

    # --- OCORRENCIAS ---
    cat = Counter(); horas = Counter(); dow = Counter(); anos = Counter(); meses = Counter()
    locf = Counter()
    for lon, lat, rec in pontos_camadas["ocorrencias"]:
        if not point_in_ring(lon, lat, ring):
            continue
        cat[(rec.get("desc_delit") or "").strip() or "(s/ tipo)"] += 1
        h = parse_hora(rec.get("hora") or "")
        if h is not None:
            horas[h] += 1
        d = (rec.get("dia_semana") or "").strip()
        if d:
            dow[d] += 1
        a = rec.get("ano")
        if a:
            anos[int(a) if isinstance(a, (int, float)) else a] += 1
        m = rec.get("mes")
        if m:
            try:
                meses[int(m)] += 1
            except (TypeError, ValueError):
                pass
        l = (rec.get("locf") or "").strip()
        if l:
            locf[l.title()] += 1
    dossie["ocorrencias"] = {
        "total": sum(cat.values()),
        "top_tipos": topk(cat, top_n),
        "top_horarios": topk(horas, top_n),
        "top_dias_semana": topk(dow, 7),
        "distribuicao_anual": dict(sorted(anos.items())),
        "top_logradouros": topk(locf, top_n),
    }

    # --- DISQUE ---
    cat = Counter(); classes = Counter(); bairros = Counter(); ruas = Counter()
    relatos = []
    anos_disq = Counter()
    for lon, lat, rec in pontos_camadas["disque"]:
        if not point_in_ring(lon, lat, ring):
            continue
        cat[(rec.get("tipo_pr") or "").strip() or "(s/ tipo)"] += 1
        cl = (rec.get("classe_pr") or "").strip()
        if cl:
            classes[cl] += 1
        b = (rec.get("bairro") or "").strip().title()
        if b:
            bairros[b] += 1
        logr = " ".join(filter(None, [
            (rec.get("tp_logr") or "").strip(),
            (rec.get("logradouro") or "").strip().title(),
        ]))
        if logr:
            ruas[logr] += 1
        rel = (rec.get("relato") or "").strip()
        if rel and len(rel) > 30:
            relatos.append(rel)
        d = parse_data_disq((rec.get("dt_denun") or "").strip())
        if d:
            anos_disq[d.year] += 1
    relatos.sort(key=len, reverse=True)
    dossie["disque"] = {
        "total": sum(cat.values()),
        "top_tipos": topk(cat, top_n),
        "top_classes": topk(classes, top_n),
        "top_bairros": topk(bairros, top_n),
        "top_ruas": topk(ruas, top_n),
        "distribuicao_anual": dict(sorted(anos_disq.items())),
        "amostras_relato": relatos[:n_amostras],
    }

    # --- FATORES URBANOS ---
    cat = Counter(); orgaos = Counter(); ruas = Counter(); bairros = Counter()
    for lon, lat, rec in pontos_camadas["fatores_urbanos"]:
        if not point_in_ring(lon, lat, ring):
            continue
        cat[(rec.get("tp_ocorr") or "").strip() or "(s/ tipo)"] += 1
        o = (rec.get("orgao") or "").strip()
        if o:
            orgaos[o] += 1
        logr = (rec.get("logradouro") or "").strip().title()
        if logr:
            ruas[logr] += 1
        b = (rec.get("bairro") or "").strip().title()
        if b:
            bairros[b] += 1
    dossie["fatores_urbanos"] = {
        "total": sum(cat.values()),
        "top_tipos": topk(cat, top_n),
        "top_orgaos_responsaveis": topk(orgaos, top_n),
        "top_ruas": topk(ruas, top_n),
        "top_bairros": topk(bairros, top_n),
    }

    # --- CAMERAS ---
    areas = Counter()
    total_cam = 0
    for lon, lat, rec in pontos_camadas["cameras"]:
        if not point_in_ring(lon, lat, ring):
            continue
        a = (rec.get("nome_area") or "").strip()
        if a:
            areas[a] += 1
        total_cam += 1
    dossie["cameras"] = {"total": total_cam, "top_areas": topk(areas, top_n)}

    # --- CPSR ---
    sexo = Counter(); faixa = Counter(); raca = Counter(); bairros = Counter()
    anos_cpsr = Counter()
    for lon, lat, rec in pontos_camadas["cpsr"]:
        if not point_in_ring(lon, lat, ring):
            continue
        sexo[(rec.get("sexo") or "").strip()] += 1
        faixa[(rec.get("faixa_et") or "").strip()] += 1
        raca[(rec.get("cor_raca") or "").strip()] += 1
        b = (rec.get("bairro") or "").strip().title()
        if b:
            bairros[b] += 1
        a = rec.get("ano")
        if a:
            try:
                anos_cpsr[int(a)] += 1
            except (TypeError, ValueError):
                pass
    dossie["cpsr"] = {
        "total": sum(sexo.values()),
        "por_sexo": topk(sexo, 5),
        "por_faixa_etaria": topk(faixa, 5),
        "por_cor_raca": topk(raca, 5),
        "top_bairros": topk(bairros, top_n),
        "distribuicao_anual": dict(sorted(anos_cpsr.items())),
    }

    # --- DOMINIO TERRITORIAL ---
    fac = Counter(); terr = []
    for lon, lat, rec in pontos_camadas["dominio_territorial"]:
        if not point_in_ring(lon, lat, ring):
            continue
        f = (rec.get("faccao") or "").strip()
        if f:
            fac[f] += 1
        t = (rec.get("territorio") or "").strip()
        if t:
            terr.append({"territorio": t, "faccao": f})
    dossie["dominio_territorial"] = {
        "total": sum(fac.values()),
        "por_faccao": topk(fac, 5),
        "territorios": terr[:top_n],
    }

    return dossie


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    # 1) Lê zonas_semanais e identifica a última semana.
    r = shapefile.Reader(ZONAS_SHP, encoding="utf-8")
    shapes = r.shapes()
    records = r.records()
    semanas = {(rec["iso_ano"], rec["iso_sem"]) for rec in records}
    ultima = max(semanas)  # (ano, sem) — ordenação natural funciona
    iso_ano, iso_sem = ultima

    zonas_da_semana = [(s, rec) for s, rec in zip(shapes, records)
                       if (rec["iso_ano"], rec["iso_sem"]) == ultima]
    zonas_da_semana.sort(key=lambda sr: sr[1]["zona_id"])
    print(f"Última semana: {iso_ano}-S{iso_sem:02d} | "
          f"zonas: {len(zonas_da_semana)}")

    sem_ini = zonas_da_semana[0][1]["sem_ini"]
    sem_ini_str = sem_ini.isoformat() if hasattr(sem_ini, "isoformat") else str(sem_ini)

    # 2) Carrega todas as camadas de pontos uma vez.
    print("Carregando camadas...")
    pontos_camadas = {}
    for layer in LAYERS:
        nome = layer[0]
        pts = carregar_pontos(layer)
        pontos_camadas[nome] = pts
        print(f"  {nome}: {len(pts)} feições")

    # 3) Compila dossiê de cada zona em 2 níveis (compacto e rico).
    saidas = {}
    for nivel in ("compacto", "rico"):
        top_n = TOP_N_COMPACTO if nivel == "compacto" else TOP_N_RICO
        zonas_dossie = []
        for s, rec in zonas_da_semana:
            ring = s.points  # já vem com último = primeiro
            if list(ring[0]) != list(ring[-1]):
                ring = list(ring) + [ring[0]]
            else:
                ring = list(ring)
            dossie = dossie_zona(
                ring=ring,
                agentes_total=int(rec["agentes"]),
                score=float(rec["score"]),
                pct=float(rec["pct"]),
                polos=None,
                n_cel=int(rec["n_cel"]),
                local=rec["local"],
                n_zonas_sem=len(zonas_da_semana),
                pontos_camadas=pontos_camadas,
                n_amostras=AMOSTRAS_RELATO[nivel],
                top_n=top_n,
            )
            dossie["zona_id"] = int(rec["zona_id"])
            zonas_dossie.append(dossie)

        # ordena por agentes (proxy do peso da zona)
        zonas_dossie.sort(key=lambda z: z["agentes_alocados"], reverse=True)
        for i, z in enumerate(zonas_dossie, 1):
            z["prioridade"] = i

        saidas[nivel] = {
            "semana": {
                "iso_ano": iso_ano,
                "iso_sem": iso_sem,
                "segunda_feira": sem_ini_str,
            },
            "parametros": {
                "n_agentes_total": sum(z["agentes_alocados"] for z in zonas_dossie),
                "n_zonas": len(zonas_dossie),
                "janela_semanas_bingo": 8,
                "grade_metros": 250,
            },
            "zonas": zonas_dossie,
        }

    # 4) Grava arquivos.
    for nivel, payload in saidas.items():
        json_path = os.path.join(FM, f"relatorio_zonas_{nivel}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        md_path = os.path.join(FM, f"relatorio_zonas_{nivel}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(montar_md(payload, nivel))
        print(f"  -> {json_path}")
        print(f"  -> {md_path}")


def montar_md(p, nivel):
    s = p["semana"]
    L = []
    L.append(f"# Relatório de zonas — {nivel} — Semana {s['iso_ano']}-S{s['iso_sem']:02d}")
    L.append("")
    L.append(f"_Segunda-feira de referência: **{s['segunda_feira']}**_  ")
    L.append(f"_{p['parametros']['n_zonas']} zonas · "
             f"{p['parametros']['n_agentes_total']} agentes alocados · "
             f"janela do bingo: {p['parametros']['janela_semanas_bingo']} semanas · "
             f"célula: {p['parametros']['grade_metros']} m_")
    L.append("")
    L.append("> Insumo para a IA gerar um RELINT por zona, no formato dos relatórios em `relints/`.")
    L.append("")
    for z in p["zonas"]:
        L.append("---")
        L.append("")
        L.append(f"## #{z['prioridade']} · {z['local_rotulo']}  (zona_id={z['zona_id']})")
        L.append("")
        L.append(f"- **Coordenada (centróide):** "
                 f"`{z['centroide']['lat']}, {z['centroide']['lon']}`")
        L.append(f"- **Bbox:** lat [{z['bbox']['lat_min']} .. {z['bbox']['lat_max']}] · "
                 f"lon [{z['bbox']['lon_min']} .. {z['bbox']['lon_max']}]")
        L.append(f"- **Área:** {z['area_km2']} km² · **{z['n_celulas']}** células · "
                 f"**{z['agentes_alocados']}** agentes · "
                 f"**{z['pct_indice_semana']}%** do índice da semana · "
                 f"score = {z['score']}")
        L.append("")

        # Ocorrências
        o = z["ocorrencias"]
        L.append(f"### Ocorrências ({o['total']})")
        if o["top_tipos"]:
            L.append("Tipos: " + ", ".join(f"{t['valor']} ({t['n']})"
                                            for t in o["top_tipos"]))
        if o["top_horarios"]:
            L.append("Horários: " + ", ".join(f"{t['valor']}h ({t['n']})"
                                                for t in o["top_horarios"]))
        if o["top_dias_semana"]:
            L.append("Dias da semana: " + ", ".join(f"{t['valor']} ({t['n']})"
                                                     for t in o["top_dias_semana"]))
        if o.get("top_logradouros"):
            L.append("Logradouros: " + ", ".join(f"{t['valor']} ({t['n']})"
                                                   for t in o["top_logradouros"][:5]))
        if nivel == "rico" and o["distribuicao_anual"]:
            L.append("Por ano: " + ", ".join(f"{a}:{n}" for a, n in o["distribuicao_anual"].items()))
        L.append("")

        # Disque
        d = z["disque"]
        L.append(f"### Disque Denúncia ({d['total']})")
        if d["top_tipos"]:
            L.append("Tipos: " + ", ".join(f"{t['valor']} ({t['n']})"
                                            for t in d["top_tipos"]))
        if d.get("top_bairros"):
            L.append("Bairros: " + ", ".join(f"{t['valor']} ({t['n']})"
                                              for t in d["top_bairros"][:5]))
        if d.get("top_ruas"):
            L.append("Ruas: " + ", ".join(f"{t['valor']} ({t['n']})"
                                            for t in d["top_ruas"][:5]))
        if d.get("amostras_relato"):
            L.append("")
            L.append(f"_Amostras de relato ({len(d['amostras_relato'])}):_")
            for rel in d["amostras_relato"]:
                rel_clean = " ".join(rel.split())
                if nivel == "compacto" and len(rel_clean) > 400:
                    rel_clean = rel_clean[:400] + "…"
                L.append(f"> {rel_clean}")
        L.append("")

        # Fatores Urbanos
        f = z["fatores_urbanos"]
        L.append(f"### Fatores Urbanos ({f['total']})")
        if f["top_tipos"]:
            L.append("Tipos: " + ", ".join(f"{t['valor']} ({t['n']})"
                                            for t in f["top_tipos"]))
        if f.get("top_orgaos_responsaveis"):
            L.append("Órgãos responsáveis: " +
                     ", ".join(f"{t['valor']} ({t['n']})"
                                for t in f["top_orgaos_responsaveis"]))
        if f.get("top_ruas"):
            L.append("Ruas: " + ", ".join(f"{t['valor']} ({t['n']})"
                                            for t in f["top_ruas"][:5]))
        L.append("")

        # Camadas auxiliares
        cam = z["cameras"]; cpsr = z["cpsr"]; dom = z["dominio_territorial"]
        aux = []
        if cam["total"]:
            aux.append(f"Câmeras: {cam['total']}")
        if cpsr["total"]:
            aux.append(f"CPSR: {cpsr['total']}")
        if dom["total"]:
            facs = ", ".join(f"{t['valor']}" for t in dom["por_faccao"])
            aux.append(f"Domínio territorial: {dom['total']} território(s) [{facs}]")
        if aux:
            L.append("### Contexto adicional")
            L.append(" · ".join(aux))
            if nivel == "rico" and dom["territorios"]:
                L.append("Territórios: " + ", ".join(
                    f"{t['territorio']} ({t['faccao']})" for t in dom["territorios"]
                ))
            L.append("")

    return "\n".join(L)


if __name__ == "__main__":
    main()
