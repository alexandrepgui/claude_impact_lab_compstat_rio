# Domínio Territorial (Facções) — Shapefile

Documentação do shapefile **`dominio_territorial.shp`**, gerado a partir do CSV
`dados/outros dados/dominio_territorial - Extração 1.csv`.

---

## 1. Origem dos dados

| Item | Valor |
|------|-------|
| Arquivo de origem | `dados/outros dados/dominio_territorial - Extração 1.csv` |
| Separador | vírgula (`,`) |
| Codificação | UTF-8 |
| Registros no CSV | 1.628 |
| Polígonos no shapefile | **1.628** (100%) |

Mapeamento dos **territórios sob domínio de organizações criminosas**. Cada linha
é um território (uma favela/comunidade) com a facção dominante e o polígono
correspondente. Usado para contextualizar a dinâmica criminal — influência
territorial, rotas de fuga e fronteiras de disputa.

Distribuição por facção (`faccao`):

| Facção | Territórios |
|--------|-------------|
| CV (Comando Vermelho) | 903 |
| Milícia | 423 |
| TCP (Terceiro Comando Puro) | 229 |
| ADA (Amigos dos Amigos) | 73 |

A geometria vem da coluna `geometria`, em formato WKT `POLYGON((lon lat, ...))`.
Todos os 1.628 registros são polígonos simples (anel único).

---

## 2. ⚠️ Registros fora do Rio de Janeiro (`regiao_rj`)

**17 polígonos** têm coordenadas **fora do estado do RJ** e parecem ser dados de
teste/placeholder na base de origem:

- A maioria tem nomes e coordenadas do **Oriente Médio/Israel** (ex.: "TEL AVIV",
  "FAIXA DE GAZA", "ASHKELON", "HOLON", "METULA", "DAN"), com **longitude
  positiva** (~+34 a +35) — claramente não pertencem ao Rio;
- Um está em **São Paulo** ("JARDIM 9 DE JULHO SP", lon −46,49).

Eles foram **mantidos** no shapefile (conversão fiel), porém marcados com
`regiao_rj = 'N'`. Por causa deles, a extensão (bbox) bruta da camada vai de
−46,5 a +35,7 de longitude — **filtre antes de usar**.

> **Filtro recomendado no QGIS:** `"regiao_rj" = 'S'` para trabalhar apenas com os
> 1.611 territórios dentro do estado do RJ (bbox lon −44,8 a −41,1 /
> lat −23,2 a −21,2). Avalie excluir definitivamente os 17 registros `N`.

---

## 3. Shapefile gerado

| Item | Valor |
|------|-------|
| Arquivo | `dominio_territorial.shp` (+ `.shx`, `.dbf`, `.prj`, `.cpg`) |
| Tipo de geometria | **Polígono (POLYGON)** |
| Sistema de coordenadas | **WGS 84 — EPSG:4326** |
| Codificação da tabela | UTF-8 |
| Feições | 1.628 (1.611 com `regiao_rj='S'`) |

### Atributos (tabela `.dbf`)

| Campo no .shp | Origem no CSV | Tipo | Descrição |
|---------------|---------------|------|-----------|
| `territorio` | `nome_territorio` | Texto | Nome do território/comunidade |
| `faccao` | `dominio_orcrim` | Texto | Organização criminosa dominante (CV, Milícia, TCP, ADA) |
| `regiao_rj` | *(derivado)* | Texto | `S` se dentro do estado do RJ; `N` caso contrário |

---

## 4. Como usar no QGIS

1. **Camada → Adicionar Camada → Adicionar Camada Vetorial** e selecione
   `dominio_territorial.shp`.
2. Em **Propriedades da Camada → Fonte → Filtro de Feições**, aplique
   `"regiao_rj" = 'S'` para remover os 17 polígonos fora do RJ.
3. Categorize a simbologia por `faccao` (cores por organização criminosa).
4. Sobreponha às camadas de ocorrências/denúncias para relacionar a dinâmica
   criminal ao domínio territorial e às fronteiras entre facções.

---

*Gerado pelo script `../gerar_shapefiles.py`.*
