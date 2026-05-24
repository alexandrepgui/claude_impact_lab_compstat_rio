"""
Step 5 — Generate score from consolidated database.

Lê a saída do consolidate (step 4) e relata o ranking de risco. Persiste
o ranking em JSON pra outros consumidores (ex.: gerador .doc futuro).

Estratégia de fonte (prefere v1 do motor semanal):
  1. Tenta `shapefiles_qgis/distribuicao_fm/zonas_semanais.shp` (v1 — motor
     semanal com pesos configuráveis; cada feição é uma zona × semana)
  2. Fallback: `shapefiles_qgis/analise/areas_fm_risco.shp` (v0 — 8 áreas FM
     estáticas com fórmula uniforme)

Usa pyshp (sem dependência de geopandas) — consistente com o resto da
pipeline.
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
V1_BASE = REPO_ROOT / "shapefiles_qgis" / "distribuicao_fm" / "zonas_semanais"
V0_BASE = REPO_ROOT / "shapefiles_qgis" / "analise" / "areas_fm_risco"
SCORE_JSON = REPO_ROOT / "score_ranking.json"


def _pick_source() -> tuple[Path, str] | None:
    if V1_BASE.with_suffix(".shp").exists():
        return V1_BASE, "v1_motor_semanal"
    if V0_BASE.with_suffix(".shp").exists():
        return V0_BASE, "v0_areas_fm_estaticas"
    return None


def _name_field(field_names: list[str]) -> str:
    for cand in ("nome_area", "nome_subar", "nome_zona", "nome"):
        if cand in field_names:
            return cand
    return field_names[0]


def _score_field(field_names: list[str]) -> str:
    for cand in ("risco", "score", "bingo", "score_total"):
        if cand in field_names:
            return cand
    return ""


def main() -> int:
    picked = _pick_source()
    if not picked:
        print(
            f"[s5] ERR: nenhuma saída do step 4 encontrada.\n"
            f"  Esperado: {V1_BASE}.shp  OU  {V0_BASE}.shp\n"
            f"  Rode `python pipeline.py --only 4` antes.",
            file=sys.stderr,
        )
        return 2

    base, version = picked
    print(f"[s5] Fonte: {base.name}.shp ({version})")

    try:
        import shapefile  # pyshp
    except ImportError:
        print(
            "[s5] ERR: pyshp não instalado. pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 4

    reader = shapefile.Reader(str(base), encoding="utf-8")
    field_names = [f[0] for f in reader.fields[1:]]
    score_field = _score_field(field_names)
    if not score_field:
        print(
            f"[s5] ERR: não encontrei campo de score em {base.name}. "
            f"Campos disponíveis: {field_names}",
            file=sys.stderr,
        )
        return 3
    name_field = _name_field(field_names)
    print(f"[s5] Campo de score: '{score_field}'  ·  Campo de nome: '{name_field}'")

    rows = []
    for rec in reader.records():
        row = dict(zip(field_names, list(rec)))
        rows.append(row)

    rows.sort(key=lambda r: r.get(score_field, 0.0) or 0.0, reverse=True)

    # v1 (zonas_semanais) tem 1 linha por (zona, semana) — pode ter dezenas
    # de linhas por zona. Pra leitura, mostramos top 20.
    top_n = min(20, len(rows))
    print(f"\n[s5] Top {top_n} entradas por {score_field} ({version}):\n")
    for i, row in enumerate(rows[:top_n], start=1):
        score_v = row.get(score_field, 0.0) or 0.0
        nome = row.get(name_field, "?")
        extras = []
        for col in ("semana", "n_agentes", "n_ocor", "n_disque", "n_fator"):
            if col in row:
                extras.append(f"{col}={row[col]}")
        extras_s = "  " + "  ".join(extras) if extras else ""
        print(f"  {i:2}. {score_field}={float(score_v):.3f}  {nome}{extras_s}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "source_shapefile": str(base.with_suffix(".shp").relative_to(REPO_ROOT)),
        "score_field": score_field,
        "n_total": len(rows),
        "ranking": rows[:50],  # cap pra evitar JSON gigante
    }
    SCORE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n[s5] Ranking salvo em {SCORE_JSON.relative_to(REPO_ROOT)} ({len(rows)} entradas; top 50 no JSON)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
