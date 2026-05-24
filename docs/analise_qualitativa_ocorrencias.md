# Análise Qualitativa das Ocorrências — ImpactHub CompStat RJ

**Data:** 2026-05-24
**Fontes:** `fatores_urbanos.csv` (8.229 linhas) + `disk_denuncia.csv` (83.549 linhas)
**Objetivo:** Mapear a estrutura das informações qualitativas para propor um vocabulário canônico de 3 níveis para o modelo ELP.

---

## 1. Fatores Urbanos — tipos distintos e estrutura

### 1.1 Confirmação: `ocorrencia_informacao` é lookup, não dado de linha

**Todos os 22 tipos de ocorrência têm exatamente 1 texto único em `ocorrencia_informacao`.**
Não há variação dentro do mesmo `id_tipo_ocorrencia`. Conclusão: este campo é a "bula técnica" do tipo — descreve ao agente de campo *o que observar*, não *o que foi observado*. **Deve migrar para a tabela `vocab_fator_urbano` como `descricao_tecnica`, fora de cada linha da base.**

### 1.2 Tabela de tipos distintos (22 tipos + 1 nulo)

| id | Tipo de Ocorrência | Órgão responsável | Contagem | Ativo |
|---|---|---|---|---|
| 5 | Vegetação obstruindo a visibilidade do passeio | COMLURB | 213 | TRUE |
| 6 | Lixo/entulho forçando pedestres à pista | COMLURB | 25 | TRUE |
| 7 | Área mal iluminada com circulação de pedestres | Rio Luz | 204 | TRUE |
| 8 | Área mal iluminada com parada de veículos | Rio Luz | 27 | TRUE |
| 9 | Mobiliário urbano desviando pedestres para a pista | SECONSERVA | 25 | TRUE |
| 12 | Calçada estreita forçando pedestres à pista | SECONSERVA | 63 | TRUE |
| 13 | Mobiliário/estrutura servindo de esconderijo | SECONSERVA | 36 | TRUE |
| 14 | Comércio irregular obstruindo a visibilidade do passeio | SEOP | 140 | TRUE |
| 15 | Estacionamento irregular forçando pedestres à pista | SEOP | 100 | TRUE |
| 16 | Veículos de grande porte obstruindo a visibilidade | SEOP | 68 | TRUE |
| 19 | Pessoas em situação de rua | SMAS | 285 | TRUE |
| 20 | Cena de uso de drogas | SMAS | 56 | TRUE |
| 21 | Praças e Parques | — | 29 | TRUE |
| 22 | Ponto de retenção do tráfego | CET-Rio | 191 | TRUE |
| 23 | Motocicletas trafegando no passeio | GM-Rio | 84 | TRUE |
| 26 | Ponto de ônibus com histórico de vandalismo | SMTR | 40 | TRUE |
| 27 | Vegetação encobrindo iluminação pública | COMLURB | 327 | TRUE |
| 28 | Lixo/entulho obstruindo a visibilidade | COMLURB | 18 | TRUE |
| 29 | Tapumes servindo de esconderijo | SECONSERVA | 19 | TRUE |
| 34 | Sem ocorrência | — | 62 | TRUE |
| 40 | Mobiliário abandonado servindo de esconderijo | SECONSERVA | 24 | TRUE |
| 41 | Vãos ou cavidades usados como esconderijo | SECONSERVA | 49 | TRUE |

**Total registros com tipo válido:** 8.167 | **"Sem ocorrência":** 62 (0,8%)

### 1.3 Hierarquia implícita por órgão responsável

Os tipos estão naturalmente agrupados pelo **órgão executor da resposta**, o que revela a lógica de **parceria intersetorial** do CompStat:

| Grupo temático | Órgão(s) | Tipos (id) |
|---|---|---|
| **Visibilidade comprometida** | COMLURB, SEOP | 5, 6, 14, 15, 16, 27, 28 |
| **Iluminação deficiente** | Rio Luz | 7, 8 |
| **Esconderijos** | SECONSERVA | 13, 29, 40, 41 |
| **Obstrução de circulação** | SECONSERVA, GM-Rio, CET-Rio | 9, 12, 22, 23 |
| **Vulnerabilidade social** | SMAS | 19, 20 |
| **Transporte público** | SMTR | 26 |
| **Espaço público** | — | 21, 34 |

### 1.4 Campos classificatórios qualitativos dentro do tipo 19 (Pessoas em Situação de Rua)

O tipo **19 (PSR)** tem subcampos que aprofundam o perfil situacional — são os únicos campos verdadeiramente qualitativos de *observação* nesta base (os demais são apenas categorical lookup):

| Campo | Valores observados | Uso analítico |
|---|---|---|
| `tipo_pessoa_descricao` | Adulto / Crianças e/ou adolescentes / Famílias ou casais | Perfil demográfico da cena |
| `ocupacao_pessoa_descricao` | De maneira transitória / Pernoite / Sinais de uso como moradia | **Severidade da ocupação** (escala de 1 a 3) |
| `tipo_frequencia_descricao` | Crônica / Eventual | Persistência do problema |
| `ocupacao_drogas_descricao` | Com sinais de pontos de venda próximos / Sem sinais | **Indicador de mercado varejista de drogas** na cena |

> **Achado para o dashboard:** a combinação `ocupacao = 'Sinais de uso como moradia'` + `frequencia = 'Crônica'` + `ocupacao_drogas = 'Com sinais...'` é um **score implícito de risco** que nunca foi formalizado. O dashboard pode calculá-lo automaticamente e sinalizar como alerta de alta prioridade.

---

## 2. Disk Denuncia — hierarquia de assuntos e estrutura narrativa

### 2.1 Achado crítico: dois sistemas de classificação no mesmo arquivo

O arquivo tem **campos duplicados** resultantes de um flatten de JSON mal resolvido:

| Campo plano (`classe`, `tipo`) | Campo aninhado (`assuntos.classe`, `assuntos.tipos.tipo`) |
|---|---|
| Traz apenas **2 classes** no extrato: CRIMES CONTRA O PATRIMÔNIO e SUBSTÂNCIAS ENTORPECENTES | Traz **19 classes** e ~100 tipos — o catálogo completo do sistema |
| Representa o **assunto principal** (1 por registro) | Representa **todos os assuntos** da denúncia (1-N por registro) |

**Conclusão:** o campo plano é um atalho de leitura rápida para o assunto principal. O campo `assuntos.*` é a fonte de verdade. Para o modelo canônico, usar `assuntos.*` com a flag `assunto_principal = 1` para identificar o tema dominante.

### 2.2 Árvore hierárquica completa — Classe → Tipo (via `assuntos.*`)

```
[1]  CRIMES CONTRA A PESSOA  (14 tipos)
     [1]  HOMICÍDIO CONSUMADO ★
     [2]  TENTATIVA DE HOMICÍDIO ★
     [3]  CEMITÉRIO CLANDESTINO
     [5]  ABORTO
     [6]  LESÃO CORPORAL ★
     [7]  VIOLÊNCIA CONTRA MULHER ★
     [8]  VIOLÊNCIA CONTRA IDOSO ★
     [9]  SEQUESTRO SIMPLES E CÁRCERE PRIVADO ★
     [10] AMEAÇA ★
     [11] PESSOAS DESAPARECIDAS ★
     [109] ENCONTRO DE CADÁVER ★
     [110] SUSPEITA DE CATIVEIRO ★
     [117] OMISSÃO DE SOCORRO
     [144] VIOLÊNCIA CONTRA DEFICIENTES ★

[2]  CRIMES CONTRA O PATRIMÔNIO  (23 tipos)
     [12] EXTORSÃO MEDIANTE SEQUESTRO ★
     [13] EXTORSÃO SIMPLES ★
     [14] ROUBO DE VEÍCULOS AUTOMOTORES ★
     [15] FURTO DE VEÍCULOS AUTOMOTORES ★
     [16] FURTO DE PEÇAS E ACESSÓRIOS VEÍCULOS ★
     [17] VEÍCULOS ABANDONADOS ★
     [18] DESMONTE VEÍCULOS ★
     [19] ROUBO DE CARGA ★
     [20] ROUBO/FURTO A TRANSEUNTES ★
     [21] ROUBO/FURTO A RESIDÊNCIAS ★
     [23] RECEP/COMERC PROD ROUBADOS/FURTADOS ★
     [24] ROUBO A INSTITUIÇÕES FINANCEIRAS ★
     [25] ROUBO EM TRANSP COLETIVOS ★
     [26] ESTELIONATO ★
     [27] FURTO DE COMBUSTÍVEL
     [28] FURTO DE FIOS DE COBRE ★
     [112] ROUBO A MOTORISTAS ★
     [114] SUSPEITA DE ROUBO/FURTO ★
     [145] INVASÃO DE PROPRIEDADE ★
     [146] APROPRIAÇÃO INDÉBITA ★
     [147] LATROCÍNIO ★
     [163] ROUBO/FURTO EST COMERCIAIS ★
     [164] ROUBO/FURTO EST NÃO COMERCIAIS ★

[3]  CRIMES CONTRA A LIBERDADE SEXUAL  (7 tipos)
     [29] ESTUPRO ★ / [31] ATOS OBSCENOS ★ / [33] LENOCÍNIO ★
     [34] TRÁFICO DE MULHERES ★ / [35] ASSÉDIO SEXUAL ★
     [174] CONTEÚDO PORNOGRÁFICO ★ / [183] IMPORTUNAÇÃO SEXUAL ★

[4]  CRIMES CONTRA CRIANÇA E O ADOLESCENTE  (10 tipos)
     [36] PROSTITUIÇÃO INFANTIL ★ / [37] SEDUÇÃO ★ / [38] CORRUPÇÃO DE MENORES ★
     [39] ABANDONO ★ / [40] MAUS TRATOS ★ / [41] TRABALHO FORÇADO ★
     [42] PRESENÇA DE MENORES CASA NOTURNA ★ / [43] VENDA BEBIDAS A MENORES ★
     [44] CRIANÇA E ADOLESCENTE INFRATOR ★ / [45] TRÁFICO DE MENORES ★

[5]  PERTURBAÇÃO DA ORDEM PÚBLICA  (5 tipos)
     [46] BADERNA ★ / [47] BARULHO ★ / [48] VANDALISMO ★
     [49] VADIAGEM ★ / [116] ATENTADO A BOMBA/TERRORISMO

[6]  CRIMES DE TRÂNSITO  (4 tipos)
     [50] PEGA DE VEÍCULOS ★ / [51] DIREÇÃO PERIGOSA ★
     [52] ESTACIONAMENTO IRREGULAR ★ / [53] TRANSPORTE ALTERNATIVO IRREGULAR ★

[7]  CRIMES CONTRA A SAÚDE PÚBLICA  (8 tipos)
     [55] MAU ATEND EST HOSPITALARES ★ / [56] VENDA REMÉDIOS PROIBIDOS ★
     [57] USO/VENDA SUBST QUÍMICAS PROIBIDAS ★ / [58] FALTA HIGIENE EM EST ★
     [59] PRAGA DE RATOS/INSETOS ★ / [60] EPIDEMIAS ★
     [61] VENDA ALIMENTOS FORA VALIDADE / [62] CRIAÇÃO ANIMAIS SEM NORMAS ★

[8]  CRIMES CONTRA A ADMINISTRAÇÃO PÚBLICA  (10 tipos)
     [64] CONTRABANDO / [65] JOGOS DE AZAR ★ / [66] EST COMERCIAL SEM ALVARÁ ★
     [67] OBRA IRREGULAR ★ / [68] USO INDEVIDO VERBAS PÚBLICAS
     [69] USO ILEGAL SERVIÇOS PÚBLICOS ★ / [118] SONEGAÇÃO ★
     [119] DANOS AO PATRIMÔNIO PÚBLICO ★ / [120] RÁDIO/TV CLANDESTINA ★
     [125] OBSTRUÇÃO DE VIAS PÚBLICAS ★

[9]  CRIMES CONTRA A ADM DA JUSTIÇA  (7 tipos)
     [65] JOGOS DE AZAR ★ / [70] FUGA DE PRESIDIÁRIOS
     [73] MAUS TRATOS CONTRA PRESIDIÁRIOS ★ / [74] LOCALIZAÇÃO DE FORAGIDOS ★
     [121] UTILIZAÇÃO DE RÁDIO-TELEFONIA ★ / [180] QUEBRA DE CONDICIONAL ★
     [187] DESCUMPRIMENTO DE MEDIDA PROTETIVA ★

[10] CRIMES CONTRA O MEIO AMBIENTE  (18 tipos)
     [75] POLUIÇÃO DO AR ★ / [76] POLUIÇÃO DAS ÁGUAS ★ / [77] LIXO ACUMULADO ★
     [78] DESMATAMENTO ★ / [79] EXTRAÇÃO IRREGULAR ÁRVORES ★ / [80] QUEIMADAS ★
     [81] BALÕES / [108] CAÇA ILEGAL ANIMAIS ★ / [122] MAUS TRATOS ANIMAIS ★
     [148] GUARDA/COMÉRCIO ANIMAIS SILVESTRES ★ / [165-169] gestão hídrica
     [175] CONTAMINAÇÃO DO SOLO ★ / [176] LOTEAMENTO IRREGULAR ★
     [178] ATERRAMENTO RIO/MANGUE ★ / [181] CONSTRUÇÃO IRREGULAR ★

[11] ARMAS DE FOGO E ARTEFATOS EXPLOSIVOS  (7 tipos)
     [82] POSSE ILÍCITA ARMAS FOGO ★ / [106] USO ILÍCITO ARMAS FOGO ★
     [107] GUARDA/COMÉRCIO ILÍCITO ARMAS FOGO ★
     [126] GUARDA MUNIÇÃO / [127] BOMBA/GRANADA/MORTEIRO
     [184] SIMULACRO ★ / [185] ARMA DE GEL ★

[12] SUBSTÂNCIAS ENTORPECENTES  (4 tipos)
     [83] TRÁFICO DE DROGAS ★ / [84] CONSUMO DE DROGAS ★
     [124] TIROTEIO ENTRE QUADRILHAS / [128] APOLOGIA AO TRÁFICO ★

[13] SUBSTÂNCIAS TÓXICAS/EXPLOSIVAS  (4 tipos) — gás, combustível, fogos, vazamentos

[14] DEFESA DO CIDADÃO  (6 tipos) — discriminação, tortura, mau atendimento, direitos trabalhistas

[15] CALAMIDADE PÚBLICA  (4 tipos) — incêndio, enchentes, desabamento, acidente trânsito

[16] CRIMES PRATICADOS POR FUNC. PÚBLICOS  (6 tipos) — abuso de autoridade, corrupção, desvio de conduta

[17] OUTROS  [105] OUTROS

[18] DAS FALSIFICAÇÕES E ADULTERAÇÕES  (7 tipos) — documentos, produtos, moeda

[19] MAU ATENDIMENTO EM ÔNIBUS  (3 tipos)
```

> ★ = aparece como assunto principal em pelo menos 1 registro do extrato.

### 2.3 Padrões de linguagem nos relatos (estrutura narrativa)

Os 83.549 relatos seguem um **template implícito consistente** com 5 elementos sequenciais:

```
[1. Âncora locacional]
"NO ENDERECO CITADO" / "NA RUA CITADA" / "NO ENDERECO MENCIONADO"
  + referência de vizinhança: "PROXIMO A [ponto de referência conhecido]"

[2. Identificação do alvo/local]
"LOCALIZASE" [estabelecimento / residência / galpão / praça]
  + descriptor físico: cor, portão, andar

[3. Identificação dos sujeitos]
"RESIDE / PODEM SER VISTOS / ENCONTRASE"
  + [NOME] (já redatado na fonte) ou apelido/vulgo
  + caracterização: "NAO CARACTERIZADO/A", "NAO IDENTIFICADO/A"

[4. Atividade denunciada]
"QUE [realiza atividade criminal]" — sempre em presente/habitual
  + tipificação informal: "CONSUMINDO ENTORPECENTES", "PRATICANDO ASSALTOS", "SEM ALVARA"

[5. Contexto temporal/frequência]
"DIARIAMENTE" / "AOS FINAIS DE SEMANA" / "A PARTIR DAS [hora]H"
  + "NESTE MOMENTO" para flagrante
```

**Observações sobre nível de detalhe por classe:**

| Classe | Nível de detalhe | Padrão narrativo dominante |
|---|---|---|
| CRIMES CONTRA A PESSOA | Alto | Vítima + agressor + tipo de violência + contexto de drogas/álcool |
| CRIMES CONTRA O PATRIMÔNIO | Médio | Local + perfil dos autores + horário de ação |
| SUBSTÂNCIAS ENTORPECENTES | Médio-Alto | Endereço exato + descrição da cena + conexão com outros crimes |
| CRIMES CONTRA CRIANÇA/ADO | Alto | Situação de vulnerabilidade detalhada + outros atores envolvidos |
| PERTURBAÇÃO DA ORDEM | Baixo-Médio | Evento + som + horário + estabelecimento comercial |
| ADMIN PÚBLICA | Médio | Estabelecimento + irregularidade + comportamento dos proprietários |
| FUNC. PÚBLICOS | Alto | PM/funcionário identificado por posto + situação + local |
| ARMAS E EXPLOSIVOS | Alto | Tipo de arma + local + contexto de tráfico/milícia |

**Padrão multiassunto:** os relatos frequentemente descrevem **múltiplos crimes no mesmo fato** — p.ex. consumo de drogas + roubo a transeuntes + ruído + menores de idade. Isso explica por que `assuntos.*` tem múltiplos tipos por registro. A flag `assunto_principal = 1` identifica o crime "âncora" da denúncia.

---

## 3. Sobreposição temática entre as duas taxonomias

| # | Fatores Urbanos (tipo + órgão) | Disk Denuncia (classe / tipo) | Tipo de sobreposição |
|---|---|---|---|
| **OV-01** | Cena de uso de drogas [20, SMAS] | [12] SUBST. ENTORPECENTES / [84] CONSUMO DE DROGAS | **Exata** — mesmo fenômeno, perspectivas diferentes (ambiente vs. ato) |
| **OV-02** | Pessoas em situação de rua [19, SMAS] | Classes [1], [2], [12] — contextualização frequente nos relatos | **Contextual** — PSR como ator secundário em múltiplas classes |
| **OV-03** | Estacionamento irregular forçando pedestres [15, SEOP] | [6] CRIMES DE TRÂNSITO / [52] ESTACIONAMENTO IRREGULAR | **Exata** — mesmo fato, um sob ótica urbana, outro sob ótica criminal |
| **OV-04** | Motocicletas trafegando no passeio [23, GM-Rio] | [6] CRIMES DE TRÂNSITO / [51] DIREÇÃO PERIGOSA | **Alta** — prática específica vs. categoria geral |
| **OV-05** | Ponto de ônibus com vandalismo [26, SMTR] | [5] PERTURBAÇÃO / [48] VANDALISMO | **Alta** — alvo específico vs. tipo de crime |
| **OV-06** | Lixo/entulho [6, 28, COMLURB] | [10] MEIO AMBIENTE / [77] LIXO ACUMULADO | **Alta** — lixo como fator de risco (FU) vs. crime ambiental (DD) |
| **OV-07** | Comércio irregular obstruindo visibilidade [14, SEOP] | [8] ADMIN PÚBLICA / [66] EST COMERCIAL/IND SEM ALVARÁ | **Exata** — mesmo estabelecimento, abordagem urbana vs. policial |
| **OV-08** | Praças e Parques [21] | [5] / [10] — mencionados em contexto | **Fraca** — espaço público como palco, não como tipo |
| **SEM PARALELO em DD** | Vegetação obstruindo/encobrindo [5, 27] | — | **Exclusivo FU** — manutenção urbana preventiva, sem equivalente criminal |
| **SEM PARALELO em DD** | Esconderijos [13, 29, 40, 41] | — | **Exclusivo FU** — CPTED, sem equivalente direto |
| **SEM PARALELO em DD** | Iluminação deficiente [7, 8] | — | **Exclusivo FU** — condição ambiental, não evento criminal |
| **SEM PARALELO em FU** | Homicídio, violência sexual, armas, milícia | — | **Exclusivo DD** — crimes graves fora do escopo de mapeamento de campo |

**Insight estrutural:** as duas taxonomias não são concorrentes — são **complementares e intencionalmente distintas**. Fatores Urbanos opera na lógica **CPTED** (prevenção criminal pelo design ambiental): mapeia *condições facilitadoras*. Disk Denuncia opera na lógica **law enforcement**: mapeia *atos e atores*. Os pontos de sobreposição (OV-01 a OV-07) são exatamente os **hotspots analíticos de maior valor para o CompStat**, porque ali existe tanto condição ambiental quanto evento criminal registrado no mesmo espaço.

---

## 4. Vocabulário canônico proposto — 3 níveis

### Metadado de contexto (antes da hierarquia)

Cada entrada no vocabulário carrega um `tipo_perspectiva`:
- `FATOR_AMBIENTAL` — condição física do espaço que facilita crime (origem: FU)
- `EVENTO_CRIMINAL` — ato criminal denunciado ou registrado (origem: DD / ocorrências)
- `VULNERABILIDADE_SOCIAL` — condição de vulnerabilidade de pessoas (origem: FU + CPSR + DD)

### Vocabulário canônico — `vocab_tipo_ocorrencia`

#### CATEGORIA 1 — VIOLÊNCIA

| id_canonico | Categoria | Subcategoria | Tipo canônico | Tipo perspectiva | Origem(s) |
|---|---|---|---|---|---|
| VIO-001 | VIOLÊNCIA | Contra pessoa | Homicídio consumado | EVENTO_CRIMINAL | DD[1/1] |
| VIO-002 | VIOLÊNCIA | Contra pessoa | Tentativa de homicídio | EVENTO_CRIMINAL | DD[1/2] |
| VIO-003 | VIOLÊNCIA | Contra pessoa | Lesão corporal | EVENTO_CRIMINAL | DD[1/6] |
| VIO-004 | VIOLÊNCIA | Contra pessoa | Ameaça | EVENTO_CRIMINAL | DD[1/10] |
| VIO-005 | VIOLÊNCIA | Contra pessoa | Encontro de cadáver | EVENTO_CRIMINAL | DD[1/109] |
| VIO-006 | VIOLÊNCIA | Contra pessoa | Sequestro / cárcere privado | EVENTO_CRIMINAL | DD[1/9] |
| VIO-007 | VIOLÊNCIA | Sexual | Estupro | EVENTO_CRIMINAL | DD[3/29] |
| VIO-008 | VIOLÊNCIA | Sexual | Importunação sexual | EVENTO_CRIMINAL | DD[3/183] |
| VIO-009 | VIOLÊNCIA | Contra vulneráveis | Violência contra mulher | EVENTO_CRIMINAL | DD[1/7] |
| VIO-010 | VIOLÊNCIA | Contra vulneráveis | Violência contra idoso | EVENTO_CRIMINAL | DD[1/8] |
| VIO-011 | VIOLÊNCIA | Contra vulneráveis | Violência contra deficientes | EVENTO_CRIMINAL | DD[1/144] |
| VIO-012 | VIOLÊNCIA | Contra criança/ado | Maus tratos a menores | EVENTO_CRIMINAL | DD[4/40] |
| VIO-013 | VIOLÊNCIA | Contra criança/ado | Prostituição infantil | EVENTO_CRIMINAL | DD[4/36] |
| VIO-014 | VIOLÊNCIA | Func. público | Abuso de autoridade | EVENTO_CRIMINAL | DD[16/100] |
| VIO-015 | VIOLÊNCIA | Func. público | Desvio de conduta policial | EVENTO_CRIMINAL | DD[16/101] |

#### CATEGORIA 2 — PATRIMÔNIO

| id_canonico | Categoria | Subcategoria | Tipo canônico | Tipo perspectiva | Origem(s) |
|---|---|---|---|---|---|
| PAT-001 | PATRIMÔNIO | Roubo a pessoas | Roubo/furto a transeunte | EVENTO_CRIMINAL | DD[2/20], OC[desc=15] |
| PAT-002 | PATRIMÔNIO | Roubo a pessoas | Roubo em transporte coletivo | EVENTO_CRIMINAL | DD[2/25] |
| PAT-003 | PATRIMÔNIO | Roubo a pessoas | Roubo a motoristas | EVENTO_CRIMINAL | DD[2/112] |
| PAT-004 | PATRIMÔNIO | Roubo a residências | Roubo/furto a residências | EVENTO_CRIMINAL | DD[2/21] |
| PAT-005 | PATRIMÔNIO | Roubo a estabelecimentos | Roubo/furto est. comerciais | EVENTO_CRIMINAL | DD[2/163] |
| PAT-006 | PATRIMÔNIO | Veículos | Roubo de veículo | EVENTO_CRIMINAL | DD[2/14] |
| PAT-007 | PATRIMÔNIO | Veículos | Furto de veículo | EVENTO_CRIMINAL | DD[2/15] |
| PAT-008 | PATRIMÔNIO | Veículos | Desmonte de veículo | EVENTO_CRIMINAL | DD[2/18] |
| PAT-009 | PATRIMÔNIO | Extorsão | Extorsão simples | EVENTO_CRIMINAL | DD[2/13] |
| PAT-010 | PATRIMÔNIO | Extorsão | Latrocínio | EVENTO_CRIMINAL | DD[2/147] |

#### CATEGORIA 3 — DROGAS

| id_canonico | Categoria | Subcategoria | Tipo canônico | Tipo perspectiva | Origem(s) |
|---|---|---|---|---|---|
| DRG-001 | DROGAS | Tráfico | Tráfico de drogas | EVENTO_CRIMINAL | DD[12/83] |
| DRG-002 | DROGAS | Tráfico | Apologia ao tráfico | EVENTO_CRIMINAL | DD[12/128] |
| DRG-003 | DROGAS | Consumo | Consumo de drogas (denúncia) | EVENTO_CRIMINAL | DD[12/84] |
| DRG-004 | DROGAS | Consumo | **Cena de uso de drogas (campo)** | FATOR_AMBIENTAL | **FU[20]** ← overlap OV-01 |
| DRG-005 | DROGAS | Associado | Tiroteio entre quadrilhas | EVENTO_CRIMINAL | DD[12/124] |

> DRG-003 e DRG-004 descrevem o mesmo fenômeno sob perspectivas diferentes. No dashboard, um ponto geográfico pode ter **ambos** os registros — essa sobreposição espacial é o maior indicador de risco desta categoria.

#### CATEGORIA 4 — ARMAS

| id_canonico | Categoria | Subcategoria | Tipo canônico | Origem |
|---|---|---|---|---|
| ARM-001 | ARMAS | Posse/porte | Posse ilícita de arma de fogo | DD[11/82] |
| ARM-002 | ARMAS | Comércio | Guarda/comércio ilícito de armas | DD[11/107] |
| ARM-003 | ARMAS | Uso | Uso ilícito de arma de fogo | DD[11/106] |
| ARM-004 | ARMAS | Explosivos | Bomba / granada / morteiro | DD[11/127] |

#### CATEGORIA 5 — INFRAESTRUTURA URBANA *(exclusivo Fatores Urbanos)*

| id_canonico | Categoria | Subcategoria | Tipo canônico | Tipo perspectiva | Origem |
|---|---|---|---|---|---|
| INF-001 | INFRAESTRUTURA | Visibilidade | Vegetação obstruindo visibilidade do passeio | FATOR_AMBIENTAL | FU[5] |
| INF-002 | INFRAESTRUTURA | Visibilidade | Vegetação encobrindo iluminação pública | FATOR_AMBIENTAL | FU[27] |
| INF-003 | INFRAESTRUTURA | Visibilidade | Lixo/entulho obstruindo visibilidade | FATOR_AMBIENTAL | FU[28] |
| INF-004 | INFRAESTRUTURA | Visibilidade | Comércio irregular obstruindo visibilidade | FATOR_AMBIENTAL | FU[14] ← overlap OV-07 |
| INF-005 | INFRAESTRUTURA | Visibilidade | Veículos de grande porte obstruindo visibilidade | FATOR_AMBIENTAL | FU[16] |
| INF-006 | INFRAESTRUTURA | Iluminação | Área mal iluminada — circulação de pedestres | FATOR_AMBIENTAL | FU[7] |
| INF-007 | INFRAESTRUTURA | Iluminação | Área mal iluminada — parada de veículos | FATOR_AMBIENTAL | FU[8] |
| INF-008 | INFRAESTRUTURA | Esconderijos | Mobiliário/estrutura servindo de esconderijo | FATOR_AMBIENTAL | FU[13] |
| INF-009 | INFRAESTRUTURA | Esconderijos | Tapumes servindo de esconderijo | FATOR_AMBIENTAL | FU[29] |
| INF-010 | INFRAESTRUTURA | Esconderijos | Mobiliário abandonado servindo de esconderijo | FATOR_AMBIENTAL | FU[40] |
| INF-011 | INFRAESTRUTURA | Esconderijos | Vãos ou cavidades como esconderijo | FATOR_AMBIENTAL | FU[41] |
| INF-012 | INFRAESTRUTURA | Obstrução circulação | Mobiliário urbano desviando pedestres | FATOR_AMBIENTAL | FU[9] |
| INF-013 | INFRAESTRUTURA | Obstrução circulação | Calçada estreita forçando pedestres à pista | FATOR_AMBIENTAL | FU[12] |
| INF-014 | INFRAESTRUTURA | Obstrução circulação | Lixo/entulho forçando pedestres à pista | FATOR_AMBIENTAL | FU[6] |
| INF-015 | INFRAESTRUTURA | Obstrução circulação | Motocicletas trafegando no passeio | FATOR_AMBIENTAL | FU[23] ← overlap OV-04 |
| INF-016 | INFRAESTRUTURA | Trânsito | Ponto de retenção do tráfego | FATOR_AMBIENTAL | FU[22] |
| INF-017 | INFRAESTRUTURA | Transporte público | Ponto de ônibus com histórico de vandalismo | FATOR_AMBIENTAL | FU[26] ← overlap OV-05 |

#### CATEGORIA 6 — VULNERABILIDADE SOCIAL

| id_canonico | Categoria | Subcategoria | Tipo canônico | Tipo perspectiva | Origem |
|---|---|---|---|---|---|
| VSO-001 | VULN. SOCIAL | Situação de rua | Pessoas em situação de rua (campo) | VULNERABILIDADE_SOCIAL | FU[19] |
| VSO-002 | VULN. SOCIAL | Situação de rua | PSR — moradia (uso crônico do espaço) | VULNERABILIDADE_SOCIAL | FU[19 + subcampos] |
| VSO-003 | VULN. SOCIAL | Criança/adolescente | Abandono de criança | EVENTO_CRIMINAL | DD[4/39] |
| VSO-004 | VULN. SOCIAL | Criança/adolescente | Corrupção de menores | EVENTO_CRIMINAL | DD[4/38] |
| VSO-005 | VULN. SOCIAL | Criança/adolescente | Trabalho forçado / exploração | EVENTO_CRIMINAL | DD[4/41] |

#### CATEGORIAS 7-11 (sumarizado)

| id_canonico | Categoria | Principais tipos | Origem |
|---|---|---|---|
| PRT-00x | PERTURBAÇÃO ORDEM | Barulho, Baderna, Vandalismo, Estacionamento irregular | DD[5], DD[6] ← overlap OV-03/05 |
| AMB-00x | MEIO AMBIENTE | Lixo acumulado, Desmatamento, Poluição | DD[10] ← overlap OV-06 |
| ADM-00x | ADMINISTRAÇÃO PÚBLICA | Est. sem alvará, Obra irregular, Danos a patrimônio público | DD[8] ← overlap OV-07 |
| CAL-00x | CALAMIDADE PÚBLICA | Incêndio, Desabamento, Acidente de trânsito | DD[15] |
| FAL-00x | FALSIFICAÇÕES | Documentos, Moeda, Produtos | DD[18] |

---

## 5. Recomendações para o modelo canônico

### 5.1 Separar `ocorrencia_informacao` de `fatores_urbanos`

**Confirmar:** 100% dos 22 tipos têm exatamente 1 texto em `ocorrencia_informacao`. Mover para `vocab_fator_urbano.descricao_tecnica_agente`. Libera ~100 KB de dados repetidos em cada ingestão.

### 5.2 Formalizar o score implícito de severidade em PSR

Os subcampos do tipo 19 formam um score de 4 dimensões que hoje não está calculado:

```
score_psr = (
  ocupacao_pessoa → [1: transitória, 2: pernoite, 3: moradia]
  + tipo_frequencia → [1: eventual, 2: crônica]
  + ocupacao_drogas → [0: sem sinais, 1: com sinais de boca]
  + tipo_pessoa → bonus se crianças/famílias
)
```

Este score deve ser **computado na ingestão** e ficar na tabela `fator_urbano` como `score_severidade_psr INT`.

### 5.3 Usar `assuntos.*` como fonte de verdade em disk_denuncia

Descartar os campos planos `id_classe`, `classe`, `id_tipo`, `tipo` para análise. Usar apenas os campos `assuntos.*` com join em `vocab_assunto_denuncia`. Os campos planos sobrevivem apenas como `assunto_principal_codigo` e `assunto_principal_descricao` para leitura rápida.

### 5.4 Modelar os relatos como entrada LLM estruturada

A estrutura narrativa consistente dos relatos (5 elementos identificados na §2.3) é o **melhor candidato a extração LLM** do projeto. Um prompt de extração pode sistematicamente retornar:

```json
{
  "localizacao": {"logradouro": "...", "referencia": "..."},
  "sujeitos": [{"descricao": "...", "vulgo": "...", "caracterizacao": "NAO_IDENTIFICADO"}],
  "atividade_principal": "CONSUMO_DROGAS",
  "atividades_secundarias": ["ROUBO_TRANSEUNTE"],
  "temporalidade": {"frequencia": "DIARIA", "horario": "22H"},
  "indicadores_risco": ["MENORES_PRESENTE", "ARMADOS"]
}
```

Esta estruturação automatizada é o passo que conecta o campo `relato_redacted` ao modelo canônico de eventos — e é onde o LLM agrega mais valor analítico.

### 5.5 Campos canônicos novos recomendados

| Campo | Tabela | Tipo | Rationale |
|---|---|---|---|
| `tipo_perspectiva` | `vocab_tipo_ocorrencia` | enum(FATOR_AMBIENTAL, EVENTO_CRIMINAL, VULN_SOCIAL) | Diferencia as duas lógicas de classificação |
| `id_canonico` | `vocab_tipo_ocorrencia` | string(8) | PK do vocabulário unificado |
| `score_severidade_psr` | `fator_urbano` | int(1-6) | Score computado dos subcampos PSR |
| `assunto_principal_flag` | `denuncia_assunto` | bool | Migrado de `assunto_principal='1'` |
| `relato_estruturado` | `denuncia` | JSONB | Saída da extração LLM sobre `relato_redacted` |
| `overlap_cross_fonte` | `local` | bool | Flag: este local tem FU + DD do mesmo tipo? |

---

## 6. Próximos passos desta análise

| # | Ação | Esforço |
|---|---|---|
| 1 | Validar `vocab_tipo_ocorrencia` com CompStat (os 22 tipos FU + hierarquia DD fazem sentido operacional?) | Reunião 1h |
| 2 | Construir tabela `vocab_tipo_ocorrencia` seed no DuckDB com os ~60 ids canônicos propostos | 1 dia |
| 3 | Implementar score PSR na pipeline de ingestão de `fatores_urbanos` | ½ dia |
| 4 | Prototipar extração LLM dos relatos: 100 registros, avaliar qualidade de estruturação | 1 dia |
| 5 | Mapear cross-source: spatial join FU ↔ DD nos 7 pontos de sobreposição — quantos locais têm as duas perspectivas? | 1 dia |
