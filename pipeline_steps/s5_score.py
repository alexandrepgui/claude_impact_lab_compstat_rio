"""
Step 5 — Generate score from consolidated database.

Lê `areas_fm_risco.shp` (produzido em step 4) e relata o ranking de
risco por área da FM. Atualmente o score é calculado dentro do
`analise_grade.py` (step 4 + 5 misturados) — futuramente o cálculo
deve ser movido para cá, recebendo a fact table do step 4 e produzindo
o ranking + breakdown.

Por enquanto:
  • Lê o shapefile de áreas
  • Imprime o ranking de risco
  • Persiste um JSON com o ranking pra outros consumidores (ex.: gerador .doc)

Quando step 3 (LLM + human) terminar, este step recomputa o score com
as novas dimensões (modus, horário, recepção, controle territorial).
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AREAS_SHP = REPO_ROOT / "shapefiles_qgis" / "analise" / "areas_fm_risco.shp"
SCORE_JSON = REPO_ROOT / "score_ranking.json"


def main() -> int:
    if not AREAS_SHP.exists():
        print(f"[s5] ERR: {AREAS_SHP} não existe. Rode step 4 antes.", file=sys.stderr)
        return 2

    try:
        import geopandas as gpd
    except ImportError:
        print("[s5] WARN: geopandas não instalado — pulando leitura. pip install geopandas.")
        return 0

    gdf = gpd.read_file(AREAS_SHP)
    if "risco" not in gdf.columns:
        print(f"[s5] ERR: coluna 'risco' não encontrada em {AREAS_SHP.name}", file=sys.stderr)
        return 3

    name_col = "nome_area" if "nome_area" in gdf.columns else "nome_subar"
    ranking = (
        gdf[[name_col, "risco", "n_ocor", "n_disque", "n_fator"]]
        .sort_values("risco", ascending=False)
        .reset_index(drop=True)
    )

    print("\n[s5] Ranking de risco por área FM (v0 — só estruturado):\n")
    for i, row in ranking.iterrows():
        print(f"  {i+1}. {row[name_col]}")
        print(f"     risco={row['risco']:.3f}  ocor={int(row['n_ocor'])}  "
              f"den={int(row['n_disque'])}  fat={int(row['n_fator'])}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "v0_structured_only",
        "score_formula": "mean(nrm_ocor, nrm_disq, nrm_fator) * (n_camadas/3)",
        "ranking": ranking.to_dict(orient="records"),
    }
    SCORE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[s5] Ranking salvo em {SCORE_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
