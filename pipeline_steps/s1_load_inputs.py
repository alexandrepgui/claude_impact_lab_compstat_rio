"""
Step 1 — Load input files.

Verifica presença e legibilidade de todas as fontes de entrada da pipeline
CompStat Rio. Não transforma; só valida + relata volumes pro audit log
(`pipeline_audit.jsonl`).

Entradas esperadas (repo root):
  dados/df_ocorrencias_tratado - Extração 1 .csv   (ocorrências, ~115k linhas)
  dados/disk_denuncia.csv                          (DD, ~83k linhas → 18k denúncias)
  dados/fatores_urbanos.csv                        (fatores, ~2k linhas)
  dados/cameras_areas_fm.csv                       (câmeras, 985 pontos)
  dados/outros dados/dominio_territorial - Extração 1.csv
  dados/outros dados/CPSR_2020_2022_2024.xlsx
  dados/Dicionário de dados.xlsx
  sh_area_forca/areas_forca_municipal.shp          (+ .shx .dbf .prj .cpg .qmd)
  relints/*.docx                                   (8 RELINTs — usados como gabarito do output)
"""

from __future__ import annotations
import sys
from pathlib import Path

# Garante que pipeline_steps seja importável (quando rodando direto)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline_steps._audit import log  # noqa: E402

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
    log("s1_check_start", {"n_expected": len(EXPECTED)})

    missing = []
    total_bytes = 0

    for key, path in EXPECTED.items():
        if not path.exists():
            log("s1_check_file", {"key": key, "path": str(path), "exists": False}, level="ERR")
            missing.append(key)
            continue

        if path.is_file():
            size = path.stat().st_size
            total_bytes += size
            log(
                "s1_check_file",
                {"key": key, "name": path.name, "size_kb": round(size / 1024, 1), "type": "file"},
                level="OK",
            )
        else:
            docx_files = list(path.glob("*.docx"))
            log(
                "s1_check_file",
                {"key": key, "name": path.name, "n_docx": len(docx_files), "type": "dir"},
                level="OK",
            )

    if missing:
        log(
            "s1_done",
            {"n_present": len(EXPECTED) - len(missing), "n_missing": len(missing), "missing": missing},
            level="ERR",
        )
        return 1

    log(
        "s1_done",
        {"n_present": len(EXPECTED), "n_missing": 0, "total_mb": round(total_bytes / 1024 / 1024, 1)},
        level="OK",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
