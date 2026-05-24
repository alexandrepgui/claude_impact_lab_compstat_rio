"""
Step 4 — Create consolidated database.

Cruza todas as camadas tratadas em uma fact table com PK
`(area_fm_id, grid_cell, periodo)` + contagens por tipo de ocorrência.

Implementação atual delega pro `shapefiles_qgis/analise_grade.py` do
Alexandre, que produz:

  shapefiles_qgis/analise/grade_risco.shp       — grid 250m, 7534 células
                                                  (cada célula com contagens
                                                  por camada e índice de risco)
  shapefiles_qgis/analise/areas_fm_risco.shp    — 8 áreas FM agregadas

Esses dois shapefiles SÃO a base consolidada (ainda sem unstructured).
Quando step 3 trouxer novas dimensões (modus, horário, recepção etc.),
este step terá que recomputar a fact table com colunas adicionais.

Owner atual: Alexandre.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "shapefiles_qgis" / "analise_grade.py"
OUT_GRADE = REPO_ROOT / "shapefiles_qgis" / "analise" / "grade_risco.shp"
OUT_AREAS = REPO_ROOT / "shapefiles_qgis" / "analise" / "areas_fm_risco.shp"


def main() -> int:
    if not SCRIPT.exists():
        print(f"[s4] ERR: script não encontrado: {SCRIPT}", file=sys.stderr)
        return 2

    print(f"[s4] Delegando para {SCRIPT.relative_to(REPO_ROOT)}")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=SCRIPT.parent,
    )
    if proc.returncode != 0:
        print(f"[s4] ERR: analise_grade.py retornou {proc.returncode}", file=sys.stderr)
        return proc.returncode

    # Sanity check: arquivos finais existem
    for out in (OUT_GRADE, OUT_AREAS):
        if not out.exists():
            print(f"[s4] WARN: saída esperada não encontrada: {out}", file=sys.stderr)

    print(f"[s4] Consolidated DB pronta: grade_risco.shp + areas_fm_risco.shp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
