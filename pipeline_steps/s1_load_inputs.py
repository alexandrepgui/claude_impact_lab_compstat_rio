"""
Step 1 — Load input files.

Verifica presença e legibilidade de todas as fontes de entrada da pipeline
CompStat Rio. Não transforma; só valida + relata volumes pro audit.

Entradas esperadas (repo root):
  dados/df_ocorrencias_tratado - Extração 1 .csv   (ocorrências, ~115k linhas)
  dados/disk_denuncia.csv                          (DD, ~83k linhas → 18k denúncias)
  dados/fatores_urbanos.csv                        (fatores, ~2k linhas)
  dados/cameras_areas_fm.csv                       (câmeras, 985 pontos)
  dados/outros dados/dominio_territorial - Extração 1.csv
  dados/outros dados/CPSR_2020_2022_2024.xlsx
  dados/Dicionário de dados.xlsx
  sh_area_forca/areas_forca_municipal.shp          (+ .shx .dbf .prj .cpg .qmd)
  relints/*.docx                                   (8 RELINTs)

Saída: print + exit code. Para flow detalhado, ler pipeline_audit.jsonl.
"""

from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED = {
    "ocorrencias_csv": REPO_ROOT / "dados" / "df_ocorrencias_tratado - Extração 1 .csv",
    "disk_denuncia_csv": REPO_ROOT / "dados" / "disk_denuncia.csv",
    "fatores_urbanos_csv": REPO_ROOT / "dados" / "fatores_urbanos.csv",
    "cameras_csv": REPO_ROOT / "dados" / "cameras_areas_fm.csv",
    "dominio_territorial_csv": REPO_ROOT / "dados" / "outros dados" / "dominio_territorial - Extração 1.csv",
    "cpsr_xlsx": REPO_ROOT / "dados" / "outros dados" / "CPSR_2020_2022_2024.xlsx",
    "dicionario_xlsx": REPO_ROOT / "dados" / "Dicionário de dados.xlsx",
    "areas_fm_shp": REPO_ROOT / "sh_area_forca" / "areas_forca_municipal.shp",
    "relints_dir": REPO_ROOT / "relints",
}


def main() -> int:
    missing = []
    found = []

    for key, path in EXPECTED.items():
        if path.exists():
            if path.is_file():
                size_kb = path.stat().st_size / 1024
                found.append(f"  ✓ {key}: {path.name} ({size_kb:,.0f} KB)")
            else:
                docx = list(path.glob("*.docx"))
                found.append(f"  ✓ {key}: {path.name}/ ({len(docx)} .docx files)")
        else:
            missing.append(f"  ✗ {key}: MISSING — {path}")

    print("\n".join(found))
    if missing:
        print("\nMISSING FILES:")
        print("\n".join(missing))
        return 1

    # Linha resumo (lida pelo pipeline.py via stdout)
    print(f"\n[s1] All {len(found)} inputs present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
