# Mudanças nesta leva — Bingo semanal + zonas dinâmicas da FM

Resumo do que entra nesta push, para passar ao PM.

---

## TL;DR

- **Antes:** as 8 zonas ótimas de atuação da FM eram **fixas** (calculadas com
  todo o período 2020–2024). O heatmap animava, mas os polígonos não.
- **Agora:** as zonas são **recalculadas semana a semana**, animando junto com
  o heatmap. Os pesos das camadas e das categorias ficam num único arquivo
  JSON, fáceis de editar. Está pronto para receber **novas camadas de dados**
  no índice "bingo" (câmeras, domínio territorial, CPSR, etc.) com 3 passos.

Tudo continua contido em `shapefiles_qgis/`, sem novas dependências (só
`pyshp`). Não toca a pipeline ETL (`pipeline.py` + `pipeline_steps/`).

---

## O que tem de novo

### 1. Motor configurável do bingo semanal — `motor_bingo_semanal.py`

Substitui (sem remover) a v1 estática (`analise_semanal_fm.py`) por uma versão
em que o índice é composto e as zonas mudam a cada semana.

Para cada semana **s** e cada célula **c**:

```
bingo(c, s) = Σ  peso_camada · min( volume_norm(c, s), 1 )

  volume_norm = soma na janela [s-W+1 .. s] / p95 da camada
                (camadas temporais — ocorrências, Disque)
              = soma estática / p95 da camada
                (camadas estáticas — fatores urbanos)
```

A partir do bingo da semana, as zonas saem como antes: top-células que
cobrem 50% do índice → componentes conectados → envoltória → alocação
proporcional dos 600 agentes (somando exatamente 600 em **toda semana**).

**Resultado da run atual:** 262 semanas (2020–2024), média ~7,4 zonas/semana
(varia entre 5 e 10), 600 agentes alocados em cada semana.

### 2. Pesos editáveis — `config_pesos.json`

Um único arquivo controla:

- **Parâmetros globais:** `janela_semanas` (8), `grade_m` (250), `cobertura`
  (0.50), `min_share_zona` (0.01), `n_agentes` (600).
- **Por camada:** `ativa`, `peso` (relativo entre camadas), categoria
  predominante e **`pesos_categoria`** — peso por subtipo.

Exemplo de uso real:

- Para dar **2× mais peso a roubos a transeunte no Disque**: edite
  `pesos_categoria` da camada `disque` → `"ROUBO/FURTO A TRANSEUNTES": 2.0`.
- Para priorizar **falta de iluminação** entre os fatores urbanos:
  `"Área mal iluminada com circulação de pedestres": 2.0`.
- Para **desligar uma camada** durante um teste: `"ativa": false`.

Depois é só rodar `python motor_bingo_semanal.py` e reabrir o HTML.

### 3. Visualização animada renovada — `distribuicao_fm/visualizacao_semanal.html`

Mesmo formato (single-file, Leaflet + heatmap, slider + ► Play + velocidade),
mas agora as **zonas mudam por semana** junto com o heatmap. ~7,6 MB,
abre em duplo clique.

**Validação:** screenshots em `distribuicao_fm/preview_semana0.png` (2020-S01)
e `preview_semana130.png` (2022-S26) — confirmam que os polígonos das zonas
são distintos entre semanas (o motor não está apenas re-renderizando o mesmo
shape).

### 4. Shapefile semanal para QGIS — `distribuicao_fm/zonas_semanais.shp`

Uma feição por (semana, zona). Campos:

| Campo | Tipo | Descrição |
|---|---|---|
| `iso_ano`, `iso_sem` | Inteiro | Ano/semana ISO |
| `sem_ini` | Data | Segunda-feira da semana (Controlador Temporal) |
| `zona_id` | Inteiro | Id da zona dentro da semana |
| `local` | Texto | Bairro dominante (rótulo) |
| `agentes` | Inteiro | Agentes alocados |
| `score` | Real | Pontuação composta da zona |
| `pct` | Real | % do índice da semana concentrado nela |
| `n_cel` | Inteiro | Nº de células |

Animação no QGIS: Propriedades → Temporal → campo `sem_ini`, duração 1 semana,
e usar o Controlador Temporal.

### 5. Documentação

- **`shapefiles_qgis/README.md`** — guia da pasta: o que cada script faz,
  o fluxo recomendado, e **como adicionar uma nova camada ao bingo em 3
  passos** (entrada em `LAYER_SPECS` + bloco em `config_pesos.json`).
- **`shapefiles_qgis/distribuicao_fm/README.md`** — atualizado documentando a
  v2 (semanal/configurável) e mantendo a v1 (estática) como referência.

---

## Arquivos modificados / criados

```
shapefiles_qgis/
├── README.md                              [NOVO — overview da pasta]
├── CHANGES.md                             [NOVO — este arquivo]
├── motor_bingo_semanal.py                 [NOVO — motor v2]
├── config_pesos.json                      [NOVO — pesos editáveis]
├── analise_semanal_fm.py                  [NOVO — v1 estática, referência]
├── gerar_visualizacao.py                  [NOVO — HTML v1, referência]
└── distribuicao_fm/
    ├── README.md                          [ATUALIZADO — v1 + v2]
    ├── zonas_semanais.shp(+shx,dbf,prj,cpg)  [NOVO — saída v2]
    ├── visualizacao_semanal.html          [NOVO — HTML animado v2]
    ├── heatmap_semanal.shp(+...)          [NOVO — saída v1]
    ├── zonas_recomendadas.shp(+...)       [NOVO — saída v1]
    ├── zonas_celulas.shp(+...)            [NOVO — saída v1]
    ├── preview_semana0.png                [NOVO — validação visual]
    └── preview_semana130.png              [NOVO — validação visual]
```

Nada fora de `shapefiles_qgis/`. Sem mudanças na pipeline ETL, no
`README.md` da raiz, em `docs/` ou em `pipeline_steps/`.

---

## Como reproduzir

```
pip install pyshp
python shapefiles_qgis/motor_bingo_semanal.py
# Abrir: shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html
```

Para ajustar pesos: editar `shapefiles_qgis/config_pesos.json` e rodar de
novo.

---

## Próximos passos sugeridos

1. **Plugar camadas novas** ao bingo (câmeras, domínio territorial, CPSR) —
   3 passos por camada, descrito em `README.md`.
2. **Modo de emprego e horário** dos 600 agentes — cruzar `hora` /
   `dia_semana` das ocorrências para repartir cada zona em
   (a pé / moto / viatura).
3. **Conectar ao output da pipeline ETL** (`s5_score.py`) — hoje o motor lê
   diretamente os shapefiles; pode passar a ler a base consolidada produzida
   pela pipeline para alinhar com o restante da equipe.
