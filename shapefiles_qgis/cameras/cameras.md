# Câmeras nas Áreas da FM — Shapefile

Documentação do shapefile **`cameras.shp`**, gerado a partir do CSV
`dados/cameras_areas_fm.csv`.

---

## 1. Origem dos dados

| Item | Valor |
|------|-------|
| Arquivo de origem | `dados/cameras_areas_fm.csv` |
| Separador | vírgula (`,`) |
| Codificação | UTF-8 |
| Registros no CSV | 985 |
| Pontos no shapefile | **985** (100%) |

Localização das câmeras de videomonitoramento nas áreas de atuação da Força
Municipal (FM). Útil para o **Desafio 4 — Otimização de Cobertura de Câmeras**
(identificar pontos cegos: locais com crime e sem câmera). São 9 áreas da FM
distintas no arquivo.

A geometria vem da coluna `geometry`, em formato WKT `POINT (lon lat)`.

---

## 2. Shapefile gerado

| Item | Valor |
|------|-------|
| Arquivo | `cameras.shp` (+ `.shx`, `.dbf`, `.prj`, `.cpg`) |
| Tipo de geometria | Ponto (POINT) |
| Sistema de coordenadas | **WGS 84 — EPSG:4326** |
| Codificação da tabela | UTF-8 |
| Feições | 985 |
| Extensão (bbox) | lon −43,564 a −43,171 / lat −22,986 a −22,876 |

### Atributos (tabela `.dbf`)

| Campo no .shp | Origem no CSV | Tipo | Descrição |
|---------------|---------------|------|-----------|
| `id_ponto` | `id_ponto` | Texto | Identificador (UUID) do ponto de câmera |
| `nome_area` | `nome_area_fm` | Texto | Nome da área da Força Municipal |
| `id_trecho` | `id_trecho` | Texto | Identificador do trecho |
| `longitude` | da geometria | Real | Longitude (graus decimais, WGS84) |
| `latitude` | da geometria | Real | Latitude (graus decimais, WGS84) |

---

## 3. Como usar no QGIS

1. **Camada → Adicionar Camada → Adicionar Camada Vetorial** e selecione
   `cameras.shp`.
2. CRS reconhecido automaticamente (EPSG:4326).
3. Para detectar pontos cegos, sobreponha com a camada `ocorrencias` e use
   **Vetor → Ferramentas de Análise → Buffer** nas câmeras (ex.: raio de
   cobertura) e depois um *diferença/seleção por localização* para achar crimes
   fora do alcance.
4. Categorize por `nome_area` para visualizar a distribuição por área da FM.

---

*Gerado pelo script `../gerar_shapefiles.py`.*
