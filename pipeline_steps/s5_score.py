"""
Step 5 — Generate score from consolidated database.

Lê `areas_fm_risco.shp` (produzido em step 4) e relata o ranking de
risco por área da FM. Persiste o ranking em JSON pra outros consumidores
(ex.: gerador .doc futuro).

Quando step 3 (LLM + human) terminar, este step recomputa o score com
as novas dimensões (modus, horário, recepção, controle territorial).

Usa pyshp (sem dependência de geopandas) — consistente com o resto da
pipeline.
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AREAS_BASE = REPO_ROOT / "shapefiles_qgis" / "analise" / "areas_fm_risco"
AREAS_SHP = AREAS_BASE.with_suffix(".shp")
SCORE_JSON = REPO_ROOT / "score_ranking.json"


def main() -> int:
    if not AREAS_SHP.exists():
        print(
            f"[s5] ERR: {AREAS_SHP} não existe. Rode step 4 antes.",
            file=sys.stderr,
        )
        return 2

    try:
        import shapefile  # pyshp
    except ImportError:
        print(
            "[s5] ERR: pyshp não instalado. Rode: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 4

    reader = shapefile.Reader(str(AREAS_BASE), encoding="utf-8")
    field_names = [f[0] for f in reader.fields[1:]]  # skip deletion flag

    if "risco" not in field_names:
        print(
            f"[s5] ERR: campo 'risco' não encontrado em {AREAS_SHP.name}",
            file=sys.stderr,
        )
        return 3

    rows = []
    for rec in reader.records():
        row = dict(zip(field_names, list(rec)))
        rows.append(row)

    rows.sort(key=lambda r: r.get("risco", 0.0), reverse=True)
    name_field = "nome_area" if "nome_area" in field_names else "nome_subar"

    print("\n[s5] Ranking de risco por área FM (v0 — só estruturado):\n")
    for i, row in enumerate(rows, start=1):
        print(f"  {i}. {row[name_field]}")
        print(
            f"     risco={row['risco']:.3f}  ocor={int(row['n_ocor'])}  "
            f"den={int(row['n_disque'])}  fat={int(row['n_fator'])}"
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "v0_structured_only",
        "score_formula": "mean(nrm_ocor, nrm_disq, nrm_fator) * (n_camadas/3)",
        "ranking": [
            {
                "rank": i,
                "fid": row.get("fid"),
                "nome_area": row[name_field],
                "risco": row["risco"],
                "n_ocor": row["n_ocor"],
                "n_disque": row["n_disque"],
                "n_fator": row["n_fator"],
                "n_camadas": row.get("n_camadas"),
            }
            for i, row in enumerate(rows, start=1)
        ],
    }
    SCORE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[s5] Ranking salvo em {SCORE_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
