"""
CompStat Rio — Transform Pipeline
Group 14 · Claude Impact Lab Rio 2026

Orchestrator. Roda os passos da pipeline ETL Transform em sequencia,
com audit log .jsonl. Cada passo é um script ou função independente —
este arquivo só amarra a ordem.

Steps (mapeados em solution.html → "Pipeline Transform"):
  P1  Load + Normalize       — gerar_shapefiles.py
  P2  Detect inconsistências — TBD (estruturado: já no P1; desestruturado: colegas em curso)
  P3  Resolve (auto + fila)  — TBD (auto: já no P1; humano: stub abaixo)
  P4  Enrich qualitativo     — TBD (LLM extraction de DD/RELINTs)
  P5  Consolidate fact table — analise_grade.py (v0) + recompute pós-enrich (v1)
  P6  Audit log              — este script grava .jsonl

Uso:
  python pipeline.py                # roda tudo
  python pipeline.py --only p1      # roda só P1
  python pipeline.py --skip p4      # pula P4
  python pipeline.py --dry-run      # mostra plano sem executar
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.resolve()
SHAPE_DIR = REPO_ROOT / "shapefiles_qgis"
AUDIT_LOG = REPO_ROOT / "pipeline_audit.jsonl"
REVIEW_QUEUE = REPO_ROOT / "review_queue.json"


# ---------- audit ----------

def log_event(event: str, data: dict | None = None, level: str = "INFO") -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "level": level,
        "data": data or {},
    }
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    icon = {"INFO": "•", "OK": "✓", "WARN": "⚠", "ERR": "✗"}.get(level, "·")
    msg = f" {data}" if data else ""
    print(f"  {icon} {event}{msg}")


# ---------- step runners ----------

def run_script(label: str, script: Path) -> bool:
    if not script.exists():
        log_event(f"{label}_skipped", {"reason": "script not found", "path": str(script)}, level="WARN")
        return False

    log_event(f"{label}_start", {"script": str(script.relative_to(REPO_ROOT))})
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=script.parent,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = proc.stderr[-800:] if proc.stderr else proc.stdout[-800:]
        log_event(f"{label}_failed", {"returncode": proc.returncode, "stderr_tail": tail}, level="ERR")
        return False

    log_event(f"{label}_done", level="OK")
    return True


def run_stub(label: str, description: str) -> bool:
    log_event(f"{label}_stub", {"description": description, "status": "pending_implementation"}, level="WARN")
    return True


# ---------- steps ----------

STEPS = {
    "p1": {
        "name": "P1 · Load + Normalize",
        "fn": lambda: run_script("p1_load_normalize", SHAPE_DIR / "gerar_shapefiles.py"),
        "owner": "Alexandre ✓",
    },
    "p2": {
        "name": "P2 · Detect inconsistências",
        "fn": lambda: run_stub(
            "p2_detect_inconsistencias",
            "Estruturado: tratamentos básicos já em P1 (coord_fix, dentro_rio, axis swap). "
            "Desestruturado: colegas em curso — DD relatos + RELINTs.",
        ),
        "owner": "Devs (em curso)",
    },
    "p3": {
        "name": "P3 · Resolve (auto + fila humana)",
        "fn": lambda: run_stub(
            "p3_resolve",
            "Auto-fix: já aplicado no P1 (correções determinísticas). "
            "Fila humana: a implementar — registros em review_queue.json com confidence < threshold.",
        ),
        "owner": "TBD",
    },
    "p4": {
        "name": "P4 · Enrich qualitativo (LLM)",
        "fn": lambda: run_stub(
            "p4_enrich_llm",
            "LLM extraction de DD relato_redacted + RELINTs .docx → padrões "
            "(modus operandi, rotas fuga, recepção, horário, controle). Colegas em curso.",
        ),
        "owner": "Devs (em curso)",
    },
    "p5": {
        "name": "P5 · Consolidate + Score v0",
        "fn": lambda: run_script("p5_consolidate_score_v0", SHAPE_DIR / "analise_grade.py"),
        "owner": "Alexandre ✓",
    },
    "p5v1": {
        "name": "P5 v1 · Recompute score com unstructured",
        "fn": lambda: run_stub(
            "p5_score_v1",
            "Aguarda P4 terminar. Recalcula risco com novas camadas (modus, horário, recepção) "
            "como contagens na fact table. Mesmo formato de saída de analise_grade.py.",
        ),
        "owner": "TBD (após P4)",
    },
}


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="CompStat Rio Transform Pipeline")
    ap.add_argument("--only", nargs="+", help="Roda só estes passos (ex.: --only p1 p5)")
    ap.add_argument("--skip", nargs="+", default=[], help="Pula estes passos")
    ap.add_argument("--dry-run", action="store_true", help="Mostra plano, não executa")
    args = ap.parse_args()

    selected = [k for k in STEPS if (args.only is None or k in args.only) and k not in args.skip]

    print(f"\n=== CompStat Rio Transform Pipeline ===")
    print(f"Repo root: {REPO_ROOT}")
    print(f"Audit log: {AUDIT_LOG}")
    print(f"\nPlano de execução:")
    for k in selected:
        step = STEPS[k]
        print(f"  [{k}] {step['name']} — owner: {step['owner']}")
    print()

    if args.dry_run:
        print("(dry-run — nada executado)")
        return 0

    log_event("pipeline_start", {"steps": selected})
    failed = []
    for k in selected:
        step = STEPS[k]
        print(f"\n▶ {step['name']}")
        ok = step["fn"]()
        if not ok:
            failed.append(k)
            if k in ("p1", "p5"):  # passos críticos: aborta se falhar
                log_event("pipeline_aborted", {"failed_at": k}, level="ERR")
                return 1

    if failed:
        log_event("pipeline_end_with_warnings", {"failed_or_skipped": failed}, level="WARN")
        print(f"\n⚠ Pipeline terminou com {len(failed)} passo(s) com falha/skip: {failed}")
        return 0  # stubs/skips não são erros fatais

    log_event("pipeline_end", level="OK")
    print(f"\n✓ Pipeline completa. Outputs em {SHAPE_DIR}/analise/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
