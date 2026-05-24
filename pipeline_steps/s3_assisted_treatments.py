"""
Step 3 — LLM + human + audit-recommended treatments.

Trata inconsistências que NÃO são resolvíveis por regra determinística:
  • Texto livre em Disque Denúncia (relato_redacted)
  • RELINTs (.docx) — texto qualitativo
  • Conflitos entre fontes (denúncia diz bairro X mas relato menciona bairro Y)
  • Padrões com confiança baixa que precisam revisão humana

Implementação esperada (em curso pelos colegas):
  1. Rodar regras semânticas + classificação LLM nos textos
  2. Auto-resolver quando confiança alta E correção segura
  3. Empilhar em review_queue.json o que precisa de humano
  4. Gravar tudo no audit log

Por enquanto este é um STUB que só registra que esse step foi pulado.
Quando os colegas terminarem, substituir o corpo de main() pela chamada
ao script real (subprocess ou import).
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_QUEUE = REPO_ROOT / "review_queue.json"


def main() -> int:
    print("[s3] STUB — LLM + human + audit treatments")
    print("[s3] Owner: devs (em curso). Substituir quando implementação for plugada.")

    # Persiste uma fila vazia (placeholder) pra demais steps poderem ler sem erro.
    REVIEW_QUEUE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "stub",
                "pending_items": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[s3] review_queue.json escrito (vazio, status=stub)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
