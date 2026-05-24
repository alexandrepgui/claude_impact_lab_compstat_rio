"""
Step 2 — Automatic treatments.

Aplica correções determinísticas nas fontes (encoding latin-1 em DD,
separador `;`, vírgula decimal, axis swap em fatores_urbanos, coord_fix,
flag dentro_rio, consolidação DD por id_denuncia) e produz os shapefiles
canônicos em `shapefiles_qgis/<fonte>/`.

Delega pro script existente `shapefiles_qgis/gerar_shapefiles.py`, que
faz tudo isso em ~520 linhas. Owner: Alexandre.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path

# Garante que pipeline_steps seja importável (quando rodando direto)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline_steps._audit import log  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "shapefiles_qgis" / "gerar_shapefiles.py"


def main() -> int:
    if not SCRIPT.exists():
        log("s2_script_missing", {"path": str(SCRIPT)}, level="ERR")
        return 2

    log("s2_delegate_start", {"script": str(SCRIPT.relative_to(REPO_ROOT))})
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=SCRIPT.parent,
    )
    if proc.returncode != 0:
        log("s2_delegate_failed", {"returncode": proc.returncode}, level="ERR")
        return proc.returncode

    # Sanity check: shapefiles esperados existem
    expected_shapes = [
        "ocorrencias/ocorrencias.shp",
        "disk_denuncia/disk_denuncia.shp",
        "fatores_urbanos/fatores_urbanos.shp",
        "cameras/cameras.shp",
        "dominio_territorial/dominio_territorial.shp",
        "cpsr/cpsr.shp",
    ]
    base = REPO_ROOT / "shapefiles_qgis"
    found = [p for p in expected_shapes if (base / p).exists()]
    log(
        "s2_done",
        {"shapefiles_produced": len(found), "expected": len(expected_shapes), "outputs": found},
        level="OK",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
