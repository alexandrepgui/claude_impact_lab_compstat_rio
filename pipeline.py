"""
CompStat Rio — Transform Pipeline
Group 14 · Claude Impact Lab Rio 2026

Orchestrator. Roda os passos da pipeline ETL Transform em sequência.
Cada passo é um script independente em `pipeline_steps/`. Este arquivo
só amarra a ordem, registra audit log e devolve um status final.

Passos:
  1. Load input files            → pipeline_steps/s1_load_inputs.py
  2. Automatic treatments        → pipeline_steps/s2_auto_treatments.py
  3. LLM / human / audit treats  → pipeline_steps/s3_assisted_treatments.py
  4. Consolidated database       → pipeline_steps/s4_consolidate.py
  5. Generate score              → pipeline_steps/s5_score.py

Uso:
  python pipeline.py                # roda tudo
  python pipeline.py --only 1 2     # roda só os passos 1 e 2
  python pipeline.py --skip 3       # pula o passo 3
  python pipeline.py --dry-run      # mostra plano sem executar
  python pipeline.py --from 2       # começa do passo 2 até o fim

Audit log: pipeline_audit.jsonl (1 entrada JSON por linha).
"""

from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
STEPS_DIR = REPO_ROOT / "pipeline_steps"
AUDIT_LOG = REPO_ROOT / "pipeline_audit.jsonl"


STEPS = [
    {
        "id": "1",
        "name": "Load input files",
        "script": STEPS_DIR / "s1_load_inputs.py",
        "owner": "Pipeline",
        "critical": True,
    },
    {
        "id": "2",
        "name": "Automatic treatments",
        "script": STEPS_DIR / "s2_auto_treatments.py",
        "owner": "Alexandre",
        "critical": True,
    },
    {
        "id": "3",
        "name": "LLM / human / audit treatments",
        "script": STEPS_DIR / "s3_assisted_treatments.py",
        "owner": "Devs (em curso) — atualmente stub",
        "critical": False,
    },
    {
        "id": "4",
        "name": "Consolidated database",
        "script": STEPS_DIR / "s4_consolidate.py",
        "owner": "Alexandre",
        "critical": True,
    },
    {
        "id": "5",
        "name": "Generate score",
        "script": STEPS_DIR / "s5_score.py",
        "owner": "TBD (recompute v1 depois do step 3)",
        "critical": False,
    },
]


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


def run_step(step: dict) -> bool:
    script: Path = step["script"]
    sid = step["id"]
    label = f"step_{sid}"

    if not script.exists():
        log_event(f"{label}_missing", {"path": str(script)}, level="ERR")
        return False

    log_event(f"{label}_start", {"name": step["name"], "owner": step["owner"]})
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
    )
    if proc.returncode != 0:
        log_event(f"{label}_failed", {"returncode": proc.returncode}, level="ERR")
        return False

    log_event(f"{label}_done", level="OK")
    return True


def select_steps(args: argparse.Namespace) -> list[dict]:
    selected = list(STEPS)
    if args.only:
        ids = set(args.only)
        selected = [s for s in selected if s["id"] in ids]
    if args.from_:
        idx_map = {s["id"]: i for i, s in enumerate(STEPS)}
        if args.from_ not in idx_map:
            print(f"--from valor inválido: {args.from_}", file=sys.stderr)
            sys.exit(2)
        start = idx_map[args.from_]
        selected = [s for s in selected if STEPS.index(s) >= start]
    if args.skip:
        skip = set(args.skip)
        selected = [s for s in selected if s["id"] not in skip]
    return selected


def main() -> int:
    ap = argparse.ArgumentParser(description="CompStat Rio Transform Pipeline")
    ap.add_argument("--only", nargs="+", help="Roda só esses passos (ex.: --only 1 2)")
    ap.add_argument("--from", dest="from_", help="Começa desse passo até o fim (ex.: --from 4)")
    ap.add_argument("--skip", nargs="+", default=[], help="Pula esses passos")
    ap.add_argument("--dry-run", action="store_true", help="Mostra plano, não executa")
    args = ap.parse_args()

    selected = select_steps(args)
    if not selected:
        print("Nenhum step selecionado.", file=sys.stderr)
        return 2

    print(f"\n=== CompStat Rio Transform Pipeline ===")
    print(f"Repo root: {REPO_ROOT}")
    print(f"Audit log: {AUDIT_LOG}")
    print("\nPlano de execução:")
    for s in selected:
        flag = "" if s["critical"] else "  (não crítico)"
        print(f"  [{s['id']}] {s['name']} — owner: {s['owner']}{flag}")
    print()

    if args.dry_run:
        print("(dry-run — nada executado)")
        return 0

    log_event("pipeline_start", {"steps": [s["id"] for s in selected]})
    failed: list[str] = []
    for s in selected:
        print(f"\n▶ Step {s['id']} · {s['name']}")
        ok = run_step(s)
        if not ok:
            failed.append(s["id"])
            if s["critical"]:
                log_event("pipeline_aborted", {"failed_at": s["id"]}, level="ERR")
                return 1

    if failed:
        log_event(
            "pipeline_end_with_warnings",
            {"failed_or_skipped": failed},
            level="WARN",
        )
        print(f"\n⚠ Pipeline terminou com {len(failed)} passo(s) não-crítico(s) com falha.")
        return 0

    log_event("pipeline_end", level="OK")
    print("\n✓ Pipeline completa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
