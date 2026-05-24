# Disque Denúncia — Shapefile

Documentação do shapefile **`disk_denuncia.shp`**, gerado a partir do CSV
`dados/disk_denuncia.csv`.

---

## 1. Origem dos dados

| Item | Valor |
|------|-------|
| Arquivo de origem | `dados/disk_denuncia.csv` |
| Separador | ponto e vírgula (`;`) |
| Codificação original | Windows-1252 (CP1252 / Latin-1) |
| Separador decimal das coordenadas | vírgula (ex.: `-22,899555`) |
| Linhas no CSV | 83.549 |
| **Denúncias distintas** | **18.003** |
| Denúncias com coordenada | 17.850 |
| Pontos no shapefile | **17.850** (1 por denúncia) |

Dados do **Disque Denúncia**, canal anônimo da população. Compõem a análise
*qualitativa* da dinâmica criminal (modus operandi, horários, locais de evasão).

---

## 2. ⚠️ Estrutura do CSV: várias linhas por denúncia

O CSV **não** tem uma linha por denúncia. Ele é um *"explode"* de uma estrutura
JSON: **cada denúncia ocupa um bloco de linhas**.

- A **1ª linha** do bloco (a "linha-cabeçalho") traz os dados únicos da denúncia:
  `id_denuncia`, `numero_denuncia`, datas, endereço, **latitude/longitude**,
  `relato_redacted`, etc.
- As **linhas seguintes** ("linhas-filhas") deixam esses campos **vazios**, mas
  carregam valores **adicionais** das listas aninhadas: `orgaos.*` (cada órgão
  acionado), `assuntos.*` (cada classe/tipo de crime) e `envolvidos.*` (cada
  suspeito descrito).

São 18.003 cabeçalhos e 65.546 linhas-filhas. A mediana é de **5 linhas por
denúncia** (de 1 a 15). Exemplo real (denúncia `2163919`, 5 linhas): envolve
**5 órgãos** (ASSINPOL, 22 BPM, SDDWEB, DRF, SSI/SEPM) e **2 assuntos**
(Consumo de Drogas + Furto de Fios de Cobre).

### Como foi tratado

Cada denúncia foi **reconstituída em um único ponto**, agrupando as linhas pelo
`id_denuncia` propagado para baixo (*forward-fill*). Os campos únicos vêm da
linha-cabeçalho; os campos de lista (órgãos, classes, tipos, envolvidos) são
**consolidados** percorrendo todas as linhas do bloco, com valores distintos
unidos por ` | ` (e ` || ` para envolvidos). Assim **nenhuma informação das
linhas-filhas é perdida**.

> A versão anterior deste shapefile descartava as linhas-filhas e guardava apenas
> o 1º órgão/assunto de cada denúncia. Esta versão consolida tudo.

Estatísticas da consolidação:
- 17.428 denúncias (97%) acionaram **mais de um órgão** (até 15);
- 12.833 têm **mais de uma classe** de crime (até 7);
- 14.101 têm **mais de um tipo** de crime (até 9);
- 3.140 têm **envolvidos descritos** (até 10 por denúncia).

---

## 3. Cobertura geográfica

> Apenas **17.850 das 18.003** denúncias têm latitude/longitude. As 153 sem
> coordenada **não** entram no shapefile (um ponto exige geometria). Para essas,
> seria preciso geocodificar o endereço (`logradouro` + `bairro`).

66 dos 17.850 pontos têm coordenadas **fora** do município do Rio (espalhadas por
outros estados, ex.: latitude −7,28), apesar de `municipio` dizer "RIO DE
JANEIRO" — são erros de geocodificação na origem. Eles foram **mantidos**, porém
marcados com `dentro_rio = 'N'`, para filtragem no QGIS sem perda de dados.

---

## 4. Shapefile gerado

| Item | Valor |
|------|-------|
| Arquivo | `disk_denuncia.shp` (+ `.shx`, `.dbf`, `.prj`, `.cpg`) |
| Tipo de geometria | Ponto (POINT) |
| Sistema de coordenadas | **WGS 84 — EPSG:4326** (graus decimais) |
| Codificação da tabela | UTF-8 (acentuação preservada) |
| Feições (pontos) | 17.850 (uma por denúncia) |

A geometria vem de `latitude`/`longitude` da linha-cabeçalho, com a vírgula
decimal convertida para ponto.

### Atributos (tabela `.dbf`)

Nomes de campo de shapefile têm limite de 10 caracteres; os originais foram
abreviados. Campos de texto têm limite de 254 bytes (truncados quando maiores).

| Campo no .shp | Origem | Tipo | Descrição |
|---------------|--------|------|-----------|
| `num_denun` | `numero_denuncia` | Texto | Número da denúncia |
| `id_denun` | `id_denuncia` | Texto | Identificador da denúncia (chave do agrupamento) |
| `dt_denun` | `data_denuncia` | Texto | Data/hora da denúncia |
| `dt_difus` | `data_difusao` | Texto | Data/hora de difusão aos órgãos |
| `tp_logr` | `tipo_logradouro` | Texto | Tipo de logradouro (R, AV...) |
| `logradouro` | `logradouro` | Texto | Nome do logradouro |
| `num_logr` | `numero_logradouro` | Texto | Número |
| `bairro` | `bairro_logradouro` | Texto | Bairro |
| `subbairro` | `subbairro_logradouro` | Texto | Sub-bairro |
| `cep` | `cep_logradouro` | Texto | CEP |
| `referencia` | `referencia_logradouro` | Texto | Ponto de referência |
| `municipio` | `municipio` | Texto | Município informado |
| `estado` | `estado` | Texto | UF |
| `status` | `status_denuncia` | Texto | Situação (ex.: DIFUNDIDA) |
| `classe_pr` | `classe` (cabeçalho) | Texto | **Classe do assunto principal** |
| `tipo_pr` | `tipo` (cabeçalho) | Texto | **Tipo do assunto principal** |
| `classes` | `assuntos.classe` (todas) | Texto | Todas as classes da denúncia, unidas por ` \| ` |
| `tipos` | `assuntos.tipos.tipo` (todos) | Texto | Todos os tipos da denúncia, unidos por ` \| ` |
| `orgaos` | `orgaos.nome` (todos) | Texto | Todos os órgãos acionados, unidos por ` \| ` |
| `n_orgaos` | *(derivado)* | Inteiro | Quantidade de órgãos distintos |
| `n_classes` | *(derivado)* | Inteiro | Quantidade de classes distintas |
| `n_tipos` | *(derivado)* | Inteiro | Quantidade de tipos distintos |
| `n_envolv` | *(derivado)* | Inteiro | Quantidade de envolvidos descritos |
| `envolvidos` | `envolvidos.*` | Texto | Descrição consolidada dos envolvidos (sexo/idade/pele...), unida por ` \|\| ` |
| `relato` | `relato_redacted` | Texto | Relato anonimizado (**truncado em 254 bytes**) |
| `longitude` | `longitude` | Real | Longitude (graus decimais, WGS84) |
| `latitude` | `latitude` | Real | Latitude (graus decimais, WGS84) |
| `dentro_rio` | *(derivado)* | Texto | `S` se dentro do município do RJ; `N` caso contrário |

> Use `classe_pr`/`tipo_pr` para o **crime principal** da denúncia (1 valor por
> ponto, ideal para categorizar simbologia) e `classes`/`tipos`/`orgaos` quando
> precisar do **conjunto completo**. Para o texto integral do relato (sem o corte
> de 254 bytes) ou a lista detalhada de envolvidos, consulte o CSV original por
> `id_denun`.

---

## 5. Tratamentos aplicados (resumo)

1. **Agrupamento por denúncia** (forward-fill do `id_denuncia`) e consolidação
   dos campos de lista — ver seção 2.
2. **Codificação:** lido em Windows-1252, regravado em UTF-8 (arquivo `.cpg`),
   preservando acentos (ex.: "SUBSTÂNCIAS ENTORPECENTES"). O truncamento de texto
   é feito por bytes, sem partir caracteres acentuados.
3. **Coordenadas:** vírgula decimal convertida para ponto.
4. **Flag `dentro_rio`** para os 66 pontos geocodificados fora do RJ — ver seção 3.

---

## 6. Como usar no QGIS

1. **Camada → Adicionar Camada → Adicionar Camada Vetorial** e selecione
   `disk_denuncia.shp`.
2. CRS reconhecido automaticamente (EPSG:4326).
3. Em **Propriedades da Camada → Fonte → Filtro de Feições**, aplique
   `"dentro_rio" = 'S'` para remover os geocodificados incorretos.
4. Para a dinâmica criminal, categorize a simbologia por `tipo_pr` ou `classe_pr`,
   ou filtre denúncias multi-crime com `"n_tipos" > 1`. Cruze com a camada de
   ocorrências para um mapa de calor da área.

---

*Gerado pelo script `../gerar_shapefiles.py`.*
