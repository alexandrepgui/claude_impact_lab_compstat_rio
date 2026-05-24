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
SHAPE_DIR = REPO_ROOT / "shapefiles_qgis"

# v0 — grade + áreas FM estáticas (analise_grade.py)
SCRIPT_V0 = SHAPE_DIR / "analise_grade.py"
OUT_GRADE = SHAPE_DIR / "analise" / "grade_risco.shp"
OUT_AREAS = SHAPE_DIR / "analise" / "areas_fm_risco.shp"

# v1 — motor semanal com pesos configuráveis (motor_bingo_semanal.py)
SCRIPT_V1 = SHAPE_DIR / "motor_bingo_semanal.py"
OUT_ZONAS = SHAPE_DIR / "distribuicao_fm" / "zonas_semanais.shp"


def _run(script: Path, label: str) -> int:
    if not script.exists():
        print(f"[s4] {label}: script não encontrado, pulando ({script.name})", file=sys.stderr)
        return 0  # não crítico: continuamos
    print(f"[s4] {label}: rodando {script.relative_to(REPO_ROOT)}")
    proc = subprocess.run([sys.executable, str(script)], cwd=script.parent)
    if proc.returncode != 0:
        print(f"[s4] {label}: ERR returncode={proc.returncode}", file=sys.stderr)
        return proc.returncode
    print(f"[s4] {label}: OK")
    return 0


def main() -> int:
    # Roda v0 e v1 em sequência. Se v0 falhar, abortamos (é o anchor).
    # v1 pode falhar sem matar o step (fallback do s5 ainda lê v0).

    rc_v0 = _run(SCRIPT_V0, "v0 (grade + áreas FM estáticas)")
    if rc_v0 != 0:
        return rc_v0
    for out in (OUT_GRADE, OUT_AREAS):
        if not out.exists():
            print(f"[s4] WARN: saída v0 não encontrada: {out}", file=sys.stderr)

    rc_v1 = _run(SCRIPT_V1, "v1 (motor semanal + alocação 600 agentes)")
    if rc_v1 != 0:
        print(f"[s4] WARN: motor v1 falhou mas v0 está OK — pipeline segue", file=sys.stderr)
    elif not OUT_ZONAS.exists():
        print(f"[s4] WARN: saída v1 não encontrada: {OUT_ZONAS}", file=sys.stderr)

    print(f"[s4] Consolidated DB pronta")
    print(f"[s4]   v0: grade_risco.shp + areas_fm_risco.shp")
    if OUT_ZONAS.exists():
        print(f"[s4]   v1: zonas_semanais.shp (motor configurável)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
