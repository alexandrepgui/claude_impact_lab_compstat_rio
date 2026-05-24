"""
Step 5 — Generate score from consolidated database.

Lê a saída do consolidate (step 4) e relata o ranking de risco.

Estratégia de fonte (prefere v1 do motor semanal):
  1. `shapefiles_qgis/distribuicao_fm/zonas_semanais.shp` (v1)
  2. Fallback: `shapefiles_qgis/analise/areas_fm_risco.shp` (v0)

Usa pyshp (sem dependência de geopandas).
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Garante que pipeline_steps seja importável (quando rodando direto)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline_steps._audit import log  # noqa: E402

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
    for cand in ("nome_area", "nome_subar", "nome_zona", "nome", "local", "bairro"):
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
        log(
            "s5_no_source",
            {"v1_expected": str(V1_BASE), "v0_expected": str(V0_BASE)},
            level="ERR",
        )
        return 2

    base, version = picked
    log("s5_source_selected", {"version": version, "shapefile": base.name}, level="OK")

    try:
        import shapefile  # pyshp
    except ImportError:
        log("s5_dep_missing", {"package": "pyshp"}, level="ERR")
        return 4

    reader = shapefile.Reader(str(base), encoding="utf-8")
    field_names = [f[0] for f in reader.fields[1:]]
    score_field = _score_field(field_names)
    if not score_field:
        log(
            "s5_score_field_missing",
            {"shapefile": base.name, "available_fields": field_names},
            level="ERR",
        )
        return 3
    name_field = _name_field(field_names)

    rows = []
    for rec in reader.records():
        row = dict(zip(field_names, list(rec)))
        rows.append(row)

    rows.sort(key=lambda r: r.get(score_field, 0.0) or 0.0, reverse=True)

    # Top 20 visível pra leitura humana (também loggado individualmente)
    top_n = min(20, len(rows))
    for i, row in enumerate(rows[:top_n], start=1):
        score_v = float(row.get(score_field, 0.0) or 0.0)
        nome = str(row.get(name_field, "?"))
        extras = {col: row[col] for col in ("semana", "n_agentes", "n_ocor", "n_disque", "n_fator") if col in row}
        log(
            "s5_ranking_entry",
            {"rank": i, "name": nome, score_field: score_v, **extras},
            level="INFO",
            echo=(i <= 10),  # só os top 10 ecoam no console pra não poluir
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "source_shapefile": str(base.with_suffix(".shp").relative_to(REPO_ROOT)),
        "score_field": score_field,
        "n_total": len(rows),
        "ranking": rows[:50],
    }
    SCORE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    log(
        "s5_done",
        {
            "version": version,
            "n_total": len(rows),
            "top_score": float(rows[0].get(score_field, 0.0) or 0.0) if rows else None,
            "top_name": str(rows[0].get(name_field, "?")) if rows else None,
            "output_json": str(SCORE_JSON.relative_to(REPO_ROOT)),
        },
        level="OK",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
