# ImpactHub — Mapeamento Canônico do Dicionário

**Projeto:** ELP CompStat RJ — Camada 1 (Linguagem Unificada) + Camada 2 (Ingestão)
**Data:** 2026-05-24
**Persona-alvo:** Analista de dados CompStat
**Escopo deste documento:** modelo canônico de entidades, vocabulários controlados, matriz de mapeamento campo-a-campo de cada fonte e regras de validação inicial.

---

## 1. Visão executiva — por que canonizar?

As 7 bases atuais do CompStat foram extraídas por equipes diferentes, em momentos diferentes, com convenções diferentes. O resultado é um *patchwork* que dificulta cruzamentos analíticos. Pior: **o próprio Dicionário de dados oficial já diverge dos arquivos reais** em vários pontos (ver §5). Sem uma linguagem unificada:

- Não há chave geográfica única que conecte ocorrências, denúncias, câmeras e fatores urbanos.
- Joins manuais por logradouro/bairro são frágeis (grafia, acentuação, encoding).
- Indicadores agregados são incomparáveis ano a ano e fonte a fonte.
- Cada nova base ingressante reabre a mesma discussão de schema.

**O modelo canônico abaixo é o "contrato"** que congela essas decisões e vira a base de:
1. Templates de upload padronizado (futuro).
2. Regras automáticas do motor de validação (Camada 3).
3. Vocabulário comum do dashboard (Camada 5).

---

## 2. Modelo canônico de entidades

Sete entidades de domínio, mais três tabelas de **vocabulário controlado** (lookups) e uma de **hierarquia geográfica**.

```
              ┌──────────────────────┐
              │ HierarquiaGeografica │◄────────┐
              └──────────────────────┘         │
                       ▲                       │
                       │                       │
   ┌───────────┐   ┌───┴─────┐   ┌──────────┐ │
   │Ocorrencia │   │ Local   │   │ Camera   │ │
   └───────────┘   └─────────┘   └──────────┘ │
                       ▲                       │
       ┌───────────────┼──────────────┐        │
       │               │              │        │
  ┌─────────┐    ┌─────────┐   ┌──────────────┐│
  │Denuncia │    │  Fator  │   │  Territorio  ││
  │         │    │ Urbano  │   │  Orcrim      ││
  └─────────┘    └─────────┘   └──────────────┘│
                       ▲                       │
                       │                       │
              ┌─────────────────┐              │
              │ CensoRua (CPSR) │──────────────┘
              └─────────────────┘
```

### 2.1 Entidades-núcleo (canônicas)

| # | Entidade | Granularidade | Fonte primária | PK canônica |
|---|---|---|---|---|
| 1 | **Ocorrencia** | 1 crime registrado | `df_ocorrencias_tratado` | `ocorrencia_id` (UUID derivado de `id_criptografado`) |
| 2 | **Denuncia** | 1 denúncia anônima ao Disque-Denúncia | `disk_denuncia` | `denuncia_id` (de `id_denuncia`) |
| 3 | **Camera** | 1 ponto de câmera | `cameras_areas_fm` | `camera_id` (de `id_ponto`, já UUID) |
| 4 | **FatorUrbano** | 1 problema urbano mapeado | `fatores_urbanos` | `fator_id` (de `id_resposta_ocorrencia`) |
| 5 | **TerritorioOrcrim** | 1 polígono de domínio territorial | `dominio_territorial` | `territorio_id` (gerado, hash de geometria + nome) |
| 6 | **CensoRua** | 1 pessoa em situação de rua entrevistada | `CPSR_2020_2022_2024` | `cpsr_id` (de `Chave_única`) |
| 7 | **Intervencao** | 1 relatório de intervenção territorial | `RI_*.docx` | `intervencao_id` (de número do documento) |

### 2.2 Entidades de apoio

| # | Entidade | Função |
|---|---|---|
| 8 | **Local** | Ponto geográfico canônico (lat, long, WGS84) atribuído a Ocorrencia/Denuncia/FatorUrbano/Camera/CensoRua via FK |
| 9 | **HierarquiaGeografica** | Tabela única que resolve: município → AISP/RISP → AP → RA → bairro → subbairro → subárea FM. Cada Local recebe todas essas chaves por *spatial join*. |
| 10 | **Vocab_TipoDelito** | Lookup unificada de tipificação penal (código + descrição + categoria) |
| 11 | **Vocab_OrgaoPublico** | Lookup unificada de órgãos (PM, Civil, COMLURB, etc.) |
| 12 | **Vocab_AssuntoDenuncia** | Hierarquia classe → tipo de assunto do Disque-Denúncia |

---

## 3. Schema canônico — campos por entidade

> Convenções: `snake_case`, prefixos por entidade quando útil, datas em ISO-8601, coordenadas em WGS84/EPSG:4326, decimal com `.`, encoding UTF-8, geometrias em WKT.

### 3.1 `ocorrencia`

| Campo canônico | Tipo | Obrigatório | Origem | Transformação |
|---|---|---|---|---|
| `ocorrencia_id` | string | sim | `id_criptografado` | passa direto |
| `data_fato` | date (ISO) | parcial | `data` ou (`ano`,`mes`) | se `data` vazio → 1º dia do `ano`-`mes` com flag `data_estimada=true` |
| `hora_fato` | time | não | `hora` | pode ser nulo |
| `dia_semana` | enum | não | `dia_semana` | normalizar (mai/min) |
| `delito_codigo` | int | sim | `delito` | FK → `vocab_tipodelito.codigo` |
| `delito_descricao` | string | sim | `desc_delito` | validar contra `vocab_tipodelito` |
| `local_id` | FK | sim | derivado | criar Local a partir de (lat,long,locf) |
| `geom` | WKT POINT | sim | `geometria` ou (lat,long) | validar consistência |

### 3.2 `denuncia`

| Campo canônico | Tipo | Obrigatório | Origem | Transformação |
|---|---|---|---|---|
| `denuncia_id` | int | sim | `id_denuncia` | — |
| `numero_denuncia` | string | sim | `numero_denuncia` | — |
| `data_denuncia` | datetime (ISO, TZ=America/Sao_Paulo) | sim | `data_denuncia` | parse `M/D/YYYY H:MM:SS` |
| `data_difusao` | datetime | não | `data_difusao` | idem |
| `local_id` | FK | parcial | (latitude, longitude, endereço) | **converter vírgula→ponto** no decimal |
| `assunto_classe_id` | int | sim | `id_classe` (ou `assuntos.id_classe`) | de-duplicar campos espelhados |
| `assunto_tipo_id` | int | sim | `id_tipo` (ou `assuntos.tipos.id_tipo`) | idem |
| `assunto_principal` | bool | sim | `assunto_principal` | `'1'→true`, `'0'→false` |
| `orgao_id` | int | não | `orgaos.id` | FK → `vocab_orgaopublico` |
| `orgao_tipo` | enum | não | `orgaos.tipo` | `OPERACIONAL` \| `INFORMATIVA` \| outros |
| `envolvido_*` | bloco | não | `envolvidos.*` | mover para tabela filha `denuncia_envolvido` (1-N) |
| `status` | enum | não | `status_denuncia` | normalizar; hoje quase sempre vazio |
| `relato` | text | não | `relato_redacted` | manter; ver §7 para extração LLM |

### 3.3 `camera`

| Campo canônico | Tipo | Obrigatório | Origem | Transformação |
|---|---|---|---|---|
| `camera_id` | UUID | sim | `id_ponto` | já é UUID |
| `area_fm_nome` | string | sim | `nome_area_fm` | FK → `hierarquia_geografica.area_fm` |
| `id_trecho` | int | sim | `id_trecho` | — |
| `geom` | WKT POINT | sim | `geometry` | validar SRID 4326 |

### 3.4 `fator_urbano`

| Campo canônico | Tipo | Obrigatório | Origem | Transformação |
|---|---|---|---|---|
| `fator_id` | int | sim | `id_resposta_ocorrencia` | — |
| `local_id` | FK | sim | (`coordenada_x`,`coordenada_y`,logradouro) | **⚠ trocar eixos: `coordenada_x` contém latitude, `coordenada_y` contém longitude** (ver §5) |
| `tipo_ocorrencia_id` | int | sim | `id_tipo_ocorrencia` | FK → `vocab_fator_urbano` |
| `tipo_ocorrencia_descricao` | string | sim | `tipo_ocorrencia_descricao` | — |
| `bairro_id` / `bairro_nome` | int/string | parcial | `id_bairro`, `bairro_nome` | resolver via hierarquia |
| `subarea_id` / `subarea_nome` | int/string | parcial | `id_subarea`, `subarea_nome` | resolver via hierarquia |
| `orgao_id_responsavel` | int | sim | `id_orgao_ocorrencia` | FK |
| `orgao_nome_responsavel` | string | sim | `ocorrencia_orgao_nome` ou `orgao_responsavel` | resolver duplicação |
| `endereco_informado_pelo_usuario` | bool | sim | `endereco_informado` | `'TRUE'/'FALSE' → bool` |
| `tipo_ativo` | bool | sim | `tipo_ocorrencia_ativo` | idem |
| `valido` | enum | sim | `valido` | `'' → 'NAO_VALIDADO'`, hoje 90%+ vazio |
| `observacao` | text | não | `observacao` | — |
| `descricao_tecnica` | text | não | `ocorrencia_informacao` | descrição do *tipo* (texto repetido por linha; mover para `vocab_fator_urbano`) |

### 3.5 `territorio_orcrim`

| Campo canônico | Tipo | Obrigatório | Origem | Transformação |
|---|---|---|---|---|
| `territorio_id` | UUID | sim | derivado | `sha1(nome\|dominio)` |
| `nome_territorio` | string | sim | `nome_territorio ` | **trim** (espaços extras no header oficial) |
| `dominio_orcrim` | enum | sim | `dominio_orcrim ` | `CV` \| `TCP` \| `ADA` \| `MILICIA` \| `OUTRO` |
| `geom` | WKT POLYGON | sim | `geometria ` | validar SRID + winding order |
| `fonte_referencia` | string | sim | constante | "Direto do Miolo (mapa público)" |

### 3.6 `censo_rua` (CPSR)

Por ter 167 colunas, modelar em **3 tabelas**:

- `censo_rua_pessoa` — cabeçalho (chave, ano, geo, demografia básica)
- `censo_rua_respostas` — formato *long* (`chave_unica`, `bloco`, `campo`, `valor`) — robusto a mudanças de questionário entre 2020/2022/2024
- `censo_rua_indicadores` — visão *wide* gerada para análises rápidas (deficiências, documentação, saúde, drogas, etc.)

Razão: o questionário variou entre anos (campos de pandemia só existem em 2020). Modelo *long* preserva linhagem; visão *wide* preserva ergonomia.

### 3.7 `intervencao` (RI_*.docx)

| Campo canônico | Tipo | Origem | Como obter |
|---|---|---|---|
| `intervencao_id` | string | nome do arquivo (`RI_010_2026`) | regex |
| `numero` | int | nome do arquivo | regex |
| `ano` | int | nome do arquivo | regex |
| `local_referencia` | string | nome do arquivo | regex (`Rodoviaria_Terminal_Gentileza`) |
| `data_intervencao` | date | corpo do .docx | **extração LLM** |
| `orgaos_envolvidos` | array | corpo | extração LLM |
| `objetivo` | text | corpo | extração LLM |
| `acoes_realizadas` | array | corpo | extração LLM |
| `resultados` | text | corpo | extração LLM |
| `geo_referencia` | WKT | corpo + geocoding | extração LLM + Nominatim |

> Esta é a entidade que mais se beneficia da **Camada 4 (LLM)** — o documento é narrativo.

---

## 4. Hierarquia geográfica canônica

Atualmente as bases referenciam **8 sistemas geográficos diferentes** (AISP, RISP, AP, RP, RA, Subprefeitura, bairro/subbairro, Área FM/Subárea FM, território de ORCRIM). Proposta: **um único Local** com todas as chaves resolvidas por spatial join.

### Schema `hierarquia_geografica`

```
local_id (PK)
latitude, longitude, geom (POINT, WGS84)
endereco_textual              ← do logradouro + número
endereco_geocodificado_score  ← 0-1 (qualidade do geocoding)
─── chaves administrativas ───
municipio
estado
codigo_ap            (AP1..AP5)         ← do CPSR
codigo_rp            (5.2, 5.3, …)      ← do CPSR
codigo_ra            (XVIII, XIX, …)    ← do CPSR
subprefeitura        (Zona Oeste, …)    ← do CPSR
bairro_nome          (canonicalizado)
bairro_id            (de fatores_urbanos)
subbairro            (de disk_denuncia)
─── chaves de segurança pública ───
aisp                 (Área Integrada de Segurança Pública / Batalhão PM)
risp                 (Região Integrada)
─── chaves de operação Força Municipal ───
area_fm_nome
subarea_fm_id, subarea_fm_nome
─── chave de inteligência territorial ───
territorio_orcrim_id (FK; pode ser nulo)
```

**Como popular:** spatial join em massa, uma vez por ingestão, contra camadas oficiais de polígonos (AISP, AP, RA, bairro, área FM, ORCRIM). Cache permanente.

---

## 5. ⚠ Inconsistências entre Dicionário oficial e bases reais

> Estas são as descobertas que o dashboard deve **destacar como caso de uso da Camada 3**.

| # | Inconsistência | Severidade | Onde |
|---|---|---|---|
| **5.1** | Dicionário diz `rgocronu`; arquivo real tem `id_criptografado` | Alta — header errado quebra qualquer integração automatizada | `df_ocorrencias_tratado` |
| **5.2** | **Eixos invertidos**: dicionário define `coordenada_x = longitude` e `coordenada_y = latitude`, mas o arquivo real traz `coordenada_x = -22.x` (latitude do RJ) e `coordenada_y = -43.x` (longitude do RJ) | **Crítica** — afeta todo georreferenciamento de fatores urbanos | `fatores_urbanos` |
| **5.3** | Dicionário lista `nome_subarea`; arquivos usam `nome_area_fm` (cameras) e `subarea_nome` (fatores_urbanos) | Alta — três nomes para a mesma coisa | `cameras_areas_fm`, `fatores_urbanos` |
| **5.4** | Encoding misto: `disk_denuncia` em **ISO-8859-1**, demais em UTF-8 | Média — todo texto acentuado vem corrompido se ingerido como UTF-8 | `disk_denuncia` |
| **5.5** | Separador CSV misto: `disk_denuncia` usa `;`, demais usam `,` | Média | `disk_denuncia` |
| **5.6** | Decimal misto em lat/long: `disk_denuncia` usa `,`, demais usam `.` | Média — inviabiliza parse direto | `disk_denuncia` |
| **5.7** | Campos espelhados no mesmo registro: `disk_denuncia` traz `assuntos.id_classe` **e** `id_classe`, `assuntos.tipos.tipo` **e** `tipo`, etc. — resultado de flatten de JSON não tratado | Média — risco de divergência silenciosa | `disk_denuncia` |
| **5.8** | Campo `data` vazio em 100% das amostras inspecionadas; só `ano`+`mes` populados | Alta — perde granularidade diária | `df_ocorrencias_tratado` |
| **5.9** | Campo `valido` vazio em ~todos os registros do `fatores_urbanos` (apesar do dicionário descrevê-lo como crítico para qualidade) | Alta — validação humana não existe operacionalmente | `fatores_urbanos` |
| **5.10** | Booleans em formato string: `'TRUE'`/`'FALSE'` (não 0/1 como dicionário descreve) | Baixa | `fatores_urbanos` |
| **5.11** | Datas em formato US (`M/D/YYYY H:MM:SS`) em base brasileira | Média — ambiguidade nos dias ≤ 12 | `disk_denuncia` |
| **5.12** | Espaços extras nos cabeçalhos do dicionário: `'nome_territorio '`, `'dominio_orcrim '`, `'geometria '` | Baixa — quebra match por nome | `dominio_territorial` (dicionário) |
| **5.13** | Coluna `Possui animal de estimação?` aparece no CPSR só com `None` nas amostras inspecionadas — campo morto ou bloco condicional? | Baixa — investigar | `CPSR` |
| **5.14** | Bloco de saúde do CPSR tem subcampos `Sífilis`, `Outras IST's`, `Hanseníase`, `Problemas psiquiátricos`, `Sarna…` com `None` em 100% das amostras (talvez só aparecem em ano específico) | Média — mudança de questionário entre anos | `CPSR` |
| **5.15** | Tipo penal em dupla representação (`delito=15` + `desc_delito='Roubo a transeunte'`) sem garantia de consistência referencial | Média — gera divergência se um dos dois for editado manualmente | `df_ocorrencias_tratado` |

---

## 6. Vocabulários controlados — proposta de seed

### 6.1 `vocab_tipodelito`

Construir a partir de `delito` + `desc_delito` distintos em `df_ocorrencias_tratado`. Cruzar com a hierarquia de `disk_denuncia` (`assuntos.classe` → `assuntos.tipos.tipo`) para enriquecer com a tipificação de inteligência.

### 6.2 `vocab_orgaopublico`

Seed sugerido (extraído das amostras):

| codigo | nome | tipo | esfera |
|---|---|---|---|
| 338 | 5 BPM | OPERACIONAL | Estadual/PM |
| 497 | SSI / SEPM (PMERJ) | INFORMATIVA | Estadual/PM |
| 1 | COMLURB | OPERACIONAL | Municipal |
| … | … | … | … |

### 6.3 `vocab_assunto_denuncia`

Estrutura hierárquica de 2 níveis (classe → tipo). Seed das amostras:

```
12 SUBSTÂNCIAS ENTORPECENTES
  └─ 84 CONSUMO DE DROGAS
2  CRIMES CONTRA O PATRIMÔNIO
  └─ 20 ROUBO/FURTO A TRANSEUNTES
```

### 6.4 `vocab_fator_urbano`

A partir dos `tipo_ocorrencia_descricao` distintos. Hoje a tabela traz a descrição técnica longa repetida em cada linha — mover para o vocabulário.

### 6.5 `vocab_dominio_orcrim`

`CV`, `TCP`, `ADA`, `MILICIA`, `OUTRO`, `DISPUTA`.

### 6.6 `vocab_hierarquia_administrativa`

5 níveis: AP → RP → RA → Subprefeitura → Bairro. Seed direto do CPSR (já vem com todas as chaves resolvidas por linha — ótimo *ground truth*).

---

## 7. Matriz de mapeamento — visão consolidada

> Para cada base de origem: coluna real → entidade/campo canônico → transformação. Indicações `▲` marcam pontos que **dependem de decisão humana ou regra de validação** (entram na fila do dashboard).

### 7.1 `df_ocorrencias_tratado`

| Coluna origem | Entidade.campo canônico | Transformação |
|---|---|---|
| `id_criptografado` | `ocorrencia.ocorrencia_id` | direto |
| `ano` | `ocorrencia.data_fato` (componente) | combinar com `mes` se `data` vazio |
| `data` | `ocorrencia.data_fato` | parse; ▲ se vazio |
| `mes` | `ocorrencia.data_fato` (componente) | idem |
| `hora` | `ocorrencia.hora_fato` | parse; nulo permitido |
| `delito` | `ocorrencia.delito_codigo` | int; FK |
| `desc_delito` | `ocorrencia.delito_descricao` | ▲ checar consistência com FK |
| `longitude` | `local.longitude` | float |
| `latitude` | `local.latitude` | float |
| `aisp` | `local.aisp` | int; spatial join confirma |
| `risp` | `local.risp` | int |
| `locf` | `local.endereco_textual` | trim |
| `dia_semana` | `ocorrencia.dia_semana` | ▲ recalcular de `data_fato` e comparar |
| `geometria` | `local.geom` | parse WKT; validar contra lat/long |

### 7.2 `disk_denuncia`

| Coluna origem | Entidade.campo canônico | Transformação |
|---|---|---|
| `numero_denuncia` | `denuncia.numero_denuncia` | — |
| `id_denuncia` | `denuncia.denuncia_id` | int |
| `data_denuncia` | `denuncia.data_denuncia` | parse `M/D/YYYY H:MM:SS` em TZ America/Sao_Paulo |
| `data_difusao` | `denuncia.data_difusao` | idem |
| `tipo_logradouro` / `logradouro` / `numero_logradouro` / `complemento_logradouro` | `local.endereco_textual` | concatenar |
| `bairro_logradouro` | `local.bairro_nome` | canonicalizar |
| `subbairro_logradouro` | `local.subbairro` | — |
| `cep_logradouro` | `local.cep` | normalizar 8 dígitos |
| `referencia_logradouro` | `local.referencia` | — |
| `municipio` / `estado` | `local.municipio` / `local.estado` | — |
| `latitude` / `longitude` | `local.latitude` / `local.longitude` | **vírgula→ponto** ▲ |
| `xptos.id` / `xptos.nome` | (descartar — sempre vazio nas amostras) | ▲ confirmar com cliente |
| `orgaos.id` / `orgaos.nome` / `orgaos.tipo` | `denuncia.orgao_id` / FK | — |
| `assuntos.id_classe` / `assuntos.classe` | `denuncia.assunto_classe_id` | ▲ deduplicar com `id_classe`/`classe` |
| `assuntos.tipos.id_tipo` / `assuntos.tipos.tipo` | `denuncia.assunto_tipo_id` | ▲ deduplicar |
| `assuntos.tipos.assunto_principal` | `denuncia.assunto_principal` | string→bool |
| `envolvidos.*` (11 campos) | tabela filha `denuncia_envolvido` | normalizar 1:N |
| `status_denuncia` | `denuncia.status` | hoje quase sempre vazio |
| `timestamp_insercao` | `denuncia.ts_insercao` | parse |
| `id_classe` / `classe` / `tipos.*` / `id_tipo` / `tipo` / `assunto_principal` | **espelhamento** de `assuntos.*` | ▲ resolver divergências |
| `relato_redacted` | `denuncia.relato` | extração LLM separada (entidades, local, modus operandi) |

### 7.3 `cameras_areas_fm`

| Coluna origem | Entidade.campo canônico | Transformação |
|---|---|---|
| `id_ponto` | `camera.camera_id` | UUID |
| `nome_area_fm` | `camera.area_fm_nome` | — |
| `id_trecho` | `camera.id_trecho` | — |
| `geometry` | `camera.geom` + `local.latitude/longitude` | parse WKT |

### 7.4 `fatores_urbanos`

| Coluna origem | Entidade.campo canônico | Transformação |
|---|---|---|
| `id_resposta_ocorrencia` | `fator_urbano.fator_id` | — |
| `logradouro` / `numero_porta` / `referencia` | `local.endereco_textual` | concatenar |
| **`coordenada_x`** | **`local.latitude`** | ⚠ inversão (ver §5.2) |
| **`coordenada_y`** | **`local.longitude`** | ⚠ inversão |
| `observacao` | `fator_urbano.observacao` | — |
| `endereco_informado` | `fator_urbano.endereco_informado_pelo_usuario` | `'TRUE'/'FALSE' → bool` |
| `valido` | `fator_urbano.valido` | enum (default `NAO_VALIDADO`) |
| `id_bairro` / `bairro_nome` | `local.bairro_id` / `local.bairro_nome` | — |
| `id_subarea` / `subarea_nome` | `local.subarea_fm_id` / `local.subarea_fm_nome` | — |
| `id_tipo_pessoa` / `tipo_pessoa_descricao` | `fator_urbano.tipo_pessoa_id` / `_desc` | FK |
| `id_ocupacao_pessoa` / `ocupacao_pessoa_descricao` | idem | FK |
| `id_tipo_frequencia` / `tipo_frequencia_descricao` | idem | FK |
| `ocupacao_drogas` / `ocupacao_drogas_descricao` | idem | FK |
| `id_item_praca` / `item_praca_descricao` | idem | FK |
| `id_tipo_ocorrencia` / `tipo_ocorrencia_descricao` | `fator_urbano.tipo_ocorrencia_id` / `_desc` | FK |
| `tipo_ocorrencia_ativo` | `fator_urbano.tipo_ativo` | string→bool |
| `orgao_responsavel` / `id_orgao_ocorrencia` / `ocorrencia_orgao_nome` / `codigo_ocorrencia_orgao` | `fator_urbano.orgao_*` | ▲ deduplicar 4 campos para 1 órgão |
| `ocorrencia_informacao` | mover para `vocab_fator_urbano.descricao_tecnica` (texto repetido) | refatorar |

### 7.5 `dominio_territorial`

| Coluna origem | Entidade.campo canônico | Transformação |
|---|---|---|
| `nome_territorio ` (trim) | `territorio_orcrim.nome_territorio` | trim |
| `dominio_orcrim ` (trim) | `territorio_orcrim.dominio_orcrim` | enum |
| `geometria ` (trim) | `territorio_orcrim.geom` | parse WKT POLYGON |

### 7.6 `CPSR_2020_2022_2024`

Mapear em 3 tabelas filhas (ver §3.6). Chaves comuns:

| Coluna origem | Entidade.campo canônico |
|---|---|
| `Chave_única` | `censo_rua_pessoa.cpsr_id` |
| `Ano` | `censo_rua_pessoa.ano_censo` |
| `Latitude`, `Longitude` | `local.latitude`, `local.longitude` |
| `Nome do Bairro` | `local.bairro_nome` |
| `Área de Planejamento_3` | `local.codigo_ap` |
| `Código da RP` / `RP` | `local.codigo_rp` / `local.nome_rp` |
| `Código da RA` / `Região Administrativa_4` | `local.codigo_ra` / `local.nome_ra` |
| `Subprefeitura` | `local.subprefeitura` |
| Demais 150+ campos | `censo_rua_respostas` (long) ou `censo_rua_indicadores` (wide) |

---

## 8. Regras de validação iniciais (seed para a Camada 3)

Estas regras viram cards no dashboard. Cada uma com **severidade**, **tipo**, **fonte**, **descrição** e **ação sugerida**.

### Estruturais
- `R001` Campo obrigatório ausente (por campo canônico marcado como `obrigatório`)
- `R002` Encoding incompatível (não-UTF-8 detectado)
- `R003` Separador CSV diferente do declarado

### Tipo/Formato
- `R010` Coordenada fora do bounding box do RJ (`lat ∈ [-23.1,-22.7]`, `long ∈ [-43.8,-43.1]`)
- `R011` Latitude/longitude com vírgula decimal
- `R012` Boolean em formato string não normalizado
- `R013` Data em formato ambíguo M/D/YYYY
- `R014` Eixos lat/long invertidos (heurística: módulo da lat > 90 ou lat positiva no RJ)

### Cross-field
- `R020` `delito_codigo` ↔ `delito_descricao` divergem do `vocab_tipodelito`
- `R021` `data_fato` incoerente com `ano`+`mes`
- `R022` `dia_semana` declarado ≠ recalculado a partir de `data_fato`
- `R023` `assuntos.classe` ≠ `classe` no mesmo registro (espelhamento divergente)

### Cross-source
- `R030` Ponto da ocorrência fora da AISP que declara
- `R031` Câmera fora da Área FM que declara
- `R032` `fator_urbano` cujo bairro declarado é diferente do bairro do spatial join
- `R033` Ocorrência aparenta duplicar denúncia (mesma lat/long ±50m, mesma janela ±24h, mesma classe)

### Vocabulário
- `R040` Valor categórico fora do domínio (lookup miss)
- `R041` Termo livre que provavelmente é o mesmo de outro registro (similaridade textual + LLM, p.ex. `'COMLURB'` vs `'Comlurb'`)

---

## 9. Próximos passos sugeridos

| # | Ação | Entregável | Esforço |
|---|---|---|---|
| 1 | Validar o modelo canônico com o CompStat | Ata de validação | Reunião 1h + 2 dias |
| 2 | Construir o **Dicionário Canônico navegável** (visualização das 12 entidades) | UI estática (HTML/Markdown render) | 2-3 dias |
| 3 | Implementar conector de ingestão piloto (1 fonte: `df_ocorrencias_tratado`) | Notebook + tabela canônica em DuckDB | 3 dias |
| 4 | Popular `vocab_*` a partir das fontes | 5 lookups versionadas | 2 dias |
| 5 | Implementar 8 regras de validação seed (R001, R010, R011, R014, R020, R023, R030, R040) | Motor mínimo + relatório de inconsistências | 5 dias |
| 6 | Mockup do dashboard com dados reais de inconsistência | Wireframes navegáveis | 3 dias |
| 7 | Demo end-to-end para sponsor | Apresentação | 1 dia |

**Total MVP demonstrável: ~3-4 semanas.**

---

## 10. Riscos e dependências

- **Geometrias oficiais** (polígonos de AISP, RA, Área FM, bairros) precisam ser obtidos da Prefeitura/PMERJ. Sem eles, a hierarquia geográfica fica incompleta.
- **Validação semântica do dicionário** com CompStat — várias decisões aqui (especialmente §5.2 sobre eixos invertidos) precisam de confirmação antes de virar regra.
- **Direitos de uso** do `dominio_territorial` (fonte: Direto do Miolo, X) — verificar se pode ser incorporado oficialmente.
- **Versionamento do questionário CPSR** — confirmar com a Prefeitura quais blocos existem em quais anos (afeta §5.14).
