"""
Step 3 — LLM + human + audit-recommended treatments.

Lê os relatos do Disque Denúncia (texto livre em `relato_redacted`),
classifica via Claude no vocabulário canônico (60 IDs em 3 perspectivas)
seguindo o template de 5 elementos descoberto em
`docs/analise_qualitativa_ocorrencias.md`, e gera:

  • relato_estruturado.jsonl  — 1 JSON por denúncia processada
  • review_queue.json         — fila humana (extração baixou confidence
                                ou parse falhou)

Comportamento auto-detect (decidido com o time):
  • Sem ANTHROPIC_API_KEY     → modo STUB (sem custo, escreve fila vazia)
  • Com ANTHROPIC_API_KEY     → modo SAMPLE (default 5 relatos)

Flags:
  python s3_assisted_treatments.py              # auto: stub OU sample 5
  python s3_assisted_treatments.py --sample 50  # processa 50
  python s3_assisted_treatments.py --all        # processa TODAS (~18k, ~$54 em Sonnet)
  python s3_assisted_treatments.py --stub       # força stub mesmo com key

Modelo default: Claude Sonnet 4.5 (mais barato). Override via
`ANTHROPIC_MODEL` no .env.
"""

from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DD_BASE = REPO_ROOT / "shapefiles_qgis" / "disk_denuncia" / "disk_denuncia"
OUT_JSONL = REPO_ROOT / "relato_estruturado.jsonl"
REVIEW_QUEUE = REPO_ROOT / "review_queue.json"


# Vocabulário canônico (subset prioritário; expandir conforme análise qualitativa).
# Fonte: docs/analise_qualitativa_ocorrencias.md seção 4
VOCAB = [
    # === VIOLÊNCIA ===
    ("VIO-001", "Homicídio consumado"),
    ("VIO-003", "Lesão corporal"),
    ("VIO-004", "Ameaça"),
    ("VIO-009", "Violência contra mulher"),
    ("VIO-010", "Violência contra idoso"),
    ("VIO-014", "Abuso de autoridade (funcionário público)"),
    # === PATRIMÔNIO (foco do CompStat) ===
    ("PAT-001", "Roubo ou furto a transeunte"),
    ("PAT-002", "Roubo em transporte coletivo"),
    ("PAT-003", "Roubo a motoristas"),
    ("PAT-004", "Roubo ou furto a residências"),
    ("PAT-005", "Roubo ou furto a estabelecimento comercial"),
    ("PAT-006", "Roubo de veículo"),
    ("PAT-007", "Furto de veículo"),
    ("PAT-009", "Extorsão"),
    # === DROGAS ===
    ("DRG-001", "Tráfico de drogas"),
    ("DRG-003", "Consumo de drogas (denúncia)"),
    ("DRG-004", "Cena pública de uso de drogas"),
    # === ARMAS ===
    ("ARM-001", "Posse ilícita de arma de fogo"),
    ("ARM-002", "Guarda/comércio ilícito de armas"),
    ("ARM-003", "Uso ilícito de arma de fogo"),
    # === INFRAESTRUTURA URBANA (fator ambiental) ===
    ("INF-006", "Área mal iluminada com circulação de pedestres"),
    ("INF-004", "Comércio irregular obstruindo visibilidade"),
    ("INF-002", "Vegetação encobrindo iluminação pública"),
    # === VULNERABILIDADE SOCIAL ===
    ("VSO-001", "Pessoas em situação de rua"),
    ("VSO-003", "Abandono de criança"),
    ("VSO-004", "Corrupção de menores"),
    # === PERTURBAÇÃO / ORDEM PÚBLICA ===
    ("PRT-001", "Barulho ou perturbação"),
    ("PRT-002", "Vandalismo"),
    # === ADMINISTRAÇÃO PÚBLICA ===
    ("ADM-001", "Estabelecimento sem alvará"),
    ("ADM-002", "Jogos de azar"),
    # === FALLBACK ===
    ("OUT-000", "Outros / não classificado"),
]


PROMPT_TEMPLATE = """Você é analista do CompStat Rio (gestão municipal de segurança pública). Extraia informações estruturadas do relato anônimo abaixo do Disque Denúncia.

VOCABULÁRIO DE CLASSIFICAÇÃO (escolha 1 atividade_principal e até 3 secundárias dentre estes IDs):
{vocab}

TEMPLATE DE EXTRAÇÃO (procure no relato):
1. Localização — logradouro mencionado + referência de vizinhança
2. Sujeitos — vulgo/apelido + caracterização ("NAO_IDENTIFICADO" se não há)
3. Atividade principal — o crime central (1 id_canonico)
4. Atividades secundárias — outros crimes mencionados (0..3 ids)
5. Temporalidade — frequência (DIARIA/CRONICA/EVENTUAL/null) + horário aproximado

RELATO (anonimizado, [NOME] = pessoa redactada):
\"\"\"
{relato}
\"\"\"

Responda EXCLUSIVAMENTE com JSON válido (sem markdown, sem comentário) seguindo este schema:
{{
  "localizacao": {{"logradouro": "string ou null", "referencia": "string ou null"}},
  "sujeitos": [{{"vulgo": "string ou null", "caracterizacao": "string"}}],
  "atividade_principal": "id_canonico (ex.: DRG-003)",
  "atividades_secundarias": ["id_canonico", ...],
  "temporalidade": {{"frequencia": "DIARIA|CRONICA|EVENTUAL|null", "horario": "string ou null"}},
  "indicadores_risco": ["string", ...],
  "confidence": 0.0
}}

A confidence deve refletir quão certo você está da classificação (0.0 = palpite, 1.0 = inequívoco). Se o relato é vago ou ambíguo, use < 0.6 — isso roteia pra revisão humana."""


def _build_prompt(relato: str) -> str:
    vocab_lines = "\n".join(f"  • {id_}  {desc}" for id_, desc in VOCAB)
    return PROMPT_TEMPLATE.format(vocab=vocab_lines, relato=relato.strip())


def _parse_llm_response(text: str) -> dict:
    """Strip markdown fences se vierem, parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove primeira linha (```json ou ```) e última (```)
        text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
    return json.loads(text)


def _read_dd_records():
    """Lê disk_denuncia.shp e devolve records com relato + geo + dentro_rio."""
    try:
        import shapefile  # pyshp
    except ImportError:
        print("[s3] ERR: pyshp não instalado. pip install -r requirements.txt", file=sys.stderr)
        raise SystemExit(4)

    if not DD_BASE.with_suffix(".shp").exists():
        print(f"[s3] ERR: {DD_BASE}.shp não existe. Rode step 2 antes.", file=sys.stderr)
        raise SystemExit(5)

    reader = shapefile.Reader(str(DD_BASE), encoding="utf-8")
    field_names = [f[0] for f in reader.fields[1:]]

    rows = []
    for rec in reader.records():
        row = dict(zip(field_names, list(rec)))
        if row.get("dentro_rio") != "S":
            continue
        relato = (row.get("relato") or "").strip()
        if not relato:
            continue
        rows.append(row)
    return rows


def _stub_run(reason: str) -> int:
    """Modo stub: escreve outputs vazios sem custo."""
    now = datetime.now(timezone.utc).isoformat()
    OUT_JSONL.write_text("", encoding="utf-8")
    REVIEW_QUEUE.write_text(
        json.dumps(
            {
                "generated_at": now,
                "status": "stub",
                "reason": reason,
                "pending_items": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[s3] STUB ({reason}) — outputs vazios escritos.")
    print(f"[s3]   {OUT_JSONL.relative_to(REPO_ROOT)}")
    print(f"[s3]   {REVIEW_QUEUE.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 3 — LLM extraction de DD relatos")
    ap.add_argument("--sample", type=int, default=5,
                    help="Quantos relatos processar (default 5 se key existe)")
    ap.add_argument("--all", action="store_true",
                    help="Processa TODOS os relatos (~18k, custoso)")
    ap.add_argument("--stub", action="store_true",
                    help="Força stub mode (não chama LLM mesmo se key existe)")
    args = ap.parse_args()

    # --stub force
    if args.stub:
        return _stub_run("forced via --stub")

    # Lazy import — não força anthropic se vamos cair em stub
    from pipeline_steps._llm_client import (
        is_configured,
        get_client,
        get_model,
        get_max_tokens,
        get_temperature,
        get_threshold,
    )

    # Auto-detect: sem key → stub
    if not is_configured():
        return _stub_run("ANTHROPIC_API_KEY não configurada (esperado em CI sem segredo)")

    # Read DD
    print(f"[s3] Lendo disk_denuncia.shp...")
    records = _read_dd_records()
    total = len(records)
    print(f"[s3]   {total} denúncias com relato + dentro do RJ")

    # Sample logic
    if args.all:
        target = records
        print(f"[s3] Modo --all: processando todos os {total} relatos")
    else:
        target = records[: args.sample]
        print(f"[s3] Modo sample: processando os primeiros {len(target)} de {total}")

    # LLM setup
    client = get_client()
    model = get_model()
    max_tokens = get_max_tokens()
    temperature = get_temperature()
    threshold = get_threshold()

    print(f"[s3] Modelo: {model} (max_tokens={max_tokens}, temp={temperature})")
    print(f"[s3] Threshold de confiança pra revisão humana: {threshold}")
    print()

    results = []
    review_queue = []
    started = time.time()

    for i, rec in enumerate(target, start=1):
        relato = rec["relato"]
        prompt = _build_prompt(relato)

        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            extracted = _parse_llm_response(text)

            # Enriquece com metadados
            extracted["id_denun"] = rec.get("id_denun")
            extracted["num_denun"] = rec.get("num_denun")
            extracted["dt_denun"] = rec.get("dt_denun")
            extracted["bairro"] = rec.get("bairro")
            extracted["latitude"] = rec.get("latitude")
            extracted["longitude"] = rec.get("longitude")
            extracted["llm_model"] = model
            extracted["extracted_at"] = datetime.now(timezone.utc).isoformat()

            confidence = float(extracted.get("confidence", 0.0))
            if confidence < threshold:
                review_queue.append({
                    "id_denun": rec.get("id_denun"),
                    "reason": "low_confidence",
                    "confidence": confidence,
                    "extracted": extracted,
                })

            results.append(extracted)

        except Exception as e:
            review_queue.append({
                "id_denun": rec.get("id_denun"),
                "reason": "extraction_failed",
                "error": str(e)[:300],
                "relato_preview": relato[:120],
            })

        if i % 5 == 0 or i == len(target):
            elapsed = time.time() - started
            avg = elapsed / i
            eta = avg * (len(target) - i)
            print(f"  ...{i}/{len(target)}  (elapsed {elapsed:.0f}s  ETA {eta:.0f}s)")

    # Persist outputs
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    REVIEW_QUEUE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed" if not review_queue else "needs_review",
                "n_processed": len(target),
                "n_extracted_ok": len(results),
                "n_needs_review": len(review_queue),
                "pending_items": review_queue,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n[s3] Done.")
    print(f"[s3]   Extraídos: {len(results)}")
    print(f"[s3]   Fila revisão: {len(review_queue)}")
    print(f"[s3]   Output: {OUT_JSONL.relative_to(REPO_ROOT)}")
    print(f"[s3]   Queue:  {REVIEW_QUEUE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
