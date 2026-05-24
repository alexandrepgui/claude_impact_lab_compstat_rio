# -*- coding: utf-8 -*-
"""
Gera shapefiles (WGS84/EPSG:4326) a partir dos dados do CompStat Rio:
  - dados/df_ocorrencias_tratado - Extração 1 .csv  -> ocorrencias/        (pontos)
  - dados/disk_denuncia.csv                          -> disk_denuncia/      (pontos)
  - dados/cameras_areas_fm.csv                        -> cameras/            (pontos)
  - dados/fatores_urbanos.csv                         -> fatores_urbanos/    (pontos)
  - dados/outros dados/dominio_territorial ...csv     -> dominio_territorial/(polígonos)
  - dados/outros dados/CPSR_2020_2022_2024.xlsx       -> cpsr/               (pontos)

Saída pronta para importar no QGIS (inclui .prj e .cpg UTF-8).
"""
import os
import re
import math
import pandas as pd
import shapefile  # pyshp

BASE = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.normpath(os.path.join(BASE, "..", "dados"))

# Garante existência das subpastas de saída (cada fonte tem a sua).
for _subdir in (
    "ocorrencias",
    "disk_denuncia",
    "cameras",
    "fatores_urbanos",
    "dominio_territorial",
    "cpsr",
):
    os.makedirs(os.path.join(BASE, _subdir), exist_ok=True)

# CRS WGS84 (mesmo do shapefile de áreas da Força Municipal)
PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

# Bounding box do município do Rio de Janeiro (aproximado)
RIO_BBOX = dict(lat_min=-23.15, lat_max=-22.70, lon_min=-43.85, lon_max=-43.05)


def write_aux(path_base):
    """Escreve .prj (WGS84) e .cpg (UTF-8) ao lado do .shp."""
    with open(path_base + ".prj", "w", encoding="utf-8") as f:
        f.write(PRJ_WGS84)
    with open(path_base + ".cpg", "w", encoding="utf-8") as f:
        f.write("UTF-8")


def s(val, limit=254):
    """Normaliza valor para texto do DBF (trata NaN e trunca).

    O tamanho do campo DBF é medido em BYTES. Como o arquivo é gravado em UTF-8
    (acentos ocupam 2 bytes), truncamos pela codificação UTF-8 e descartamos um
    eventual caractere parcial no fim, evitando bytes inválidos.
    """
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    txt = str(val).strip()
    return txt.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def to_int(val):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_wkt_point(wkt):
    """Extrai (lon, lat) de 'POINT (lon lat)'. Retorna None se inválido."""
    if not isinstance(wkt, str):
        return None
    nums = re.findall(r"-?\d+\.?\d*", wkt)
    if len(nums) < 2:
        return None
    return float(nums[0]), float(nums[1])


def parse_wkt_polygon(wkt):
    """Converte 'POLYGON((x y, ...),(buraco...))' em lista de anéis [[ [x,y], ... ]]."""
    if not isinstance(wkt, str):
        return None
    try:
        inner = wkt[wkt.index("((") + 2: wkt.rindex("))")]
    except ValueError:
        return None
    rings = []
    for ring in inner.split("),("):
        pts = []
        for pair in ring.replace("(", "").replace(")", "").split(","):
            xy = pair.split()
            if len(xy) >= 2:
                pts.append([float(xy[0]), float(xy[1])])
        if pts:
            rings.append(pts)
    return rings or None


# ---------------------------------------------------------------------------
# 1) OCORRÊNCIAS
# ---------------------------------------------------------------------------
def gerar_ocorrencias():
    src = os.path.join(DADOS, "df_ocorrencias_tratado - Extração 1 .csv")
    out = os.path.join(BASE, "ocorrencias", "ocorrencias")
    df = pd.read_csv(src, dtype={"id_criptografado": str})

    w = shapefile.Writer(out, shapeType=shapefile.POINT, encoding="utf-8")
    w.field("id_cripto", "C", 64)
    w.field("ano", "N", 4)
    w.field("data", "C", 20)
    w.field("mes", "N", 2)
    w.field("hora", "C", 10)
    w.field("delito", "N", 4)
    w.field("desc_delit", "C", 60)
    w.field("aisp", "N", 4)
    w.field("risp", "N", 4)
    w.field("locf", "C", 120)
    w.field("dia_semana", "C", 12)
    w.field("longitude", "N", 20, 10)
    w.field("latitude", "N", 20, 10)
    w.field("coord_fix", "C", 1)  # 'S' = coordenada reparada (faltava ponto decimal)

    escritos = reparados = descartados = 0
    for _, r in df.iterrows():
        lat = r["latitude"]
        lon = r["longitude"]
        fix = "N"
        # Repara coords sem ponto decimal (ex.: -22806 -> -22.806)
        if abs(lat) > 90:
            lat = lat / 1000.0
            fix = "S"
        if abs(lon) > 180:
            lon = lon / 1000.0
            fix = "S"
        # Descarta o que ainda estiver fora de um intervalo plausível
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            descartados += 1
            continue
        w.point(lon, lat)
        w.record(
            s(r["id_criptografado"], 64),
            to_int(r["ano"]),
            s(r["data"], 20),
            to_int(r["mes"]),
            s(r["hora"], 10),
            to_int(r["delito"]),
            s(r["desc_delito"], 60),
            to_int(r["aisp"]),
            to_int(r["risp"]),
            s(r["locf"], 120),
            s(r["dia_semana"], 12),
            round(float(lon), 10),
            round(float(lat), 10),
            fix,
        )
        escritos += 1
        if fix == "S":
            reparados += 1
    w.close()
    write_aux(out)
    print(f"[ocorrencias] escritos={escritos} reparados={reparados} descartados={descartados}")
    return dict(total=len(df), escritos=escritos, reparados=reparados, descartados=descartados)


# ---------------------------------------------------------------------------
# 2) DISK DENÚNCIA
# ---------------------------------------------------------------------------
def gerar_disk():
    src = os.path.join(DADOS, "disk_denuncia.csv")
    out = os.path.join(BASE, "disk_denuncia", "disk_denuncia")
    df = pd.read_csv(src, sep=";", encoding="cp1252", dtype=str)
    total_linhas = len(df)

    # O CSV é um "explode" de JSON: cada denúncia ocupa 1 linha-cabeçalho (com
    # id_denuncia, datas, endereço e coordenada) seguida de N linhas-filhas
    # vazias nesses campos, mas que trazem orgaos.* / assuntos.* / envolvidos.*
    # adicionais. Reconstituímos cada denúncia agrupando por id_denuncia
    # propagado para baixo (forward-fill).
    df["grp"] = df["id_denuncia"].ffill()
    df = df[df["grp"].notna()]

    # Descrição compacta de cada envolvido (uma por linha que tenha dados).
    env_cols = [
        ("Sexo", "envolvidos.sexo"), ("Idade", "envolvidos.idade"),
        ("Pele", "envolvidos.pele"), ("Estatura", "envolvidos.estatura"),
        ("Porte", "envolvidos.porte"), ("Cabelos", "envolvidos.cabelos"),
        ("Olhos", "envolvidos.olhos"), ("Obs", "envolvidos.outras_caracteristicas"),
    ]

    def env_desc(row):
        partes = []
        for rotulo, col in env_cols:
            v = row.get(col)
            if v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip():
                partes.append(f"{rotulo}:{str(v).strip()}")
        return " ".join(partes)

    df["_env"] = df.apply(env_desc, axis=1)

    total_denuncias = df["grp"].nunique()

    w = shapefile.Writer(out, shapeType=shapefile.POINT, encoding="utf-8")
    w.field("num_denun", "C", 30)
    w.field("id_denun", "C", 20)
    w.field("dt_denun", "C", 25)
    w.field("dt_difus", "C", 25)
    w.field("tp_logr", "C", 10)
    w.field("logradouro", "C", 120)
    w.field("num_logr", "C", 15)
    w.field("bairro", "C", 60)
    w.field("subbairro", "C", 60)
    w.field("cep", "C", 12)
    w.field("referencia", "C", 120)
    w.field("municipio", "C", 60)
    w.field("estado", "C", 4)
    w.field("status", "C", 50)
    w.field("classe_pr", "C", 80)   # classe do assunto principal (cabeçalho)
    w.field("tipo_pr", "C", 80)     # tipo do assunto principal (cabeçalho)
    w.field("classes", "C", 254)    # todas as classes da denúncia (consolidado)
    w.field("tipos", "C", 254)      # todos os tipos da denúncia (consolidado)
    w.field("orgaos", "C", 254)     # todos os órgãos acionados (consolidado)
    w.field("n_orgaos", "N", 4)
    w.field("n_classes", "N", 4)
    w.field("n_tipos", "N", 4)
    w.field("n_envolv", "N", 4)
    w.field("envolvidos", "C", 254)  # descrição consolidada dos envolvidos
    w.field("relato", "C", 254)
    w.field("longitude", "N", 20, 10)
    w.field("latitude", "N", 20, 10)
    w.field("dentro_rio", "C", 1)    # 'S' se dentro do bbox do município do RJ

    def uniq(series):
        """Lista de valores únicos não-vazios, preservando a ordem de aparição."""
        out_vals = []
        for v in series:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            t = str(v).strip()
            if t and t not in out_vals:
                out_vals.append(t)
        return out_vals

    escritos = sem_coord = invalidos = fora_rio = 0
    b = RIO_BBOX
    for _, g in df.groupby("grp", sort=False):
        h = g.iloc[0]  # linha-cabeçalho da denúncia

        if h["latitude"] is None or h["longitude"] is None \
                or (isinstance(h["latitude"], float) and math.isnan(h["latitude"])):
            sem_coord += 1
            continue
        try:
            lat = float(str(h["latitude"]).replace(",", "."))
            lon = float(str(h["longitude"]).replace(",", "."))
        except (ValueError, TypeError):
            invalidos += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            invalidos += 1
            continue

        dentro = (
            b["lat_min"] <= lat <= b["lat_max"]
            and b["lon_min"] <= lon <= b["lon_max"]
        )
        if not dentro:
            fora_rio += 1

        classes = uniq(g["assuntos.classe"])
        tipos = uniq(g["assuntos.tipos.tipo"])
        orgaos = uniq(g["orgaos.nome"])
        envolv = uniq(g["_env"])

        w.point(lon, lat)
        w.record(
            s(h["numero_denuncia"], 30),
            s(h["id_denuncia"], 20),
            s(h["data_denuncia"], 25),
            s(h["data_difusao"], 25),
            s(h["tipo_logradouro"], 10),
            s(h["logradouro"], 120),
            s(h["numero_logradouro"], 15),
            s(h["bairro_logradouro"], 60),
            s(h["subbairro_logradouro"], 60),
            s(h["cep_logradouro"], 12),
            s(h["referencia_logradouro"], 120),
            s(h["municipio"], 60),
            s(h["estado"], 4),
            s(h["status_denuncia"], 50),
            s(h["classe"], 80),
            s(h["tipo"], 80),
            s(" | ".join(classes), 254),
            s(" | ".join(tipos), 254),
            s(" | ".join(orgaos), 254),
            len(orgaos),
            len(classes),
            len(tipos),
            len(envolv),
            s(" || ".join(envolv), 254),
            s(h["relato_redacted"], 254),
            round(lon, 10),
            round(lat, 10),
            "S" if dentro else "N",
        )
        escritos += 1
    w.close()
    write_aux(out)
    print(f"[disk] linhas={total_linhas} denuncias={total_denuncias} "
          f"escritos={escritos} sem_coord={sem_coord} fora_rio={fora_rio} invalidos={invalidos}")
    return dict(total_linhas=total_linhas, total_denuncias=total_denuncias,
                escritos=escritos, sem_coord=sem_coord, fora_rio=fora_rio, invalidos=invalidos)


# ---------------------------------------------------------------------------
# 3) CÂMERAS
# ---------------------------------------------------------------------------
def gerar_cameras():
    src = os.path.join(DADOS, "cameras_areas_fm.csv")
    out = os.path.join(BASE, "cameras", "cameras")
    df = pd.read_csv(src, dtype=str)

    w = shapefile.Writer(out, shapeType=shapefile.POINT, encoding="utf-8")
    w.field("id_ponto", "C", 40)
    w.field("nome_area", "C", 120)
    w.field("id_trecho", "C", 20)
    w.field("longitude", "N", 20, 10)
    w.field("latitude", "N", 20, 10)

    escritos = invalidos = 0
    for _, r in df.iterrows():
        pt = parse_wkt_point(r["geometry"])
        if pt is None:
            invalidos += 1
            continue
        lon, lat = pt
        w.point(lon, lat)
        w.record(s(r["id_ponto"], 40), s(r["nome_area_fm"], 120),
                 s(r["id_trecho"], 20), round(lon, 10), round(lat, 10))
        escritos += 1
    w.close()
    write_aux(out)
    print(f"[cameras] total={len(df)} escritos={escritos} invalidos={invalidos}")
    return dict(total=len(df), escritos=escritos, invalidos=invalidos)


# ---------------------------------------------------------------------------
# 4) FATORES URBANOS
# ---------------------------------------------------------------------------
def gerar_fatores():
    src = os.path.join(DADOS, "fatores_urbanos.csv")
    out = os.path.join(BASE, "fatores_urbanos", "fatores_urbanos")
    df = pd.read_csv(src, dtype=str)

    w = shapefile.Writer(out, shapeType=shapefile.POINT, encoding="utf-8")
    w.field("id_resp", "C", 20)      # id_resposta_ocorrencia
    w.field("logradouro", "C", 120)
    w.field("num_porta", "C", 15)
    w.field("referencia", "C", 120)
    w.field("bairro", "C", 60)       # bairro_nome
    w.field("subarea", "C", 80)      # subarea_nome
    w.field("tp_ocorr", "C", 120)    # tipo_ocorrencia_descricao (o fator urbano)
    w.field("orgao", "C", 30)        # orgao_responsavel
    w.field("valido", "C", 6)
    w.field("tp_pessoa", "C", 80)    # tipo_pessoa_descricao
    w.field("ocup_pess", "C", 80)    # ocupacao_pessoa_descricao
    w.field("frequenc", "C", 60)     # tipo_frequencia_descricao
    w.field("drogas", "C", 80)       # ocupacao_drogas_descricao
    w.field("item_praca", "C", 80)   # item_praca_descricao
    w.field("longitude", "N", 20, 10)
    w.field("latitude", "N", 20, 10)
    w.field("dentro_rio", "C", 1)

    escritos = invalidos = fora_rio = 0
    b = RIO_BBOX
    for _, r in df.iterrows():
        # ATENÇÃO: no CSV, coordenada_x = latitude e coordenada_y = longitude.
        try:
            lat = float(str(r["coordenada_x"]).replace(",", "."))
            lon = float(str(r["coordenada_y"]).replace(",", "."))
        except (ValueError, TypeError):
            invalidos += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            invalidos += 1
            continue
        dentro = (b["lat_min"] <= lat <= b["lat_max"]
                  and b["lon_min"] <= lon <= b["lon_max"])
        if not dentro:
            fora_rio += 1
        w.point(lon, lat)
        w.record(
            s(r["id_resposta_ocorrencia"], 20),
            s(r["logradouro"], 120),
            s(r["numero_porta"], 15),
            s(r["referencia"], 120),
            s(r["bairro_nome"], 60),
            s(r["subarea_nome"], 80),
            s(r["tipo_ocorrencia_descricao"], 120),
            s(r["orgao_responsavel"], 30),
            s(r["valido"], 6),
            s(r["tipo_pessoa_descricao"], 80),
            s(r["ocupacao_pessoa_descricao"], 80),
            s(r["tipo_frequencia_descricao"], 60),
            s(r["ocupacao_drogas_descricao"], 80),
            s(r["item_praca_descricao"], 80),
            round(lon, 10),
            round(lat, 10),
            "S" if dentro else "N",
        )
        escritos += 1
    w.close()
    write_aux(out)
    print(f"[fatores] total={len(df)} escritos={escritos} fora_rio={fora_rio} invalidos={invalidos}")
    return dict(total=len(df), escritos=escritos, fora_rio=fora_rio, invalidos=invalidos)


# ---------------------------------------------------------------------------
# 5) DOMÍNIO TERRITORIAL (polígonos)
# ---------------------------------------------------------------------------
def gerar_dominio():
    src = os.path.join(DADOS, "outros dados", "dominio_territorial - Extração 1.csv")
    out = os.path.join(BASE, "dominio_territorial", "dominio_territorial")
    df = pd.read_csv(src, dtype=str)

    # Bounding box generoso do estado do Rio de Janeiro
    rj = dict(lon_min=-45.0, lon_max=-40.5, lat_min=-23.8, lat_max=-20.5)

    w = shapefile.Writer(out, shapeType=shapefile.POLYGON, encoding="utf-8")
    w.field("territorio", "C", 120)  # nome_territorio
    w.field("faccao", "C", 20)       # dominio_orcrim
    w.field("regiao_rj", "C", 1)     # 'S' se o polígono está dentro do estado do RJ

    escritos = invalidos = fora_rj = 0
    for _, r in df.iterrows():
        rings = parse_wkt_polygon(r["geometria"])
        if not rings:
            invalidos += 1
            continue
        xs = [p[0] for ring in rings for p in ring]
        ys = [p[1] for ring in rings for p in ring]
        dentro = (rj["lon_min"] <= min(xs) and max(xs) <= rj["lon_max"]
                  and rj["lat_min"] <= min(ys) and max(ys) <= rj["lat_max"])
        if not dentro:
            fora_rj += 1
        w.poly(rings)
        w.record(s(r["nome_territorio"], 120), s(r["dominio_orcrim"], 20),
                 "S" if dentro else "N")
        escritos += 1
    w.close()
    write_aux(out)
    print(f"[dominio] total={len(df)} escritos={escritos} fora_rj={fora_rj} invalidos={invalidos}")
    return dict(total=len(df), escritos=escritos, fora_rj=fora_rj, invalidos=invalidos)


# ---------------------------------------------------------------------------
# 6) CPSR — Censo de Pessoas em Situação de Rua (pontos)
#    Por privacidade, inclui apenas campos NÃO sensíveis (sem CPF, nome, saúde).
# ---------------------------------------------------------------------------
def gerar_cpsr():
    src = os.path.join(DADOS, "outros dados", "CPSR_2020_2022_2024.xlsx")
    out = os.path.join(BASE, "cpsr", "cpsr")
    df = pd.read_excel(src, sheet_name="Censo_histórico")

    w = shapefile.Writer(out, shapeType=shapefile.POINT, encoding="utf-8")
    w.field("chave", "C", 40)        # Chave_única
    w.field("ano", "N", 4)
    w.field("sexo", "C", 20)
    w.field("faixa_et", "C", 20)     # Faixa etária
    w.field("cor_raca", "C", 20)     # Cor_raça
    w.field("ap", "C", 6)            # Área de Planejamento
    w.field("bairro", "C", 60)       # Nome do Bairro
    w.field("ra", "C", 60)           # Região Administrativa
    w.field("subpref", "C", 60)      # Subprefeitura
    w.field("longitude", "N", 20, 10)
    w.field("latitude", "N", 20, 10)
    w.field("dentro_rio", "C", 1)

    escritos = invalidos = fora_rio = 0
    b = RIO_BBOX
    for _, r in df.iterrows():
        try:
            lat = float(str(r["Latitude"]).replace(",", "."))
            lon = float(str(r["Longitude"]).replace(",", "."))
        except (ValueError, TypeError):
            invalidos += 1
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            invalidos += 1
            continue
        dentro = (b["lat_min"] <= lat <= b["lat_max"]
                  and b["lon_min"] <= lon <= b["lon_max"])
        if not dentro:
            fora_rio += 1
        w.point(lon, lat)
        w.record(
            s(r["Chave_única"], 40),
            to_int(r["Ano"]),
            s(r["Sexo"], 20),
            s(r["Faixa etária"], 20),
            s(r["Cor_raça"], 20),
            s(r["Área de Planejamento_3"], 6),
            s(r["Nome do Bairro"], 60),
            s(r["Região Administrativa_4"], 60),
            s(r["Subprefeitura"], 60),
            round(lon, 10),
            round(lat, 10),
            "S" if dentro else "N",
        )
        escritos += 1
    w.close()
    write_aux(out)
    print(f"[cpsr] total={len(df)} escritos={escritos} fora_rio={fora_rio} invalidos={invalidos}")
    return dict(total=len(df), escritos=escritos, fora_rio=fora_rio, invalidos=invalidos)


if __name__ == "__main__":
    print("Gerando shapefiles...")
    gerar_ocorrencias()
    gerar_disk()
    gerar_cameras()
    gerar_fatores()
    gerar_dominio()
    gerar_cpsr()
    print("Concluído.")
