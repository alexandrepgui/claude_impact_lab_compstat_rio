# Heatmap Semanal + Distribuição da Força Municipal

Duas gerações conviveram aqui:

- **Versão 1 (estática)** — `../analise_semanal_fm.py`: heatmap semanal e
  **8 zonas fixas** desenhadas a partir de **todo o período**.
- **Versão 2 (semanal + configurável)** — `../motor_bingo_semanal.py`: monta um
  **índice composto ("bingo")** das várias camadas com **pesos editáveis** em
  `../config_pesos.json` e **recalcula as zonas a cada semana**.

Tudo em **WGS 84 / EPSG:4326**, grade ~250 m.

---

## Versão 2 — Bingo semanal configurável (recomendada)

### Arquivos gerados

| Arquivo | O que é |
|---|---|
| `zonas_semanais.shp` | Zonas ótimas **recalculadas a cada semana** (animáveis no QGIS) |
| `visualizacao_semanal.html` | Mapa animado: heatmap do bingo + zonas mudando por semana |

### Campos (`zonas_semanais.shp`)

| Campo | Tipo | Descrição |
|---|---|---|
| `iso_ano` | Inteiro | Ano ISO da semana |
| `iso_sem` | Inteiro | Número da semana ISO |
| `sem_ini` | Data | Segunda-feira da semana (para Controlador Temporal) |
| `zona_id` | Inteiro | Id da zona dentro da semana |
| `local` | Texto | Bairro dominante (rótulo) |
| `agentes` | Inteiro | Agentes alocados (soma 600 por semana) |
| `score` | Real | Pontuação composta da zona |
| `pct` | Real | % do índice da semana concentrado nela |
| `n_cel` | Inteiro | Nº de células da zona |

### Como editar os pesos

Abra `../config_pesos.json`. Estrutura:

```jsonc
{
  "janela_semanas": 8,       // janela móvel das camadas temporais (em semanas)
  "grade_m": 250,            // tamanho da célula
  "cobertura": 0.50,         // hotspots = células que cobrem X do índice da semana
  "min_share_zona": 0.01,    // descarta zona com menos que X do índice
  "n_agentes": 600,          // total alocado por semana

  "camadas": {
    "ocorrencias": { "ativa": true, "peso": 1.0, ... },
    "disque":      { "ativa": true, "peso": 0.6, ... },
    "fatores":     { "ativa": true, "peso": 0.4, ... }
  }
}
```

Em cada camada:

- `ativa` — `true/false` para ligar/desligar.
- `peso` — peso da camada no índice composto (relativo às outras).
- `pesos_categoria` — peso por subtipo (ex.: dar `2.0` a
  *"ROUBO/FURTO A TRANSEUNTES"* no Disque, ou `2.0` a *"Área mal iluminada com
  circulação de pedestres"* nos fatores urbanos).
- `peso_categoria_default` — peso usado para o que não estiver listado.

Depois de editar, rode:

```
python ../motor_bingo_semanal.py
```

E reabra `visualizacao_semanal.html`.

### Como funciona o índice composto, em uma frase

Para cada semana e cada célula:
**bingo = Σ (peso_camada × min(volume_normalizado_p95, 1))**, onde o volume das
camadas temporais é a soma na **janela_semanas** anterior. Daí as zonas saem
exatamente como antes (top células → componentes conectados → envoltória),
**mas refeitas a cada semana**.

### Como adicionar uma nova camada (futuro)

1. Gere o shapefile de pontos da nova camada em `shapefiles_qgis/`.
2. Adicione uma entrada em `LAYER_SPECS` no topo de `motor_bingo_semanal.py`
   (caminho, se é temporal, campo de data, campo de categoria).
3. Acrescente o bloco de pesos correspondente em `config_pesos.json`.

Nada mais muda — o motor descobre tudo a partir do JSON.

### Como ver/animar no QGIS

Camada `zonas_semanais.shp`:

1. **Propriedades → Temporal** → "Configuração temporal dinâmica" → campo
   `sem_ini`, duração **1 semana**.
2. **Ver → Painéis → Controlador Temporal** → passo de 1 semana → ► Play.

---

## Versão 1 — Estático (mantida para referência)

Gerada por `../analise_semanal_fm.py`. Mantém o heatmap semanal das ocorrências
e **8 zonas fixas** calculadas a partir de todo o período (2020–2024).

### Arquivos

- `heatmap_semanal.shp` — heatmap semanal das **ocorrências** (mais leve que o
  bingo composto da Versão 2 para análises focadas em crime apenas).
- `zonas_recomendadas.shp` + `zonas_celulas.shp` — 8 zonas fixas e suas células.

**Resultado:** 8 zonas, 32,1% do crime total da cidade, 600 agentes.

| Prioridade | Zona (bairro) | Ocorrências | % do crime | Agentes |
|:---:|---|---:|---:|---:|
| 1 | Centro | 12.344 | 10,8% | **201** |
| 2 | Tijuca | 6.887 | 6,0% | **112** |
| 3 | Madureira | 5.512 | 4,8% | **90** |
| 4 | Méier | 3.938 | 3,4% | **64** |
| 5 | Copacabana | 3.705 | 3,2% | **60** |
| 6 | Pavuna | 1.824 | 1,6% | **30** |
| 7 | Botafogo | 1.341 | 1,2% | **22** |
| 8 | Irajá | 1.256 | 1,1% | **21** |

Campos completos do `zonas_recomendadas.shp`:

| Campo | Tipo | Descrição |
|---|---|---|
| `zona_id` | Inteiro | Id da zona |
| `local` | Texto | Bairro dominante |
| `prioridade` | Inteiro | Ordem por volume de crime |
| `n_celulas` | Inteiro | Nº de células da zona |
| `n_ocor` | Inteiro | Ocorrências na zona |
| `n_disque` | Inteiro | Denúncias na zona |
| `n_fator` | Inteiro | Fatores urbanos na zona |
| `pct_crime` | Real | % do crime total |
| `agentes` | Inteiro | Agentes recomendados |
| `area_km2` | Real | Área aproximada |

---

## Limites e próximos passos

- O `local` é só um rótulo (bairro mais frequente); zona pode cruzar divisas.
- Camadas temporais usam **janela móvel** (default 8 semanas) — uma denúncia
  muito antiga deixa de pesar. Ajustável em `config_pesos.json`.
- Camadas estáticas (fatores urbanos) entram com o mesmo peso em todas as
  semanas — é o que faz sentido para infraestrutura.
- A alocação ainda não considera **modo de emprego** (a pé/moto/viatura) nem
  **horário**. Próximo passo: cruzar com `hora`/`dia_semana` das ocorrências.
