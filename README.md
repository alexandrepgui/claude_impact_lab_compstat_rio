# 🏙️ Claude Impact Lab Rio — CompStat Rio

Repositório de dados e protótipo desenvolvidos para o Claude Impact Lab Rio, com foco em segurança pública e inteligência territorial na cidade do Rio de Janeiro.

---

## 🎯 O Desafio

**Arquivo de referência:** `Briefing_Hackathon_Desenvolvedores_CompStat.pdf`

O CompStat Municipal é o modelo de gestão de segurança pública da Prefeitura do Rio de Janeiro. Inspirado no CompStat do NYPD e adaptado à realidade municipal, ele combina análise de dados criminais, inteligência territorial e coordenação entre órgãos para orientar decisões operacionais baseadas em evidências. O modelo opera sobre 22 áreas prioritárias, definidas com base nas manchas criminais de roubo e furto, com emprego estratégico da Força Municipal (Divisão de Elite da Guarda Municipal - FM) e atuação sobre fatores urbanos que favorecem o crime (20 fatores mapeados), como iluminação, vegetação, desordem urbana, obstrução de calçadas, entre outros. Enquanto a FM irá realizar o policiamento ostensivo e preventivo nas áreas de maior incidência de furto e roubo, os órgãos municipais (Comlurb, SECONSERVA, SMAS, RioLuz, SEOP, Guarda Municipal, dentre outros) irão priorizar a resolução dos fatores ambientais nos polígonos de atuação da FM.

O briefing disponibilizado explica de forma mais detalhada o modelo de gestão do CompStat e como ele é aplicado hoje na prática, incluindo, em anexo, um exemplo de Relatório produzido para informar as reuniões semanais, produzido por área de atuação da FM. 

**O problema:** Os dados vivem em silos distintos (ocorrências georreferenciadas, denúncias qualitativas, fatores urbanos, relatórios de inteligência) e não há cruzamento automatizado entre eles (mancha criminal, fatores urbanos e dinâmica criminal). Portanto, a produção dos relatórios analíticos que subsidiam as reuniões semanais de CompStat (focada nas decisões de alta gestão do município para segurança pública) demanda horas de trabalho manual de compilação, análise e formatação.  

**O objetivo:** desenvolver uma plataforma de inteligência criminal com IA que:

1. Integre automaticamente as cinco fontes de dados do CompStat (ocorrências de furto e roubo, Disque Denúncia, Relatórios de Inteligência - RELINTs, fatores urbanos de incidência criminal e polígonos de atuação da Força Municipal - FM);
2. Cruze a mancha criminal (quantitativa - registros de ocorrência georreferenciadas) com fatores urbanos e dinâmica criminal (qualitativa - composta pelo RELINT e Disque Denúncia) para identificar **coincidências de alto risco** — áreas onde crime, fator ambiental e dinâmica criminal se sobrepõem e, portanto, devem ser priorizadas;
3. Gere automaticamente os **Relatórios Analíticos de Área** em .doc, baseados no formato já utilizado pelo CompStat, incluindo resumo executivo, análise temporal, dinâmica criminal e plano de ação com responsáveis;
4. Utilizar a IA para sugerir (1) a cobertura da FM com base na mancha e dinâmica criminais, incluindo horário de patrulhamento e modelo de emprego — moto, viatura ou a pé, considerando a restrição de 600 agentes disponíveis para operação em todas as áreas, (por exemplo, a FM deve atuar a R. Presidente Vargas, priorizando o emprego do efetivo a pé em torno da Uruguaiana, considerando que a maior parte dos furtos e roubos se valem da alta circulação de pessoas no passeio); e (2) a resolução dos fatores urbanos pelos órgãos responsáveis (por exemplo, Comlurb deve realizar podas cobrindo a iluminação na R. Uruguaiana).

O papel da IA é amplificar a capacidade analítica da equipe — processando síntese qualitativa, cruzamento geoespacial e geração de recomendações — para que os analistas foquem na interpretação e na tomada de decisão, não na montagem de planilhas.

---

## 📂 Estrutura do Repositório

```
claude_impact_lab_compstat_rio/
├── dados/                                                        # Datasets principais
│   ├── cameras_areas_fm.csv                                      # Localização de câmeras nas áreas da FM
│   ├── df_ocorrencias_tratado - Extração 1.csv                   # Ocorrências criminais
│   ├── disk_denuncia.csv                                         # Disk Denúncia
│   ├── fatores_urbanos.csv                                       # Fatores ambientais/urbanos
│   ├── Dicionário de dados.xlsx                                  # Dicionário de todos os datasets
│   └── outros dados/                                             # Dados complementares
│       ├── CPSR_2020_2022_2024.xlsx                              # Censo de Pessoas em Situação de Rua
│       └── dominio_territorial - Extração 1.csv                  # Domínio territorial (facções)
├── relints/                                                      # Relatórios de Inteligência (RELINTs)
│   ├── RI_010_2026_Rodoviaria_Terminal_Gentileza.docx
│   ├── RI_011_2026_Metro_Botafogo_Sao_Clemente.docx
│   ├── RI_012_2026_Jardim_de_Alah.docx
│   ├── RI_013_2026_Campo_Grande_Estacao_Calcadao.docx
│   ├── RI_014_2026_Rio_Sul.docx
│   ├── RI_015_2026_Praia_Botafogo_Marques_Abrantes.docx
│   ├── RI_016_2026_Estacoes_SFX_Afonso_Pena.docx
│   └── RI_017_2026_Presidente_Vargas_Campo_Santana.docx
├── sh_area_forca/                                                # Shapefiles das áreas da Força Municipal
│   ├── areas_forca_municipal.shp
│   ├── areas_forca_municipal.shx
│   ├── areas_forca_municipal.dbf
│   ├── areas_forca_municipal.prj
│   ├── areas_forca_municipal.cpg
│   └── areas_forca_municipal.qmd
├── Briefing_Hackathon_Desenvolvedores_CompStat.pdf               # Briefing técnico do desafio
```
---

## 📊 Datasets

### Ocorrências Criminais
**Arquivo:** `df_ocorrencias_tratado - Extração 1.csv`

Base de dados tratada contendo registros de ocorrências criminais de furto e roubo, incluindo tipificação, localização, data/hora e demais informações relevantes para análise criminal. Esta base é utilizada para realizar análise quantitativa dos fenômenos criminais e a mancha criminal. 

### Disque Denúncia
**Arquivo:** `disk_denuncia.csv`

Dados provenientes do serviço Disque Denúncia, canal de denúncias anônimas da população. Contém registros de denúncias recebidas com suas respectivas categorizações e localizações. Esta base é usada para compor análise da dinâmica criminal (por exemplo, os roubos em determinada área acontecem majoritariamente à noite, com o uso de motocicletas e emprego de arma de fogo, com evasão no Campo de Santana). 

### Fatores Urbanos / Ambientais
**Arquivo:** `fatores_urbanos - Extração 1 (1).csv`

Dados sobre fatores ambientais e urbanos que podem influenciar a dinâmica criminal, como iluminação, infraestrutura, ocupação do solo e outras variáveis contextuais (por exemplo, em determinada rua com alta incidência de furtos no período noturno há lâmpadas quebradas e árvores cobrindo postes; mobiliário urbano abandonado ou bueiro servindo como esconderijo; retenção de tráfego facilitando a fuga a pé; comércio irregular obstruindo a visibilidade e forçando o pedestre à via, aumentando o risco de abordagens; calçada estreita forçando o pedestre à via).  

#### 🏛️ Matriz de Fatores Urbanos e Órgãos Responsáveis

A tabela abaixo apresenta os fatores de incidência criminal mapeados pelo CompStat, quem os registra em campo e o órgão responsável pela resolução.

| Registrado por | Categoria | Fator | Órgão Responsável por resolver|
|----------------|-----------|-------|--------------------|
| **CET-Rio** | Trânsito | Ponto de retenção de tráfego | CET-Rio |
| | Trânsito | Motocicletas trafegando no passeio | GM-Rio |
| | Trânsito | Estacionamento irregular forçando pedestres à pista | SEOP |
| | Trânsito | Veículos de grande porte obstruindo a visibilidade | SEOP |
| **SMTR** | Ponto de ônibus | Ponto de ônibus com histórico de vandalismo | SMTR |
| **Comlurb** | Vegetação urbana | Vegetação encobrindo iluminação pública | Comlurb |
| | Vegetação urbana | Vegetação obstruindo a visibilidade do passeio | Comlurb |
| | Limpeza urbana | Lixo/entulho obstruindo a visibilidade | Comlurb |
| | Limpeza urbana | Lixo/entulho forçando pedestres à pista | Comlurb |
| **RioLuz** | Iluminação | Área mal iluminada com circulação de pedestres | RioLuz |
| | Iluminação | Área mal iluminada com parada de veículos | RioLuz |
| **Seconserva** | Obstrução de logradouro | Mobiliário urbano desviando pedestres à pista | Seconserva |
| | Obstrução de logradouro | Calçada estreita forçando pedestres à pista | Seconserva |
| | Refúgio | Mobiliário abandonado servindo de esconderijo | Seconserva |
| | Refúgio | Tapumes servindo de esconderijo | Seconserva |
| | Refúgio | Mobiliário/estrutura servindo de esconderijo | Seconserva |
| | Refúgio | Vãos ou cavidades usados como esconderijo | Seconserva |
| **SEOP** | Obstrução de logradouro | Comércio irregular obstruindo a visibilidade do passeio | SEOP |
| | Trânsito | Estacionamento irregular forçando pedestres à pista | SEOP |
| | Trânsito | Veículos de grande porte obstruindo a visibilidade | SEOP |
| | Pessoa em situação de rua | Adultos (transitória / pernoite / moradia) | SMAS |
| | Pessoa em situação de rua | Crianças e/ou adolescentes | SMAS |
| | Pessoa em situação de rua | Famílias ou casais | SMAS |
| | Cena de uso de drogas | Eventual (sem pontos de venda próximos) | SMAS |
| | Cena de uso de drogas | Crônica (com pontos de venda nas proximidades) | SMAS |
| **SMAS** | Pessoa em situação de rua | Adultos (transitória / pernoite / moradia) | SMAS |
| | Pessoa em situação de rua | Crianças e/ou adolescentes | SMAS |
| | Pessoa em situação de rua | Famílias ou casais | SMAS |
| | Cena de uso de drogas | Eventual (sem pontos de venda próximos) | SMAS |
| | Cena de uso de drogas | Crônica (com pontos de venda nas proximidades) | SMAS |
| **GM-Rio** | Praças e parques | Área mal iluminada com circulação de pedestres | RioLuz |
| | Praças e parques | Vegetação servindo de esconderijo | Comlurb |
| | Praças e parques | Mobiliário abandonado servindo de esconderijo | Seconserva |
| | Praças e parques | Mobiliário/estrutura servindo de esconderijo | Seconserva |
| | Trânsito | Ponto de retenção de tráfego | CET-Rio |
| | Trânsito | Motocicletas trafegando no passeio | GM-Rio |
| | Trânsito | Bicicletas trafegando no passeio | GM-Rio |

---

## Outras fontes de dados 

### Domínio Territorial
**Arquivo:** `dados/outros dados/dominio_territorial - Extração 1.csv`

Mapeamento dos territórios sob influência de organizações criminosas no município do Rio de Janeiro. Contém o nome do território, a facção com domínio sobre a área e a geometria (polígono) correspondente. Esse dado é essencial para contextualizar a dinâmica criminal das áreas analisadas e entender a influência territorial sobre padrões de crime e rotas de fuga.

### Censo de Pessoas em Situação de Rua (PSR)
**Arquivo:** `dados/outros dados/CPSR_2020_2022_2024.xlsx`

Dados do Censo de Pessoas em Situação de Rua realizado pela Prefeitura do Rio de Janeiro a cada dois anos, temos dados dos anos de 2020, 2022 e 2024. Permite identificar a concentração e evolução da PSR no território ao longo do tempo — um dos fatores de incidência criminal mapeados pelo CompStat, sob responsabilidade da SMAS.

### Central 1746 — Chamados de Serviços Públicos
**Base pública:** disponível no DataLake da Prefeitura do Rio de Janeiro (BigQuery)

A Central 1746 é o canal oficial de solicitação de serviços públicos da Prefeitura, onde o cidadão registra demandas como iluminação apagada, poda de árvores, buracos, lixo acumulado, entre outros. A base completa desde 2010 está disponível publicamente e pode ser acessada em: `https://console.cloud.google.com/bigquery?project=rj-ssm-dev&ws=!1m6!1m5!4m3!1sdatario!2sadm_central_atendimento_1746!3schamado!23sTREE_NODE_SELECTION`

Esse dataset é especialmente relevante para o CompStat porque os chamados do 1746 funcionam como uma camada adicional de validação dos fatores urbanos de incidência criminal — quando um trecho aparece com alta incidência de roubos, iluminação deficiente no levantamento de campo e múltiplos chamados de "poste apagado" no 1746, a coincidência reforça a priorização da ação.

### Dicionário de Dados
**Arquivo:** `Dicionário de dados.xlsx`

Planilha consolidada com a descrição de todas as variáveis (colunas) de cada dataset acima, incluindo nome do campo, tipo, descrição e observações. **Consulte este arquivo primeiro** para entender a estrutura dos dados.

---

## 📄 Relatórios de Inteligência (RelInts)

**Pasta:** `relints/`

Contém PDFs que simulam relatórios de inteligência reais (RELINTs). Esses documentos servem como referência do formato e conteúdo esperado em um relatório de inteligência da FM, permitindo que as soluções desenvolvidas no hackathon se orientem por esse padrão. Os RELINTs são uma das principais fontes qualitativas para desenvolvimento da dinâmica criminal.

---

## 🚀 Desafios Extras

Além do desafio principal de geração automatizada dos Relatórios Analíticos de Área, propomos quatro desafios complementares que ampliam a capacidade analítica do CompStat Municipal.

### Desafio 1 — Inteligência de Redes Sociais
Monitorar menções públicas nas redes sociais relacionadas à Força Municipal e a relatos de crimes no território do Rio de Janeiro. A solução deve identificar *onde* os eventos estão sendo reportados (bairro, logradouro, ponto de referência) e *como* ocorrem (padrão, tipo, horário), distinguindo denúncias de comentários gerais e gerando alertas estruturados para integração ao fluxo do CompStat Municipal.

### Desafio 2 — Migração do Crime no Território
Quando operamos com intensidade em um perímetro, as ocorrências tendem a migrar para áreas adjacentes menos monitoradas. A solução deve detectar e antecipar esse deslocamento geográfico da criminalidade, cruzando dados operacionais e de ocorrências para alertar a equipe sobre onde o crime está se deslocando em tempo hábil.

### Desafio 3 — Relatório de Decisão de Permanência Operacional
Nosso protocolo prevê uma permanência mínima de 90 dias de operação em determinada área. A solução deve apoiar a decisão de permanecer ou sair de uma área, consolidando indicadores de resultado, tendências de ocorrência e comparativos territoriais em um painel de monitoramento que oriente a alocação estratégica dos recursos.

### Desafio 4 — Otimização de Cobertura de Câmeras
Identificar pontos cegos no território — locais onde há registro de crimes mas ausência de cobertura por câmeras — para orientar a instalação ou remanejamento de equipamentos. A solução deve cruzar dados de ocorrências com o mapa atual de câmeras (CIVITAS/COR) e recomendar os pontos prioritários de expansão da vigilância.



**CompStat Rio** | Claude Impact Lab Rio 2026
