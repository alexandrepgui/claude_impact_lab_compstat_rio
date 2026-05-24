# Group 14 — ImpactHub · CompStat Rio

> Solução para o desafio **Segurança Pública (CompStat Rio)** no Claude Impact Lab Rio 2026.

## 👥 Equipe

**Group 14** · **Tema:** Segurança Pública — CompStat Rio
**Membros:** Caio Tranjan · Alexandre Pinheiro Guimarães · Vinicius Henequim · D. Kligcar

---

## 🎯 Resumo da solução

Pipeline **ETL agêntica (LLM-first, humano só audita)** que cruza 5 fontes do CompStat e gera, por **zona × semana**, um **índice BINGO** + **Relatórios Analíticos de Área em `.docx`** no estilo dos RELINTs oficiais.

O BINGO é uma **soma ponderada por camada × categoria** em **janela móvel de 8 semanas**, sobre uma grade de 250 m. As **zonas FM são recalculadas a cada semana** e os **600 agentes** são distribuídos proporcionalmente ao score. Pesos editáveis em `config_pesos.json` sem refactor.

O output final (step 6) é o `.docx` por zona que substitui o relatório que a equipe da Duda hoje monta à mão pra reunião semanal de terça.

---

## 🏗️ Pipeline em 6 passos

```
S1  Load input files          → pipeline_steps/s1_load_inputs.py
S2  Automatic treatments      → pipeline_steps/s2_auto_treatments.py
S3  LLM extraction (DD)       → pipeline_steps/s3_assisted_treatments.py
S4  Consolidated DB (v0+v1)   → pipeline_steps/s4_consolidate.py
S5  Generate score            → pipeline_steps/s5_score.py
S6  Generate report (.docx)   → pipeline_steps/s6_generate_report.py   ← Load
```

Orquestrado por `pipeline.py`. Cada passo é independente, observável, com **audit log JSONL** consumível pela UI web (`ui/pipeline_server.py`).

**Como o Claude é usado:**
- **S3**: extrai estrutura JSON dos relatos do Disque Denúncia (modus operandi, rotas, recepção, horários) classificada num vocabulário canônico de 60 IDs em 3 perspectivas (FATOR · EVENTO · VULNERABILIDADE). Auto-detect: stub sem `ANTHROPIC_API_KEY`, sample 5 default com key.
- **S6**: lê dossiê por zona + RELINT exemplar → gera texto no estilo dos RELINTs oficiais → monta `.docx` com mapa Leaflet (Playwright headless) + texto IA + plano de ação por órgão.
- **Modelo default**: `claude-sonnet-4-6` (econômico).

---

## 🚀 Como rodar

### Setup (uma vez só)
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium    # pra S6 (mapa do relatório)
cp .env.example .env                                # editar e colar ANTHROPIC_API_KEY
```

Smoke test da API key (sem custo):
```bash
.venv/bin/python pipeline_steps/_llm_client.py
```

### CLI
```bash
.venv/bin/python pipeline.py                    # roda S1→S6 em sequência
.venv/bin/python pipeline.py --dry-run          # mostra plano sem executar
.venv/bin/python pipeline.py --only 5           # só rerun do score
.venv/bin/python pipeline.py --from 3           # começa do S3
.venv/bin/python pipeline.py --skip 3           # pula LLM extraction
```

Env vars opcionais: `PIPELINE_LLM_SAMPLE` (S3 sample size), `PIPELINE_REPORT_MAX_ZONAS` (S6 zonas).

### UI local
```bash
make dev   # abre http://127.0.0.1:8787
```

UI permite selecionar steps, rodar, acompanhar logs em tempo real (audit log JSONL), editar pesos do BINGO no `/lab` e baixar os `.docx` gerados na aba `/relatorio`.

### Outputs principais
- `shapefiles_qgis/<fonte>/*.shp` — camadas tratadas (S2)
- `shapefiles_qgis/distribuicao_fm/zonas_semanais.shp` — fact table semanal (S4)
- `score_ranking.json` — ranking S5
- `shapefiles_qgis/distribuicao_fm/relatorios_ia/RA_*.docx` — relatórios finais (S6)
- `pipeline_audit.jsonl` — audit log estruturado (consumido pela UI)

---

## 📐 BINGO score (v1)

Por **célula × semana**, em janela móvel de **8 semanas**:

```
bingo(célula, semana) = Σ peso_camada × Σ (peso_categoria × n_normalizado_p95)
                          ↑
                    ocorrencias=1.0 · disque=0.6 · fatores=0.4
```

Boosts (em `config_pesos.json`): `ROUBO/FURTO A TRANSEUNTES = 2.0` (foco do CompStat) · `Iluminação ruim com pedestres = 2.0` · `CONSUMO DE DROGAS = 0.5`. Premia **coincidência** das 3 camadas, não intensidade isolada.

---

## 🔗 Links

- **Este repo**: https://github.com/alexandrepgui/claude_impact_lab_compstat_rio
- **Repo oficial do desafio**: https://github.com/CompStat-Rio/claude_impact_lab_compstat_rio
- **Regras do hackathon**: https://github.com/taicor-ai/claude-impact-lab-rio

## 📄 Documentação

- [`docs/project-brief.html`](docs/project-brief.html) — contexto do problema, datasets, critérios oficiais
- [`docs/solution.html`](docs/solution.html) — design da solução, pipeline detalhada, decision log
- [`docs/data-inventory.html`](docs/data-inventory.html) — inventário técnico das fontes
- [`docs/ImpactHub_Mapeamento_Canonico.md`](docs/ImpactHub_Mapeamento_Canonico.md) — modelo canônico das entidades
- [`docs/analise_qualitativa_ocorrencias.md`](docs/analise_qualitativa_ocorrencias.md) — análise qualitativa DD + FU
- [`shapefiles_qgis/README.md`](shapefiles_qgis/README.md) — scripts geoespaciais + como adicionar nova camada

## 🎥 Vídeo demo

**BINGO semanal — evolução das zonas ótimas da FM ao longo de 5 anos** (262 semanas, 2020–2024). Heatmap = índice composto por célula da grade. Polígonos = 8 zonas ótimas da Força Municipal **recalculadas a cada semana**, rotuladas por bairro × nº de agentes.

![Visualização semanal — BINGO + Zonas FM](docs/visualizacao_semanal.gif)

Versão interativa: [`shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html`](shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html).

---

## 📚 Sobre o desafio

O **CompStat Municipal** é o modelo de gestão de segurança pública da Prefeitura do Rio, inspirado no CompStat NYPD. Opera sobre 22 áreas prioritárias com a **Força Municipal** (Divisão de Elite da Guarda Municipal, 600 agentes) atuando sobre crime + 20 fatores urbanos coordenados com Comlurb, RioLuz, SEOP, SECONSERVA, SMAS, GM-Rio, CET-Rio e SMTR.

**Problema:** dados em silos, sem cruzamento automatizado. Relatórios semanais da equipe da Duda são montados à mão.

**Nossa solução:** pipeline ETL agêntica que cruza as 5 fontes (ocorrências, Disque Denúncia, RELINTs, fatores urbanos, polígonos FM), identifica **coincidências de alto risco** semanais, e gera automaticamente os Relatórios Analíticos de Área `.docx` no estilo dos RELINTs oficiais — pronto pra subsidiar a reunião de terça.

Briefing completo: [`Briefing_Hackathon_Desenvolvedores_CompStat-2.pdf`](Briefing_Hackathon_Desenvolvedores_CompStat-2.pdf).

---

**CompStat Rio · Group 14 · ImpactHub · Claude Impact Lab Rio 2026**
