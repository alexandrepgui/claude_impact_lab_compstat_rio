"""
Step 4 — Create consolidated database.

Cruza todas as camadas tratadas em uma fact table com PK
`(area_fm_id, grid_cell, periodo)` + contagens por tipo de ocorrência.

Roda dois engines em sequência:
  • v0 — analise_grade.py        → grade_risco.shp + areas_fm_risco.shp (anchor)
  • v1 — motor_bingo_semanal.py  → zonas_semanais.shp + visualizacao_semanal.html

Se v0 falhar = abort (anchor crítico). Se v1 falhar = warn (s5 lê v0 como fallback).
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path

# Garante que pipeline_steps seja importável (quando rodando direto)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline_steps._audit import log  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SHAPE_DIR = REPO_ROOT / "shapefiles_qgis"

# v0 — grade + áreas FM estáticas
SCRIPT_V0 = SHAPE_DIR / "analise_grade.py"
OUT_GRADE = SHAPE_DIR / "analise" / "grade_risco.shp"
OUT_AREAS = SHAPE_DIR / "analise" / "areas_fm_risco.shp"

# v1 — motor semanal configurável
SCRIPT_V1 = SHAPE_DIR / "motor_bingo_semanal.py"
OUT_ZONAS = SHAPE_DIR / "distribuicao_fm" / "zonas_semanais.shp"


def _run(script: Path, label: str) -> int:
    if not script.exists():
        log(f"s4_{label}_skipped", {"reason": "script_missing", "path": str(script)}, level="WARN")
        return 0

    log(f"s4_{label}_start", {"script": str(script.relative_to(REPO_ROOT))})
    proc = subprocess.run([sys.executable, str(script)], cwd=script.parent)
    if proc.returncode != 0:
        log(f"s4_{label}_failed", {"returncode": proc.returncode}, level="ERR")
        return proc.returncode

    log(f"s4_{label}_done", level="OK")
    return 0


def main() -> int:
    # v0 é o anchor — se falhar, abortamos
    rc_v0 = _run(SCRIPT_V0, "v0")
    if rc_v0 != 0:
        log("s4_done", {"v0_ok": False, "fatal": True}, level="ERR")
        return rc_v0

    v0_outputs_present = OUT_GRADE.exists() and OUT_AREAS.exists()
    if not v0_outputs_present:
        log(
            "s4_v0_outputs_missing",
            {"grade_present": OUT_GRADE.exists(), "areas_present": OUT_AREAS.exists()},
            level="WARN",
        )

    # v1 é o motor moderno — falha é só warning (s5 cai pra v0)
    rc_v1 = _run(SCRIPT_V1, "v1")
    v1_ok = rc_v1 == 0 and OUT_ZONAS.exists()

    log(
        "s4_done",
        {
            "v0_ok": v0_outputs_present,
            "v1_ok": v1_ok,
            "primary_source": "zonas_semanais.shp" if v1_ok else "areas_fm_risco.shp",
        },
        level="OK",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
