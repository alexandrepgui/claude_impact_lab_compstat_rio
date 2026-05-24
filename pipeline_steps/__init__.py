"""
CompStat Rio — pipeline steps package.

Cada módulo `sN_*.py` é um passo executável da pipeline. O módulo
`_audit` é o logger compartilhado (JSONL) que todos os steps usam.
O módulo `_llm_client` carrega o cliente Anthropic + .env.
"""
