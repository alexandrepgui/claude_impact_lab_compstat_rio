# Ocorrências Criminais — Shapefile

Documentação do shapefile **`ocorrencias.shp`**, gerado a partir do CSV
`dados/df_ocorrencias_tratado - Extração 1 .csv`.

---

## 1. Origem dos dados

| Item | Valor |
|------|-------|
| Arquivo de origem | `dados/df_ocorrencias_tratado - Extração 1 .csv` |
| Separador | vírgula (`,`) |
| Codificação | UTF-8 |
| Registros no CSV | 115.354 |
| Registros no shapefile | **115.354** (100%) |

Base tratada de ocorrências criminais de **furto e roubo** no município do Rio de
Janeiro (anos de 2020 a 2024), usada para a análise quantitativa do fenômeno
criminal — a *mancha criminal*. Cada linha é uma ocorrência georreferenciada.

Distribuição por tipo de delito (`desc_delito`):

| Delito | Registros |
|--------|-----------|
| Roubo a transeunte | 69.697 |
| Roubo de aparelho celular | 33.288 |
| Roubo em coletivo | 12.369 |

Distribuição por ano: 2020 (26.870), 2021 (25.931), 2022 (21.890),
2023 (18.077), 2024 (22.586).

---

## 2. Shapefile gerado

| Item | Valor |
|------|-------|
| Arquivo | `ocorrencias.shp` (+ `.shx`, `.dbf`, `.prj`, `.cpg`) |
| Tipo de geometria | Ponto (POINT) |
| Sistema de coordenadas | **WGS 84 — EPSG:4326** (graus decimais) |
| Codificação da tabela | UTF-8 |
| Feições (pontos) | 115.354 |
| Extensão (bbox) | lon −43,747 a −43,159 / lat −23,060 a −22,784 |

A geometria de cada ponto vem das colunas `longitude` e `latitude` do CSV.

### Atributos (tabela `.dbf`)

Os nomes de campo de shapefile têm limite de 10 caracteres, por isso alguns
foram abreviados:

| Campo no .shp | Origem no CSV | Tipo | Descrição |
|---------------|---------------|------|-----------|
| `id_cripto` | `id_criptografado` | Texto | Identificador único (hash) da ocorrência |
| `ano` | `ano` | Inteiro | Ano do registro |
| `data` | `data` | Texto | Data associada ao registro (ver observação 3.2) |
| `mes` | `mes` | Inteiro | Mês (1–12) |
| `hora` | `hora` | Texto | Horário (`HH:MM:SS`), quando disponível |
| `delito` | `delito` | Inteiro | Código numérico do delito |
| `desc_delit` | `desc_delito` | Texto | Descrição do delito |
| `aisp` | `aisp` | Inteiro | Área Integrada de Segurança Pública (batalhão PM) |
| `risp` | `risp` | Inteiro | Região Integrada de Segurança Pública |
| `locf` | `locf` | Texto | Logradouro / local do fato |
| `dia_semana` | `dia_semana` | Texto | Dia da semana |
| `longitude` | `longitude` | Real | Longitude (graus decimais, WGS84) |
| `latitude` | `latitude` | Real | Latitude (graus decimais, WGS84) |
| `coord_fix` | *(derivado)* | Texto | `S` se a coordenada foi reparada; `N` caso contrário |

> A coluna `geometria` do CSV (WKT `POINT(...)`) foi descartada por ser redundante
> com a geometria nativa do shapefile.

---

## 3. Tratamentos aplicados

### 3.1 Reparo de coordenadas sem ponto decimal
36 registros tinham latitude/longitude sem o separador decimal
(ex.: `-22806` em vez de `-22.806`; `-43225` em vez de `-43.225`). Quando o valor
absoluto da latitude excedia 90 (ou da longitude excedia 180), ele foi dividido
por 1.000 para recuperar a posição correta. Esses pontos ficam marcados com
`coord_fix = 'S'`. Nenhum registro foi descartado.

### 3.2 Observação sobre o campo `data`
O campo `data` no CSV de origem contém valores inconsistentes (datas muito
antigas, ex.: `26/03/1924`), aparentemente não correspondentes à data do fato.
Para análise temporal confiável, **prefira os campos `ano` e `mes`**. O campo
`data` foi preservado como texto apenas para rastreabilidade.

---

## 4. Como usar no QGIS

1. **Camada → Adicionar Camada → Adicionar Camada Vetorial** e selecione
   `ocorrencias.shp`.
2. O CRS será reconhecido automaticamente como EPSG:4326 (via `.prj`). Se o
   projeto estiver em outro CRS, o QGIS reprojeta em tempo real.
3. Para mapas de calor da mancha criminal, use
   **Propriedades da Camada → Simbologia → Mapa de Calor (Heatmap)**.
4. Para filtrar por tipo/ano, use o seletor de feições com expressões como
   `"desc_delit" = 'Roubo a transeunte' AND "ano" = 2024`.

---

*Gerado pelo script `../gerar_shapefiles.py`.*
