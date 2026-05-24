# Group 14 — ImpactHub · CompStat Rio

> Solução para o desafio de **Segurança Pública (CompStat Rio)** no Claude Impact Lab Rio 2026.

---

## 👥 Equipe

**Time**: Group 14
**Tema**: Segurança Pública — CompStat Rio
**Membros**:
- Caio Tranjan
- Alexandre Pinheiro Guimarães
- Vinicius Henequim
- D. Kligcar
- (+ confirmar 5º membro se houver)

---

## 🎯 Resumo da solução

Pipeline **ETL Transform com human-in-the-loop** que cruza 5 fontes de dados do CompStat, detecta inconsistências (programáticas + agênticas + revisão humana), consolida uma base unificada e calcula um **índice de coincidência de risco** ("BINGO") por área operacional da Força Municipal.

O índice ranqueia as áreas onde **três camadas se sobrepõem**: mancha criminal (ocorrências) ∩ dinâmica criminal (Disque Denúncia + RELINTs) ∩ fator urbano relevante. O output é o insumo direto pra geração dos **Relatórios Analíticos de Área** que hoje a equipe do CompStat monta manualmente para subsidiar as reuniões semanais com o alto escalão da Prefeitura.

**Resultado v0 (atual)**: ranking de risco das 8 áreas FM, com Presidente Vargas–Campo de Santana liderando (0.842). Quando a camada qualitativa (em curso) for plugada, o score recompõe (v1) com dimensões de modus operandi, horário, recepção e controle territorial extraídas via Claude.

---

## 🏗️ Arquitetura e uso do Claude

### Pipeline em 5 passos
```
Step 1: Load input files            → pipeline_steps/s1_load_inputs.py
Step 2: Automatic treatments        → pipeline_steps/s2_auto_treatments.py
Step 3: LLM + human + audit treats  → pipeline_steps/s3_assisted_treatments.py
Step 4: Consolidated database       → pipeline_steps/s4_consolidate.py
Step 5: Generate score              → pipeline_steps/s5_score.py
```

Orquestrado por `pipeline.py` na raiz. Cada passo é um script independente, observável, com audit log JSONL. Suporta `--only`, `--skip`, `--from`, `--dry-run`.

### Como o Claude é usado
- **Step 3 (assisted treatments)**: extração de padrões qualitativos dos relatos do Disque Denúncia e dos RELINTs (.docx) — modus operandi, rotas de fuga, pontos de recepção, horário pico, controle territorial. Cada extração vem com `confidence`; baixo → fila de revisão humana.
- **Julgamento de inconsistências ambíguas**: quando regras determinísticas não decidem, Claude classifica + sugere correção, sempre logada no audit.
- **Modelo default**: Claude Sonnet (econômico). Opus pontualmente em raciocínio crítico.

### Estrutura do código
```
.
├── pipeline.py                    # Orquestrador
├── pipeline_steps/                # 1 script por passo
│   └── s1..s5_*.py
├── shapefiles_qgis/               # Tratamentos + análise espacial (pyshp)
│   ├── gerar_shapefiles.py        # P1+P2: CSV → SHP com correções
│   ├── analise_grade.py           # P4+P5: grid 250m + score v0
│   └── {ocorrencias,disk_denuncia,fatores_urbanos,...}/  # SHP + .md por fonte
├── docs/                          # Documentação de design
└── notebooks/                     # EDA
```

---

## 🚀 Como rodar

### Pré-requisitos
```bash
pip install -r requirements.txt
```

Python 3.11+ recomendado.

### Configurar API key (para step 3 — LLM)
```bash
cp .env.example .env
# Editar .env, colar sua chave Anthropic (obtida em
# https://console.anthropic.com/settings/keys)
```

O `.env` está no `.gitignore` — nunca commita. Testa que a chave foi
carregada:
```bash
python pipeline_steps/_llm_client.py
```

Saída esperada:
```
✓ ANTHROPIC_API_KEY presente (108 chars)
✓ Model:       claude-sonnet-4-5
...
```

### Pipeline completa
```bash
python pipeline.py             # roda os 5 passos em sequência
python pipeline.py --dry-run   # mostra o plano sem executar
```

### UI local da pipeline
```bash
make dev
```

Abra `http://127.0.0.1:8787` para selecionar os steps, rodar dry-run, executar a pipeline e acompanhar logs/status por job. O comando valida a UI, limpa servidores antigos em `8787`/`8765` e reinicia automaticamente quando arquivos da UI mudam.

### Comandos úteis
```bash
python pipeline.py --only 1        # só verifica inputs presentes
python pipeline.py --only 1 2      # carrega + tratamentos automáticos
python pipeline.py --from 4        # começa do consolidate até o final
python pipeline.py --skip 3        # pula assisted treatments (atualmente stub)
```

### Outputs
- `shapefiles_qgis/<fonte>/<fonte>.shp` — uma camada de pontos tratada por fonte
- `shapefiles_qgis/analise/grade_risco.shp` — fact table (grid 250m, 7.534 células)
- `shapefiles_qgis/analise/areas_fm_risco.shp` — 8 áreas FM com score agregado
- `score_ranking.json` — ranking gerado pelo step 5
- `pipeline_audit.jsonl` — audit log (uma entrada JSON por evento)

### Visualizar no QGIS
Abrir `shapefiles_qgis/analise/grade_risco.shp` e `areas_fm_risco.shp` e estilizar por `risco`. Instruções detalhadas em `shapefiles_qgis/analise/analise.md`.

---

## 📐 Conceito do BINGO

```
risco_celula = média(nrm_ocorrencias, nrm_disque, nrm_fator) × (n_camadas / 3)
```

Onde cada `nrm_*` é a contagem da camada na célula, normalizada pelo percentil 95. O fator `n_camadas/3` premia células onde as **três** camadas estão presentes (= 1.0) frente a células com apenas uma (= 0.33). Resultado: alta intensidade isolada não passa — precisa de **coincidência**.

---

## 🔗 Links

- **Repositório**: https://github.com/alexandrepgui/claude_impact_lab_compstat_rio
- **Repo oficial do desafio**: https://github.com/CompStat-Rio/claude_impact_lab_compstat_rio
- **Regras do hackathon**: https://github.com/taicor-ai/claude-impact-lab-rio

## 📄 Documentação

- [`docs/project-brief.html`](docs/project-brief.html) — contexto do problema, datasets, critérios oficiais
- [`docs/solution.html`](docs/solution.html) — design da solução, pipeline detalhada, decision log
- [`docs/data-inventory.html`](docs/data-inventory.html) — inventário técnico das 11 fontes de dados
- [`docs/ImpactHub_Mapeamento_Canonico.md`](docs/ImpactHub_Mapeamento_Canonico.md) — modelo canônico das entidades

## 🎥 Vídeo demo

**BINGO semanal — evolução das zonas ótimas da FM ao longo de ~5 anos** (262 semanas, 2020–2024). Heatmap = índice composto por célula da grade 250 m (janela de 8 semanas, pesos em [`config_pesos.json`](shapefiles_qgis/config_pesos.json)). Polígonos = 8 zonas ótimas da Força Municipal recalculadas a cada semana, rotuladas por bairro × nº de agentes.

![Visualização semanal — BINGO + Zonas FM](docs/visualizacao_semanal.gif)

> Fonte interativa: [`shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html`](shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html) (abrir no browser pra navegar com slider/play).
>
> Pra regenerar o GIF: `python shapefiles_qgis/distribuicao_fm/gerar_gif_demo.py` (requer `playwright` + `python -m playwright install chromium`).

---

## 📚 Sobre o desafio (briefing oficial)

O **CompStat Municipal** é o modelo de gestão de segurança pública da Prefeitura do Rio de Janeiro, inspirado no CompStat NYPD e adaptado à realidade municipal. Combina análise de dados criminais, inteligência territorial e coordenação entre órgãos para orientar decisões operacionais baseadas em evidências. Opera sobre **22 áreas prioritárias** definidas pela mancha criminal de roubo e furto, com emprego estratégico da **Força Municipal** (Divisão de Elite da Guarda Municipal) e atuação sobre **20 fatores urbanos** mapeados (iluminação, vegetação, desordem urbana, obstrução de calçadas, etc.).

**O problema:** os dados vivem em silos distintos (ocorrências georreferenciadas, denúncias qualitativas, fatores urbanos, RELINTs) e não há cruzamento automatizado entre eles. A produção dos relatórios analíticos semanais demanda horas de trabalho manual.

**O objetivo:** plataforma de inteligência criminal com IA que (1) integra as cinco fontes, (2) cruza mancha × dinâmica × fatores urbanos para identificar coincidências de alto risco, (3) gera automaticamente Relatórios Analíticos de Área em `.doc`, e (4) usa IA para recomendar cobertura da FM (rota, horário, modelo de emprego) e resolução dos fatores urbanos pelos órgãos responsáveis (Comlurb, RioLuz, SEOP, SECONSERVA, SMAS, GM-Rio, CET-Rio, SMTR).

Briefing completo: [`Briefing_Hackathon_Desenvolvedores_CompStat-2.pdf`](Briefing_Hackathon_Desenvolvedores_CompStat-2.pdf).

---

**CompStat Rio · Group 14 · ImpactHub · Claude Impact Lab Rio 2026**
