# -*- coding: utf-8 -*-
"""
ETL do dashboard COOP Clima São Vicente.

Lê os três CSVs de dados_tratados/, limpa e cruza os dados, e injeta o JSON
resultante no template.html, gerando o index.html estático final (pronto para
GitHub Pages — sem backend).

Uso:  python etl.py
"""
import base64
import json
import re
import unicodedata
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
DADOS = BASE / "dados_tratados"
TEMPLATE = BASE / "template.html"
SAIDA = BASE / "index.html"
LOGO = BASE / "logo_branco_verde.png"

# Caixa delimitadora aproximada de São Vicente (SP) — pontos fora dela são
# erros de geocodificação e ficam sem marcador no mapa.
LAT_MIN, LAT_MAX = -24.10, -23.85
LNG_MIN, LNG_MAX = -46.62, -46.28

# ---------------------------------------------------------------- normalização

ABREV = {
    "JD": "JARDIM", "PQ": "PARQUE", "PRQ": "PARQUE", "VL": "VILA",
    "CJTO": "CONJUNTO", "CONJ": "CONJUNTO", "SRA": "SENHORA",
    "STA": "SANTA", "NSA": "NOSSA", "AV": "AVENIDA",
}

# Grafias diferentes do mesmo bairro (aplicado após normalizar/expandir)
ALIASES = {
    "VILA JOQUEI CLUBE": "JOCKEY CLUB",
    "JOQUEI CLUBE": "JOCKEY CLUB",
    "CIDADE NAUTICA III": "CIDADE NAUTICA",
    "NAUTICA III": "CIDADE NAUTICA",
    "VILA NOVA SAO VICENTE": "NOVA SAO VICENTE",
    "CONJUNTO RESIDENCIAL HUMAITA": "HUMAITA",
    "CONJUNTO HUMAITA": "HUMAITA",
    "POMPEBA": "JARDIM POMPEBA",
}


def norm(texto):
    """Normaliza nome de bairro: sem acento, maiúsculo, abreviações expandidas."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    s = unicodedata.normalize("NFD", str(texto))
    s = s.encode("ascii", "ignore").decode("ascii").upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = " ".join(ABREV.get(tok, tok) for tok in s.split())
    return ALIASES.get(s, s)


def title_pt(s):
    """Título legível para bairros sem registro no censo (VILA MATEO BEI -> Vila Mateo Bei)."""
    minusculas = {"DE", "DA", "DO", "DAS", "DOS", "E"}
    partes = []
    for tok in s.split():
        partes.append(tok.lower() if tok in minusculas else tok.capitalize())
    return " ".join(partes)


def fix_coord(v):
    """Corrige coordenadas sem ponto decimal (ex.: -239575481911.0 -> -23.9575...)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if pd.isna(v) or v == 0:
        return None
    while abs(v) >= 100:
        v /= 10
    return round(v, 7)


def dentro_da_cidade(lat, lng):
    return (
        lat is not None and lng is not None
        and LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX
    )


# --------------------------------------------------------------------- censo

def carrega_censo():
    df = pd.read_csv(DADOS / "dados_censo_limpos.csv")
    df = df.dropna(subset=["NM_BAIRRO"])
    registros = []
    for _, r in df.iterrows():
        pop_total = int(r["pop_amarel"] + r["pop_indige"] + r["pop_branco"] + r["pop_negros"])
        registros.append({
            "bairro": r["NM_BAIRRO"].strip(),
            "key": norm(r["NM_BAIRRO"]),
            "situacao": r["SITUACAO"],
            "area_km2": round(float(r["AREA_KM2"]), 4),
            "pop_amarela": int(r["pop_amarel"]),
            "pop_indigena": int(r["pop_indige"]),
            "pop_branca": int(r["pop_branco"]),
            "pop_negra": int(r["pop_negros"]),
            "pop_total": pop_total,
            "hab_setor": int(r["hab_setor"]),
            "densidade": round(float(r["densidade"]), 1),
            "hab_ha": round(float(r["hab/ha"]), 1),
            "renda_sal": float(r["renda_sal"]),
        })
    return registros


def casa_truncado(key, keys_censo):
    """Nomes truncados em 20 caracteres na base de saúde: casa por prefixo único."""
    if len(key) < 15:
        return key
    candidatos = [k for k in keys_censo if k.startswith(key)]
    return candidatos[0] if len(candidatos) == 1 else key


# -------------------------------------------------------------------- escolas

CAPACIDADE = {
    "Escola sem matrícula de escolarização": 0,
    "Até 50 matrículas de escolarização": 50,
    "Entre 51 e 200 matrículas de escolarização": 200,
    "Entre 201 e 500 matrículas de escolarização": 500,
    "Entre 501 e 1000 matrículas de escolarização": 1000,
    # faixa aberta: usa o piso (capacidade real é >= 1000)
    "Mais de 1000 matrículas de escolarização": 1000,
}

PORTE_CURTO = {
    "Escola sem matrícula de escolarização": "Sem matrícula",
    "Até 50 matrículas de escolarização": "Até 50",
    "Entre 51 e 200 matrículas de escolarização": "51–200",
    "Entre 201 e 500 matrículas de escolarização": "201–500",
    "Entre 501 e 1000 matrículas de escolarização": "501–1000",
    "Mais de 1000 matrículas de escolarização": "Mais de 1000",
}

STATUS = {
    "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO": "Em funcionamento",
    "ESCOLA PARALISADA": "Paralisada",
    "ESCOLA ATENDE EXCLUSIVAMENTE ALUNOS COM DEFICIÊNCIA": "Exclusiva p/ alunos com deficiência",
    "ESCOLA EXCLUSIVA DE ATIVIDADE COMPLEMENTAR": "Atividade complementar",
}


def carrega_escolas(keys_censo):
    df = pd.read_csv(DADOS / "escolas_final.csv")
    registros = []
    for _, r in df.iterrows():
        key = casa_truncado(norm(r["Bairro"]), keys_censo)
        lat, lng = fix_coord(r["Latitude"]), fix_coord(r["Longitude"])
        if not dentro_da_cidade(lat, lng):
            lat, lng = None, None
        porte = r["Porte da Escola"] if pd.notna(r["Porte da Escola"]) else None
        etapas = []
        if pd.notna(r["Etapas e Modalidade de Ensino Oferecidas"]):
            etapas = [e.strip() for e in str(r["Etapas e Modalidade de Ensino Oferecidas"]).split(",")]
        registros.append({
            "nome": str(r["Escola"]).strip(),
            "categoria": r["Categoria Administrativa"],
            "endereco": str(r["Endereço"]).strip() if pd.notna(r["Endereço"]) else "",
            "telefone": str(r["Telefone"]).strip() if pd.notna(r["Telefone"]) else "",
            "porte": PORTE_CURTO.get(porte) if porte else None,
            "capacidade": CAPACIDADE.get(porte, 0) if porte else 0,
            "etapas": etapas,
            "status": STATUS.get(r["Restrição de Atendimento"], r["Restrição de Atendimento"]),
            "lat": lat, "lng": lng,
            "key": key,
        })
    return registros


# ---------------------------------------------------------------------- saúde

TURNO_CURTO = [
    ("24 HORAS", "24 horas"),
    ("MANHA, TARDE E NOITE", "Manhã, tarde e noite"),
    ("MANHA E A TARDE", "Manhã e tarde"),
    ("SOMENTE A TARDE", "Somente à tarde"),
    ("SOMENTE PELA MANHA", "Somente pela manhã"),
    ("INTERMITENTES", "Turnos intermitentes"),
]


def turno_curto(t):
    t = str(t).upper()
    for chave, rotulo in TURNO_CURTO:
        if chave in t:
            return rotulo
    return "Não informado"


def flag(v):
    try:
        return float(v) == 1.0
    except (TypeError, ValueError):
        return False


def carrega_saude(keys_censo):
    df = pd.read_csv(DADOS / "estabelecimento_saude_final.csv")
    registros = []
    for _, r in df.iterrows():
        key = casa_truncado(norm(r["NO_BAIRRO"]), keys_censo)
        lat, lng = fix_coord(r["NU_LATITUDE"]), fix_coord(r["NU_LONGITUDE"])
        if not dentro_da_cidade(lat, lng):
            lat, lng = None, None
        numero = str(r["NU_ENDERECO"]).strip() if pd.notna(r["NU_ENDERECO"]) else "S/N"
        endereco = f"{str(r['NO_LOGRADOURO']).strip().title()}, {numero}"
        registros.append({
            "nome": str(r["NOME"]).strip(),
            "endereco": endereco,
            "telefone": str(r["NU_TELEFONE"]).strip() if pd.notna(r["NU_TELEFONE"]) else "",
            "turno": turno_curto(r["DS_TURNO_ATENDIMENTO"]),
            "sus": str(r["CO_AMBULATORIAL_SUS"]).strip().upper() == "SIM",
            "servicos": {
                "cirurgico": flag(r["ST_CENTRO_CIRURGICO"]),
                "obstetrico": flag(r["ST_CENTRO_OBSTETRICO"]),
                "neonatal": flag(r["ST_CENTRO_NEONATAL"]),
                "hospitalar": flag(r["ST_ATEND_HOSPITALAR"]),
                "apoio": flag(r["ST_SERVICO_APOIO"]),
                "ambulatorial": flag(r["ST_ATEND_AMBULATORIAL"]),
            },
            "lat": lat, "lng": lng,
            "key": key,
        })
    return registros


# ------------------------------------------------------------------------ logo

def logo_data_uri():
    """Lê a logo, recorta a margem verde sobrando e devolve como data URI PNG.

    Embutir a imagem mantém o index.html autocontido (um único arquivo). O
    recorte usa Pillow quando disponível; sem Pillow, embute a imagem íntegra.
    """
    if not LOGO.exists():
        print("AVISO: logo_branco_verde.png não encontrada — cabeçalho ficará sem logo.")
        return ""
    raw = LOGO.read_bytes()
    try:
        from PIL import Image, ImageChops
        im = Image.open(BytesIO(raw)).convert("RGBA")
        fundo = Image.new("RGB", im.size, im.convert("RGB").getpixel((0, 0)))
        bbox = ImageChops.difference(im.convert("RGB"), fundo).getbbox()
        if bbox:
            pad = 26
            im = im.crop((
                max(bbox[0] - pad, 0), max(bbox[1] - pad, 0),
                min(bbox[2] + pad, im.width), min(bbox[3] + pad, im.height),
            ))
        buf = BytesIO()
        im.save(buf, format="PNG", optimize=True)
        raw = buf.getvalue()
    except ImportError:
        print("AVISO: Pillow não instalado — logo embutida sem recorte.")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ----------------------------------------------------------------------- main

def main():
    censo = carrega_censo()
    keys_censo = [c["key"] for c in censo]
    escolas = carrega_escolas(keys_censo)
    saude = carrega_saude(keys_censo)

    # Bairros presentes só nas bases de equipamentos (sem dados do censo)
    conhecidos = set(keys_censo)
    extras = sorted({r["key"] for r in escolas + saude if r["key"] and r["key"] not in conhecidos})
    extra_bairros = [{"key": k, "bairro": title_pt(k)} for k in extras]

    dados = {
        "gerado_em": date.today().isoformat(),
        "censo": censo,
        "escolas": escolas,
        "saude": saude,
        "extra_bairros": extra_bairros,
    }

    payload = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # nunca fechar a tag <script> por acidente

    template = TEMPLATE.read_text(encoding="utf-8")
    if "__DATA_JSON__" not in template:
        raise SystemExit("template.html não contém o marcador __DATA_JSON__")
    html = template.replace("__DATA_JSON__", payload)
    html = html.replace("__LOGO_DATA__", logo_data_uri())
    SAIDA.write_text(html, encoding="utf-8")

    sem_coord = sum(1 for r in escolas + saude if r["lat"] is None)
    print(f"OK: {SAIDA.name} gerado.")
    print(f"  bairros do censo: {len(censo)} | escolas: {len(escolas)} | saúde: {len(saude)}")
    print(f"  bairros extras (sem censo): {len(extra_bairros)}")
    print(f"  registros sem coordenada válida (fora do mapa): {sem_coord}")


if __name__ == "__main__":
    main()
