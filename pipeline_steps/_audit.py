"""
Audit log compartilhado da pipeline CompStat Rio.

Todos os steps (s1..s5) + o orchestrator (pipeline.py) escrevem eventos
estruturados em `pipeline_audit.jsonl`. A visualização web consome esse
arquivo (tail OU full read), então o schema é estável.

Schema (1 JSON por linha):
  {
    "ts":    "2026-05-24T13:42:11+00:00",  # iso8601 UTC
    "event": "s3_llm_call_done",            # snake_case, prefixo do step
    "level": "OK",                          # INFO | OK | WARN | ERR
    "data":  {...}                          # payload livre
  }

Convenções de event name:
  • pipeline_*          — orchestrator
  • pre_check_*         — verificações de deps
  • step_N_start|done|failed|missing  — fronteira de step
  • sN_<acao>           — eventos internos do step N

Convenções de level (pra visualização web):
  INFO  • progresso / nota
  OK    ✓ milestone bem-sucedido
  WARN  ⚠ atenção (não fatal)
  ERR   ✗ falha

Uso típico:
  from pipeline_steps._audit import log

  log("s1_check_start", {"n_expected": 9})
  log("s1_check_file", {"key": "dd_csv", "size_kb": 1880}, level="OK")
  log("s1_done", {"n_present": 9, "n_missing": 0}, level="OK")
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Path do audit log — sempre relativo à raiz do repo
_REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG = _REPO_ROOT / "pipeline_audit.jsonl"

_ICONS = {"INFO": "•", "OK": "✓", "WARN": "⚠", "ERR": "✗"}


def log(
    event: str,
    data: Optional[dict[str, Any]] = None,
    level: str = "INFO",
    echo: bool = True,
) -> dict:
    """Escreve um evento estruturado em pipeline_audit.jsonl.

    Args:
        event: nome do evento (snake_case, ex.: 's3_llm_call_done').
        data:  dict de payload (opcional). Pode aninhar.
        level: INFO | OK | WARN | ERR (default INFO).
        echo:  se True (default), também imprime no stdout com ícone.

    Returns:
        O dict do evento gravado (útil em testes).
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "level": level,
        "data": data or {},
    }
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if echo:
        icon = _ICONS.get(level, "·")
        suffix = ""
        if data:
            parts = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    parts.append(f"{k}={len(v)} items")
                else:
                    s = str(v)
                    if len(s) > 60:
                        s = s[:57] + "..."
                    parts.append(f"{k}={s}")
            suffix = " " + " ".join(parts)
        print(f"  {icon} {event}{suffix}")

    return entry


def reset() -> None:
    """Apaga o audit log. Útil em testes; não usar em prod."""
    if AUDIT_LOG.exists():
        AUDIT_LOG.unlink()


# --- helpers de convenção pra reduzir ruído nos steps ---

def step_start(step_id: str, name: str, owner: str = "") -> dict:
    return log(f"step_{step_id}_start", {"name": name, "owner": owner})


def step_done(step_id: str, **extras) -> dict:
    return log(f"step_{step_id}_done", extras or None, level="OK")


def step_failed(step_id: str, **extras) -> dict:
    return log(f"step_{step_id}_failed", extras or None, level="ERR")
