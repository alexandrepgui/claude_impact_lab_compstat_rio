# `shapefiles_qgis/` — Tratamentos e análise espacial

Toda a parte **geoespacial** do CompStat Rio vive aqui: scripts Python que
transformam os CSVs/DOCXs de `dados/`+`relints/` em **shapefiles** (para QGIS) e
em **análises de risco** sobre uma grade comum (~250 m). Sem dependências
pesadas — só `pyshp`.

> Os scripts dos passos da pipeline ETL (`s1..s5_*.py`) ficam em
> `../pipeline_steps/`. Esta pasta é a *camada espacial* do trabalho.

---

## 1. Mapa dos scripts

| Script | Função (em uma linha) | Lê | Escreve |
|---|---|---|---|
| `gerar_shapefiles.py` | Converte cada CSV/DOCX em shapefile de pontos | `../dados/*` , `../relints/*` | `<camada>/<camada>.shp` |
| `analise_grade.py` | Grade 250 m + 1º índice de risco (v0) por célula e por área da FM | `<camada>/*.shp` | `analise/grade_risco.shp`, `analise/areas_fm_risco.shp` |
| `analise_semanal_fm.py` | **v1 estática** — heatmap semanal + 8 zonas fixas (todo o período) | `ocorrencias/*.shp`, `disk_denuncia/*.shp`, `fatores_urbanos/*.shp` | `distribuicao_fm/heatmap_semanal.shp`, `zonas_recomendadas.shp`, `zonas_celulas.shp` |
| `gerar_visualizacao.py` | HTML animado para a v1 estática (slider de semanas, zonas fixas) | `distribuicao_fm/heatmap_semanal.shp`, `zonas_recomendadas.shp` | `distribuicao_fm/visualizacao_semanal_estatica.html` *(legado)* |
| **`motor_bingo_semanal.py`** | **v2 configurável** — índice "bingo" composto, **zonas recalculadas a cada semana** | `<camada>/*.shp` + `config_pesos.json` | `distribuicao_fm/zonas_semanais.shp`, `visualizacao_semanal.html` |
| `config_pesos.json` | Pesos editáveis das camadas e categorias do bingo | — | — |
| **`relatorio_zonas.py`** | Compila um dossiê por zona da **última semana** (insumo p/ IA gerar RELINT) | `distribuicao_fm/zonas_semanais.shp` + `<camada>/*.shp` | `distribuicao_fm/relatorio_zonas_{compacto,rico}.{md,json}` |
| **`gerar_relatorios_ia.py`** | Gera **1 .docx por zona** no estilo dos `relints/`: mapa + texto IA (Claude Sonnet 4.6) | `relatorio_zonas_compacto.json` + `zonas_semanais.shp` + camadas de pontos + 1 RELINT exemplar | `distribuicao_fm/relatorios_ia/RA_<N>_<local>.{docx,png}` |

> O fluxo recomendado hoje é: rode `gerar_shapefiles.py` uma vez (gera as
> camadas de pontos) e depois `motor_bingo_semanal.py` toda vez que mudar
> pesos. A v1 estática (`analise_semanal_fm.py` + `gerar_visualizacao.py`) é
> mantida para referência e para análises sem janela móvel.

### Saídas geradas (pasta `distribuicao_fm/`)

| Arquivo | Origem | Tamanho típico |
|---|---|---|
| `zonas_semanais.shp` | motor v2 | ~400 KB |
| `visualizacao_semanal.html` | motor v2 | ~7,6 MB (single file, abrir no navegador) |
| `relatorio_zonas_compacto.{md,json}` | relatorio_zonas | ~80 KB — insumo curto p/ IA |
| `relatorio_zonas_rico.{md,json}` | relatorio_zonas | ~140 KB — insumo detalhado p/ IA |
| `heatmap_semanal.shp` | v1 estática | ~13 MB |
| `zonas_recomendadas.shp` + `zonas_celulas.shp` | v1 estática | < 100 KB |

---

## 2. Como executar

Requisitos: Python 3.10+ e `pyshp`.

```
pip install pyshp
python shapefiles_qgis/gerar_shapefiles.py        # 1× (já materializado no repo)
python shapefiles_qgis/motor_bingo_semanal.py     # toda vez que mudar pesos
python shapefiles_qgis/relatorio_zonas.py         # dossiê da última semana p/ IA
```

A visualização sai em `shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html`
(abrir no navegador — precisa de internet só para o mapa base do OpenStreetMap).

---

## 3. O índice "bingo" semanal (motor v2)

Em **cada semana** e **cada célula** da grade:

```
bingo(c, s) = Σ  peso_camada · min( volume_norm(c, s) , 1 )
             camadas

  onde:
   volume_norm(c, s) = soma da camada na janela [s-W+1 .. s] (se temporal)
                       ÷ p95 da camada (estabilizador)
                     = soma estática (se a camada não tem data, ex.: fatores)
                       ÷ p95 da camada

Cada ponto contribui com (peso_categoria · 1) — categorias listadas em
config_pesos.json mandam, o que faltar usa peso_categoria_default.
```

Daí as **zonas** caem direto: top células que somam `cobertura` do índice da
semana → componentes 8-conexos → envoltória convexa → alocação proporcional
dos 600 agentes. Tudo é refeito **a cada semana** — diferente da v1 estática,
onde as zonas eram fixas pelo período inteiro.

Parâmetros gerais ficam em `config_pesos.json`:

```jsonc
{
  "janela_semanas": 8,       // janela móvel das camadas temporais
  "grade_m": 250,            // tamanho da célula
  "cobertura": 0.50,         // hotspots = células que cobrem X do índice/semana
  "min_share_zona": 0.01,    // descarta zonas com <X do índice
  "n_agentes": 600           // total alocado por semana
}
```

---

## 4. Como ajustar pesos

Edite `config_pesos.json`, bloco `camadas`. Cada camada tem:

| Campo | O que faz |
|---|---|
| `ativa` | `true`/`false` — liga/desliga a camada no bingo |
| `peso` | Peso relativo no índice composto (ex.: ocorrências 1.0, disque 0.6, fatores 0.4) |
| `campo_categoria` | Campo do shapefile que define o subtipo (ex.: `tipo_pr` no Disque) |
| `peso_categoria_default` | Peso usado para subtipos não listados |
| `pesos_categoria` | Dicionário `"subtipo": peso` — sobrescreve o default |

Exemplos prontos no JSON:

- Disque Denúncia: `"ROUBO/FURTO A TRANSEUNTES": 2.0` (duplica) e
  `"CONSUMO DE DROGAS": 0.5` (reduz).
- Fatores urbanos: `"Área mal iluminada com circulação de pedestres": 2.0` e
  `"Vegetação encobrindo iluminação pública": 1.5`.

Depois de editar:

```
python shapefiles_qgis/motor_bingo_semanal.py
```

E reabra o HTML. A run gasta ~30–60 s e imprime, por camada, a escala p95
usada e o total de zonas geradas.

---

## 5. Como adicionar uma nova camada ao bingo

Hoje o motor combina **ocorrências + Disque + fatores urbanos**. Plugar
`cameras/`, `dominio_territorial/`, `cpsr/` (ou qualquer fonte futura) leva
**3 passos** — o motor descobre o resto pelo JSON.

### Passo 1 — Garanta o shapefile de pontos

Confira que existe `shapefiles_qgis/<minha_camada>/<minha_camada>.shp` com
geometria **POINT**. As que vêm do CSV/DOCX original são geradas por
`gerar_shapefiles.py` (basta acrescentar uma função `gerar_<camada>()` lá se
ainda não houver — `cameras/`, `cpsr/`, `dominio_territorial/` já estão
prontos).

### Passo 2 — Acrescente uma entrada em `LAYER_SPECS`

No topo de `motor_bingo_semanal.py`:

```python
LAYER_SPECS = {
    ...
    "cameras": dict(
        path="cameras/cameras",         # sem extensão; relativo a shapefiles_qgis/
        temporal=False,                  # tem campo de data? (True/False)
        date_field=None,                 # nome do campo (None se estática)
        date_fmts=[],                    # formatos possíveis (ex.: ["%d/%m/%Y"])
        cat_field="tipo_camera",         # campo da categoria/subtipo
        only_rio=False,                  # filtra rec["dentro_rio"] == "S"?
    ),
}
```

- **Temporal** = `True` ⇒ a camada entra com janela móvel (soma das W semanas
  anteriores). Recomendado para denúncias/eventos que datam.
- **Temporal** = `False` ⇒ a camada entra com o valor estático em todas as
  semanas. Recomendado para infraestrutura (fatores, câmeras).

### Passo 3 — Acrescente o bloco no `config_pesos.json`

```jsonc
"camadas": {
  ...
  "cameras": {
    "ativa": true,
    "peso": 0.3,
    "campo_categoria": "tipo_camera",
    "peso_categoria_default": 1.0,
    "pesos_categoria": {
      "OCR": 1.5,
      "Domo": 1.0
    }
  }
}
```

Pronto. Rode `motor_bingo_semanal.py` e a nova camada já entra no bingo. Não
há mais nada para mexer no código.

---

## 6. Dossiê por zona — insumo para a IA gerar RELINT

`relatorio_zonas.py` lê `zonas_semanais.shp`, pega a **última semana** e, para
cada polígono daquela semana, compila tudo o que está acontecendo dentro do
contorno: ocorrências, denúncias do Disque (com amostras de relato),
fatores urbanos, câmeras, CPSR e domínio territorial.

Gera 4 arquivos em `distribuicao_fm/`:

- `relatorio_zonas_compacto.json` ← **principal insumo para a IA**
- `relatorio_zonas_compacto.md`   ← versão legível por humano
- `relatorio_zonas_rico.json`     ← versão com séries temporais e mais relatos
- `relatorio_zonas_rico.md`

Cada zona traz: rótulo, centróide, bbox, área, células, agentes, score, %
do índice da semana, e por camada um **top N** de categorias / horários /
dias / logradouros + uma amostra de relatos do Disque (3 no compacto, 10 no
rico). Encoding de DBFs mistos (utf-8 + cp1252) é tratado automaticamente
via `fix_mojibake`.

```
python shapefiles_qgis/relatorio_zonas.py
```

A ideia: a IA recebe um dos JSONs e produz um documento no estilo dos
RELINTs em `relints/` — um relatório por polígono.

---

## 7. Geração automática dos RELINTs (.docx) com Claude

`gerar_relatorios_ia.py` fecha o ciclo: pega o `relatorio_zonas_compacto.json`,
gera **um .docx por zona** no estilo dos arquivos em `relints/`, com:

- um **mapa** Leaflet → screenshot PNG via Edge headless (polígono da zona +
  pontos amostrados de ocorrências, Disque e fatores urbanos no entorno);
- um **texto** redigido pelo **Claude Sonnet 4.6** a partir do dossiê + um
  RELINT real como exemplar de estilo (hard-coded no script).

### Requisitos

```
pip install anthropic python-docx pyshp
set ANTHROPIC_API_KEY=sk-ant-...       # sua chave da Anthropic
```

E ter o **Microsoft Edge** instalado (caminho fixo no topo do script;
ajuste se estiver em outro path).

### Uso

```
# Smoke test — só a zona prioritária #1
python shapefiles_qgis/gerar_relatorios_ia.py

# Todas as 7 zonas da semana
python shapefiles_qgis/gerar_relatorios_ia.py --max-zonas 10

# Específicas (por zona_id)
python shapefiles_qgis/gerar_relatorios_ia.py --zonas 1,3,5
```

Saídas em `distribuicao_fm/relatorios_ia/`:

- `RA_<prio>_<local>.docx` — relatório final (mapa + texto)
- `RA_<prio>_<local>_mapa.png` — imagem do mapa (também embutida no docx)

### Detalhes da chamada do Claude

- **Modelo**: `claude-sonnet-4-6`, `max_tokens=16000`.
- **Prompt caching**: o `SYSTEM_PROMPT` inclui o RELINT exemplar e usa
  `cache_control: ephemeral` — a partir da 2ª zona o exemplar (~6 KB) é lido do
  cache (~0,1× preço), só o dossiê de cada zona é input novo.
- **Anti-alucinação**: o system prompt instrui a usar apenas números reais do
  JSON e a parafrasear (não citar literalmente) os relatos do Disque.
- **API key**: lida de `ANTHROPIC_API_KEY` (não é hardcoded).

### Trocar o exemplar de estilo

O exemplar usado pelo Claude está em `RELINT_EXEMPLAR` no topo do script —
um trecho do `relints/RI_017_Presidente_Vargas_Campo_Santana.docx`. Para
usar outro RELINT como referência, substitua o texto da constante (mantenha
a estrutura: título / parágrafo / sub-locais com bullets / CONCLUSÃO).

---

## 8. Pastas por camada (referência)

Cada subpasta documenta a fonte e o shapefile gerado:

| Camada | Origem | .md de referência |
|---|---|---|
| `ocorrencias/` | `dados/df_ocorrencias_tratado*.csv` | `ocorrencias.md` |
| `disk_denuncia/` | `dados/disk_denuncia.csv` | `disk_denuncia.md` |
| `fatores_urbanos/` | `dados/fatores_urbanos*.csv` | `fatores_urbanos.md` |
| `cameras/` | `dados/cameras_areas_fm.csv` | `cameras.md` |
| `cpsr/` | `dados/outros dados/CPSR_*.xlsx` | `cpsr.md` |
| `dominio_territorial/` | `dados/outros dados/dominio_territorial*.csv` | `dominio_territorial.md` |
| `analise/` | derivado (v0) | `analise.md` |
| `distribuicao_fm/` | derivado (v1 + v2) | `README.md` |

---

## 9. Como animar no QGIS

`distribuicao_fm/zonas_semanais.shp`:

1. **Propriedades → Temporal** → "Configuração temporal dinâmica" → campo
   `sem_ini`, duração **1 semana**.
2. **Ver → Painéis → Controlador Temporal** → passo de 1 semana → ► Play.

Mesmo procedimento serve para `heatmap_semanal.shp` (v1) usando o campo
`sem_ini`.

---

## 10. Limites conhecidos

- O `local` de cada zona é só o **bairro dominante** (pode cruzar divisas).
- Camadas estáticas pesam o mesmo em todas as semanas — é o que faz sentido
  para infraestrutura, mas implica que essas zonas têm um "piso" fixo.
- A alocação dos 600 agentes não considera ainda **modo de emprego** (a pé,
  moto, viatura) nem **horário** — próximo passo, cruzando com `hora` /
  `dia_semana` das ocorrências.
