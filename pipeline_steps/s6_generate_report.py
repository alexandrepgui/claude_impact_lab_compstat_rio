"""
Step 6 — Generate report (.docx) per zone.

Orquestra dois scripts em sequência:
  1) shapefiles_qgis/relatorio_zonas.py
     Lê zonas_semanais.shp + camadas cruzadas, monta dossiê compacto/rico
     em distribuicao_fm/relatorio_zonas_{compacto,rico}.{json,md}

  2) shapefiles_qgis/gerar_relatorios_ia.py
     Pra cada zona da última semana (default 8 / env PIPELINE_REPORT_MAX_ZONAS):
       • Renderiza mapa Leaflet via Playwright → PNG
       • Claude Sonnet 4.6 gera texto RELINT a partir do dossiê
       • Monta .docx com texto + mapa
     Outputs em shapefiles_qgis/distribuicao_fm/relatorios_ia/

Modos:
  • Sem ANTHROPIC_API_KEY → STUB (constrói dossiês mas não chama LLM)
  • Com chave → processa N zonas (default 8 = todas da semana)

Pode também usar `python pipeline.py --skip 6` se quiser pular Load.
"""

from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

# Garante que pipeline_steps seja importável (rodando direto OU via pipeline.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline_steps._audit import log  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SHAPE_DIR = REPO_ROOT / "shapefiles_qgis"
SCRIPT_DOSSIE = SHAPE_DIR / "relatorio_zonas.py"
SCRIPT_IA = SHAPE_DIR / "gerar_relatorios_ia.py"
DOSSIE_JSON = SHAPE_DIR / "distribuicao_fm" / "relatorio_zonas_compacto.json"
OUT_DIR = SHAPE_DIR / "distribuicao_fm" / "relatorios_ia"


def _check_api_key_configured() -> bool:
    """True se ANTHROPIC_API_KEY existe e não é placeholder."""
    try:
        from pipeline_steps._llm_client import is_configured  # type: ignore
        return is_configured()
    except ImportError:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        return bool(key) and not key.startswith("sk-ant-api03-COLE")


def _run_subscript(script: Path, label: str, extra_env: dict | None = None) -> int:
    if not script.exists():
        log(f"s6_{label}_missing", {"path": str(script)}, level="ERR")
        return 2

    log(f"s6_{label}_start", {"script": str(script.relative_to(REPO_ROOT))})
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=script.parent,
        env=env,
    )
    if proc.returncode != 0:
        log(f"s6_{label}_failed", {"returncode": proc.returncode}, level="ERR")
        return proc.returncode

    log(f"s6_{label}_done", level="OK")
    return 0


def _count_outputs() -> dict:
    if not OUT_DIR.exists():
        return {"docx": 0, "png": 0}
    docx = list(OUT_DIR.glob("*.docx"))
    png = list(OUT_DIR.glob("*.png"))
    return {"docx": len(docx), "png": len(png), "files": [f.name for f in docx]}


def _stub_run(reason: str) -> int:
    """Constrói dossiês (sem LLM) e pula a geração dos .docx."""
    log("s6_mode_detected", {"mode": "stub", "reason": reason}, level="WARN")
    # Roda só o script de dossiê — não precisa de API key
    rc = _run_subscript(SCRIPT_DOSSIE, "dossie")
    if rc != 0:
        return rc
    log(
        "s6_done",
        {
            "mode": "stub",
            "dossie_built": DOSSIE_JSON.exists(),
            "n_docx": 0,
            "note": "Sem ANTHROPIC_API_KEY: pulei a geração dos .docx (LLM).",
        },
        level="OK",
    )
    return 0


def main() -> int:
    if not _check_api_key_configured():
        return _stub_run("ANTHROPIC_API_KEY não configurada")

    log(
        "s6_mode_detected",
        {
            "mode": "full",
            "max_zonas": os.environ.get("PIPELINE_REPORT_MAX_ZONAS", "8"),
        },
        level="OK",
    )

    # 1) dossiê compacto/rico
    rc = _run_subscript(SCRIPT_DOSSIE, "dossie")
    if rc != 0:
        return rc

    if not DOSSIE_JSON.exists():
        log("s6_dossie_missing", {"path": str(DOSSIE_JSON)}, level="ERR")
        return 3

    # 2) .docx via Claude + Playwright
    rc = _run_subscript(SCRIPT_IA, "ia")
    if rc != 0:
        return rc

    outputs = _count_outputs()
    log(
        "s6_done",
        {
            "mode": "full",
            "n_docx": outputs["docx"],
            "n_png": outputs["png"],
            "files": outputs.get("files", [])[:10],
            "output_dir": str(OUT_DIR.relative_to(REPO_ROOT)),
        },
        level="OK",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
