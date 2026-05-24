"""
Step 2 — Automatic treatments.

Aplica correções determinísticas nas fontes (encoding latin-1 em DD,
separador `;`, vírgula decimal, axis swap em fatores_urbanos, coord_fix,
flag dentro_rio, consolidação DD por id_denuncia) e produz os shapefiles
canônicos em `shapefiles_qgis/<fonte>/`.

Delega pro script existente `shapefiles_qgis/gerar_shapefiles.py`, que
faz tudo isso em ~520 linhas. Owner: Alexandre.

Saídas (cada uma com .shp + .shx + .dbf + .prj + .cpg):
  shapefiles_qgis/ocorrencias/ocorrencias.shp        (115.354 pontos)
  shapefiles_qgis/disk_denuncia/disk_denuncia.shp    (17.850 pontos, 1/denúncia)
  shapefiles_qgis/fatores_urbanos/fatores_urbanos.shp (2.085 pontos)
  shapefiles_qgis/cameras/cameras.shp                (985 pontos)
  shapefiles_qgis/dominio_territorial/dominio_territorial.shp
  shapefiles_qgis/cpsr/cpsr.shp                      (Censo PSR)
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "shapefiles_qgis" / "gerar_shapefiles.py"


def main() -> int:
    if not SCRIPT.exists():
        print(f"[s2] ERR: script não encontrado: {SCRIPT}", file=sys.stderr)
        return 2

    print(f"[s2] Delegando para {SCRIPT.relative_to(REPO_ROOT)}")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=SCRIPT.parent,
    )
    if proc.returncode != 0:
        print(f"[s2] ERR: gerar_shapefiles.py retornou {proc.returncode}", file=sys.stderr)
        return proc.returncode

    print(f"[s2] Treatments automáticos aplicados. Shapefiles em shapefiles_qgis/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
