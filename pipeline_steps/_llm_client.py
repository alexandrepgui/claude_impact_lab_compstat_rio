"""
LLM client helper — carrega API key do .env e devolve cliente Anthropic configurado.

Uso típico nos steps:

    from pipeline_steps._llm_client import get_client, get_model, get_threshold

    client = get_client()
    model = get_model()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

A primeira chamada de get_client() carrega .env (se existir) e valida que
ANTHROPIC_API_KEY está setada. Se faltar, raise com mensagem clara apontando
para .env.example.

Se python-dotenv não estiver instalado, ainda tenta usar variáveis já no
ambiente (export ANTHROPIC_API_KEY=... no shell).
"""

from __future__ import annotations
import os
import sys
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.0
DEFAULT_THRESHOLD = 0.6


def _load_env_once() -> None:
    """Carrega .env via python-dotenv se disponível. Idempotente."""
    if not ENV_FILE.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        # Fallback: parser mínimo (sem dotenv)
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("'\"")
            os.environ.setdefault(k, v)
        return
    load_dotenv(ENV_FILE)


def _fail_missing_key() -> None:
    msg = [
        "",
        "✗ ANTHROPIC_API_KEY não está configurada.",
        "",
        "Como resolver:",
        "  1. Copie o template:    cp .env.example .env",
        "  2. Edite .env e cole sua chave (https://console.anthropic.com/settings/keys)",
        "  3. Reexecute a pipeline",
        "",
        "Alternativa (sem .env):  export ANTHROPIC_API_KEY='sk-ant-...'",
        "",
    ]
    if not ENV_EXAMPLE.exists():
        msg.insert(2, "  ⚠ .env.example também não existe — algo no setup do repo está estranho.")
    print("\n".join(msg), file=sys.stderr)
    raise SystemExit(2)


@lru_cache(maxsize=1)
def get_client():
    """Devolve um cliente Anthropic configurado. Cacheia entre chamadas."""
    _load_env_once()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-ant-api03-COLE"):
        _fail_missing_key()
    try:
        import anthropic  # type: ignore
    except ImportError:
        print(
            "\n✗ Lib 'anthropic' não instalada.\n"
            "  Rode: pip install anthropic  (ou pip install -r requirements.txt)\n",
            file=sys.stderr,
        )
        raise SystemExit(3)
    return anthropic.Anthropic(api_key=api_key)


def get_model() -> str:
    _load_env_once()
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_max_tokens() -> int:
    _load_env_once()
    try:
        return int(os.environ.get("LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS))
    except ValueError:
        return DEFAULT_MAX_TOKENS


def get_temperature() -> float:
    _load_env_once()
    try:
        return float(os.environ.get("LLM_TEMPERATURE", DEFAULT_TEMPERATURE))
    except ValueError:
        return DEFAULT_TEMPERATURE


def get_threshold() -> float:
    """Threshold de confiança abaixo do qual vai pra fila humana."""
    _load_env_once()
    try:
        return float(os.environ.get("PIPELINE_CONFIDENCE_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD


if __name__ == "__main__":
    # Smoke test: confere que a key existe sem fazer chamada de fato.
    _load_env_once()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or key.startswith("sk-ant-api03-COLE"):
        _fail_missing_key()
    print(f"✓ ANTHROPIC_API_KEY presente ({len(key)} chars)")
    print(f"✓ Model:       {get_model()}")
    print(f"✓ Max tokens:  {get_max_tokens()}")
    print(f"✓ Temperature: {get_temperature()}")
    print(f"✓ Threshold:   {get_threshold()}")
