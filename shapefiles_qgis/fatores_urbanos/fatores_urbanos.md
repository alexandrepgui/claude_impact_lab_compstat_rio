# Fatores Urbanos — Shapefile

Documentação do shapefile **`fatores_urbanos.shp`**, gerado a partir do CSV
`dados/fatores_urbanos.csv`.

---

## 1. Origem dos dados

| Item | Valor |
|------|-------|
| Arquivo de origem | `dados/fatores_urbanos.csv` |
| Separador | vírgula (`,`) |
| Codificação | UTF-8 |
| Registros (denúncias) | **2.085** |
| Pontos no shapefile | **2.085** (100%) |

Mapeamento em campo dos **fatores urbanos/ambientais** que favorecem o crime
(iluminação deficiente, vegetação encobrindo postes, comércio irregular,
desordem, pessoas em situação de rua etc.), cada um com o **órgão responsável**
pela resolução. É a camada de fatores ambientais do CompStat.

> ⚠️ O CSV tem 8.230 linhas físicas, mas apenas **2.085 registros**: o campo
> `observacao` contém textos longos com quebras de linha. A leitura foi feita
> respeitando o CSV com aspas, resultando em 2.085 ocorrências reais.

Principais fatores (`tp_ocorr`):

| Fator | Registros |
|-------|-----------|
| Vegetação encobrindo iluminação pública | 327 |
| Pessoas em situação de rua | 285 |
| Vegetação obstruindo a visibilidade do passeio | 213 |
| Área mal iluminada com circulação de pedestres | 204 |
| Ponto de retenção do tráfego | 191 |

Órgãos responsáveis (`orgao`): COMLURB (583), SMAS (341), SEOP (308),
Rio Luz (231), SECONSERVA (216), CET-Rio (191), GM-Rio (84), SMTR (40).

---

## 2. ⚠️ Coordenadas invertidas na origem

No CSV, as colunas estão **trocadas** em relação à convenção usual:
- `coordenada_x` contém a **latitude** (ex.: −22,89);
- `coordenada_y` contém a **longitude** (ex.: −43,27).

Na geração do shapefile isso foi corrigido: o ponto é montado como
`(longitude = coordenada_y, latitude = coordenada_x)`. Todos os 2.085 pontos
caem dentro do município do Rio.

---

## 3. Shapefile gerado

| Item | Valor |
|------|-------|
| Arquivo | `fatores_urbanos.shp` (+ `.shx`, `.dbf`, `.prj`, `.cpg`) |
| Tipo de geometria | Ponto (POINT) |
| Sistema de coordenadas | **WGS 84 — EPSG:4326** |
| Codificação da tabela | UTF-8 |
| Feições | 2.085 |
| Extensão (bbox) | lon −43,684 a −43,169 / lat −23,011 a −22,822 |

### Atributos (tabela `.dbf`)

Foram mantidos os campos analíticos; os textos longos de instrução
(`observacao`, `ocorrencia_informacao`) e códigos internos de órgão foram
omitidos. Consulte o CSV original por `id_resp` para esses campos.

| Campo no .shp | Origem no CSV | Tipo | Descrição |
|---------------|---------------|------|-----------|
| `id_resp` | `id_resposta_ocorrencia` | Texto | Identificador da resposta/ocorrência |
| `logradouro` | `logradouro` | Texto | Logradouro |
| `num_porta` | `numero_porta` | Texto | Número |
| `referencia` | `referencia` | Texto | Ponto de referência |
| `bairro` | `bairro_nome` | Texto | Bairro |
| `subarea` | `subarea_nome` | Texto | Subárea (estação/perímetro) |
| `tp_ocorr` | `tipo_ocorrencia_descricao` | Texto | **O fator urbano identificado** |
| `orgao` | `orgao_responsavel` | Texto | Órgão responsável pela resolução |
| `valido` | `valido` | Texto | Flag de validade da ocorrência |
| `tp_pessoa` | `tipo_pessoa_descricao` | Texto | Tipo de pessoa (quando aplicável) |
| `ocup_pess` | `ocupacao_pessoa_descricao` | Texto | Ocupação da pessoa |
| `frequenc` | `tipo_frequencia_descricao` | Texto | Frequência observada |
| `drogas` | `ocupacao_drogas_descricao` | Texto | Descrição de cena de uso de drogas |
| `item_praca` | `item_praca_descricao` | Texto | Item de praça/parque |
| `longitude` | `coordenada_y` | Real | Longitude (graus decimais, WGS84) |
| `latitude` | `coordenada_x` | Real | Latitude (graus decimais, WGS84) |
| `dentro_rio` | *(derivado)* | Texto | `S` se dentro do município do RJ (todos `S`) |

---

## 4. Como usar no QGIS

1. **Camada → Adicionar Camada → Adicionar Camada Vetorial** e selecione
   `fatores_urbanos.shp`.
2. CRS reconhecido automaticamente (EPSG:4326).
3. Categorize a simbologia por `tp_ocorr` (fator) ou `orgao` (responsável).
4. Cruze com `ocorrencias` e `disk_denuncia` para achar **coincidências de alto
   risco** — locais onde crime + fator urbano + denúncia se sobrepõem.

---

*Gerado pelo script `../gerar_shapefiles.py`.*
