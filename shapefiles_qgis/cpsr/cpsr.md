# Censo de Pessoas em Situação de Rua (CPSR) — Shapefile

Documentação do shapefile **`cpsr.shp`**, gerado a partir da planilha
`dados/outros dados/CPSR_2020_2022_2024.xlsx`.

---

## 1. Origem dos dados

| Item | Valor |
|------|-------|
| Arquivo de origem | `dados/outros dados/CPSR_2020_2022_2024.xlsx` |
| Aba | `Censo_histórico` |
| Colunas na planilha | 167 |
| Registros (pessoas) | 23.332 |
| Pontos no shapefile | **23.332** (100%) |

Censo de Pessoas em Situação de Rua (PSR) da Prefeitura do Rio, realizado a cada
dois anos. Cada linha é uma pessoa entrevistada, georreferenciada. A PSR é um dos
fatores de incidência criminal mapeados pelo CompStat (responsabilidade da SMAS).

Distribuição por ano (`ano`): 2020 (7.272), 2022 (7.865), 2024 (8.195).

---

## 2. 🔒 Privacidade — campos sensíveis NÃO incluídos

A planilha original contém **dados pessoais sensíveis** (CPF, documentos, nomes
de instituições, e condições de saúde como HIV/AIDS, transtornos psiquiátricos,
uso de drogas etc.). Para um arquivo geográfico de análise territorial, **esses
campos foram deliberadamente excluídos**. O shapefile mantém apenas a localização
e atributos demográficos agregáveis (ano, sexo, faixa etária, cor/raça) e a
divisão administrativa.

> Se precisar de variáveis adicionais para uma análise específica, volte à
> planilha original — e avalie as implicações de privacidade antes de
> redistribuir.

---

## 3. Shapefile gerado

| Item | Valor |
|------|-------|
| Arquivo | `cpsr.shp` (+ `.shx`, `.dbf`, `.prj`, `.cpg`) |
| Tipo de geometria | Ponto (POINT) |
| Sistema de coordenadas | **WGS 84 — EPSG:4326** |
| Codificação da tabela | UTF-8 |
| Feições | 23.332 |
| Extensão (bbox) | lon −43,708 a −43,154 / lat −23,053 a −22,785 |

As colunas `Latitude`/`Longitude` da planilha já vêm em graus decimais; todos os
pontos caem dentro do município do Rio.

### Atributos (tabela `.dbf`)

| Campo no .shp | Origem na planilha | Tipo | Descrição |
|---------------|--------------------|------|-----------|
| `chave` | `Chave_única` | Texto | Identificador do registro |
| `ano` | `Ano` | Inteiro | Ano do censo (2020 / 2022 / 2024) |
| `sexo` | `Sexo` | Texto | Sexo |
| `faixa_et` | `Faixa etária` | Texto | Faixa etária (ex.: "18 a 30") |
| `cor_raca` | `Cor_raça` | Texto | Cor/raça |
| `ap` | `Área de Planejamento_3` | Texto | Área de Planejamento (AP1–AP5) |
| `bairro` | `Nome do Bairro` | Texto | Bairro |
| `ra` | `Região Administrativa_4` | Texto | Região Administrativa |
| `subpref` | `Subprefeitura` | Texto | Subprefeitura |
| `longitude` | `Longitude` | Real | Longitude (graus decimais, WGS84) |
| `latitude` | `Latitude` | Real | Latitude (graus decimais, WGS84) |
| `dentro_rio` | *(derivado)* | Texto | `S` se dentro do município do RJ (todos `S`) |

---

## 4. Como usar no QGIS

1. **Camada → Adicionar Camada → Adicionar Camada Vetorial** e selecione
   `cpsr.shp`.
2. CRS reconhecido automaticamente (EPSG:4326).
3. Filtre por `"ano" = 2024` para o censo mais recente, ou compare anos para ver
   a **evolução** da PSR no território.
4. Use **Mapa de Calor** ou agregue por `bairro`/`ra` para identificar
   concentrações — cruzando com fatores urbanos e ocorrências.

---

*Gerado pelo script `../gerar_shapefiles.py`.*
