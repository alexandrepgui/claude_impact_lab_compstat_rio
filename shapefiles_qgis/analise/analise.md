# Análise de Coincidência de Risco — Grade + Áreas da FM

Camadas derivadas que **cruzam os pontos** (ocorrências + Disque Denúncia +
fatores urbanos) e os **convergem em áreas**, para a leitura de
**coincidências de alto risco** do CompStat.

Geradas pelo script `../analise_grade.py`, que lê os shapefiles de pontos já
tratados.

---

## 1. O que foi cruzado

| Camada | Fonte | Pontos usados |
|--------|-------|---------------|
| Ocorrências (mancha criminal) | `ocorrencias.shp` | 115.354 |
| Disque Denúncia (dinâmica) | `disk_denuncia.shp` (só `dentro_rio='S'`) | 17.784 |
| Fatores urbanos | `fatores_urbanos.shp` | 2.085 |

> CPSR e câmeras **não** entram no índice (decisão de escopo). Podem ser
> sobrepostos como camadas separadas no QGIS.

---

## 2. Índice de coincidência (`risco`)

O objetivo não é "onde há mais crime", e sim **onde crime + dinâmica + fator
urbano se sobrepõem**. Por isso o índice premia a co-ocorrência:

```
nrm_x  = contagem da camada x na área, normalizada para 0–1
n_camadas = quantas das 3 camadas têm ≥1 ponto na área (0–3)

risco = média(nrm_ocor, nrm_disq, nrm_fator) × (n_camadas / 3)
```

- O 1º termo (média das normalizadas) mede a **intensidade**.
- O 2º termo (`n_camadas/3`) é o **fator de sobreposição**: vale 1,0 só quando as
  3 camadas estão presentes; cai para 0,67 (2 camadas) e 0,33 (1 camada).

Resultado: uma área com muito furto mas sem denúncia nem fator pontua baixo; o
risco alto aparece onde os três fenômenos coincidem.

**Normalização:** na grade, cada camada é normalizada pelo seu **percentil 95**
das células (reduz o efeito de outliers); nas áreas da FM (só 8), pela camada de
**valor máximo** entre as áreas. Por isso os valores de `risco` da grade e das
áreas **não são diretamente comparáveis** — cada camada é um ranking interno.

---

## 3. Camadas geradas

### 3.1 `grade_risco.shp` — grade ~250 m
Malha quadrada cobrindo o município (célula ≈ 250 m). Apenas células com ≥1 ponto
são gravadas (**7.534 células**). Destas, **229 têm as 3 camadas sobrepostas** —
os hotspots de coincidência.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cell_id` | Texto | Identificador da célula (`coluna_linha`) |
| `n_ocor` | Inteiro | Nº de ocorrências na célula |
| `n_disque` | Inteiro | Nº de denúncias na célula |
| `n_fator` | Inteiro | Nº de fatores urbanos na célula |
| `nrm_ocor` | Real | Ocorrências normalizadas (0–1, p95) |
| `nrm_disq` | Real | Denúncias normalizadas (0–1, p95) |
| `nrm_fator` | Real | Fatores normalizados (0–1, p95) |
| `n_camadas` | Inteiro | Quantas das 3 camadas estão presentes (1–3) |
| `risco` | Real | **Índice de coincidência (0–1)** |

### 3.2 `areas_fm_risco.shp` — áreas da Força Municipal
As 8 áreas operacionais da FM (`../../sh_area_forca`) com as contagens e o índice
agregados por área. Mesmos campos da grade, mais:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `fid` | Inteiro | Id da área (original do shapefile da FM) |
| `nome_area` | Texto | Nome da área de atuação |

Ranking de risco por área (intensidade × sobreposição):

| Área (FM) | Ocor. | Denún. | Fator | risco |
|-----------|------:|-------:|------:|------:|
| Presidente Vargas – Campo de Santana – Central | 4.011 | 231 | 90 | **0,842** |
| Metrô Botafogo – São Clemente – Voluntários | 821 | 86 | 171 | 0,526 |
| Estações São Francisco Xavier – Afonso Pena | 1.507 | 146 | 70 | 0,472 |
| Praia de Botafogo – Marquês de Abrantes | 1.138 | 62 | 146 | 0,469 |
| Rodoviária – Terminal Gentileza – Leopoldina | 1.974 | 134 | 50 | 0,455 |
| Jardim de Alah | 298 | 17 | 148 | 0,338 |
| Rio Sul | 457 | 58 | 72 | 0,262 |
| Campo Grande – Estação de Trem – Calçadão | 294 | 38 | 87 | 0,249 |

---

## 4. Como visualizar no QGIS

### Mapa de calor a partir da grade
1. Adicione `grade_risco.shp`.
2. **Propriedades da Camada → Simbologia → Graduado**, coluna `risco`, método
   *Quebras naturais (Jenks)* ou *Quantil*, rampa de cores (ex.: amarelo→vermelho).
3. **Camada → Estilo → Opacidade** ~70% para sobrepor a um mapa base.
4. Para ver **só os hotspots de coincidência**, filtre
   (**Fonte → Filtro de Feições**) por `"n_camadas" = 3` ou `"risco" > 0.5`.

> Dica: com células contíguas coloridas por `risco`, a grade já funciona como um
> mapa de calor "intersectável" — diferente de um heatmap KDE, aqui cada célula
> carrega os números que explicam a cor.

### Leitura por área da FM
1. Adicione `areas_fm_risco.shp`, simbologia graduada por `risco`.
2. Use rótulos (**Rótulos → `nome_area`**) e a tabela de atributos para o
   comparativo entre áreas — alinhado ao relatório semanal do CompStat.

---

## 5. Reproduzir / ajustar

Rode `python ../analise_grade.py` após (re)gerar os shapefiles de pontos.
Parâmetros fáceis de ajustar no topo do script: `CELL_M` (tamanho da célula) e a
fórmula em `risco()`. Para pesos por camada (ex.: dar mais peso à dinâmica), basta
trocar a média simples por uma média ponderada.

---

*Gerado pelo script `../analise_grade.py`.*
