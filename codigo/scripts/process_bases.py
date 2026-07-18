import pandas as pd
import io
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# =======================================================
# Configurações e Listas de Colunas para Remoção
# =======================================================

arquivo_saude = "estabelecimento_saude.csv"
colunas_remover_saude = [
    "CO_UNIDADE",
    "CO_UF",
    "CO_IBGE",
    "NU_CNPJ_MANTENEDORA",
    "NO_RAZAO_SOCIAL",
    "CO_NATUREZA_ORGANIZACAO",
    "DS_NATUREZA_ORGANIZACAO",
    "TP_GESTAO",
    "CO_NIVEL_HIERARQUIA",
    "DS_NIVEL_HIERARQUIA",
    "CO_ESFERA_ADMINISTRATIVA",
    "DS_ESFERA_ADMINISTRATIVA",
    "CO_ATIVIDADE",
    "TP_UNIDADE",
    "CO_TURNO_ATENDIMENTO",
    "NU_CNPJ",
    "NO_EMAIL",
    "CO_NATUREZA_JUR",
    "CO_MOTIVO_DESAB",
]

arquivo_escolas = "escolas_com_bairro.csv"
colunas_remover_escolas = [
    "Código INEP",
    "UF",
    "Município",
    "Localização",
    "Localidade Diferenciada",
    "Categoria Escola Privada",
    "Conveniada Poder Público",
    "Regulamentação pelo Conselho de Educação",
    "Outras Ofertas Educacionais",
]

# =======================================================
# Coordenadas Manuais (Linha do Excel : (Latitude, Longitude))
# =======================================================
coordenadas_manuais_saude = {
    128: (-23.967906, -46.384924),
    129: (-23.965482, -46.389158),
    160: (-23.962599, -46.380445),
    194: (-23.967906, -46.384924),
    210: (-23.967639, -46.385073),
    426: (-23.957742, -46.375625),
}

coordenadas_manuais_escolas = {
    24: (-23.962403, -46.393104),
    26: (-23.977582, -46.474333),
    33: (-23.956439, -46.456142),
    36: (-23.982742, -46.487191),
    40: (-23.939421, -46.420030),
    41: (-23.937723, -46.419883),
    42: (-23.937692, -46.419682),
    45: (-23.939326, -46.418792),
    50: (-23.989617, -46.489348),
    54: (-23.966122, -46.405922),
}

# Inicializa o geocodificador do OpenStreetMap (Nominatim)
geolocator = Nominatim(user_agent="geocodificador_planilhas_br")

falhas_saude = []
falhas_escolas = []

# =======================================================
# Funções Auxiliares
# =======================================================


def limpar_linhas_csv(caminho_arquivo):
    """Corrige problemas de formatação onde a linha inteira fica presa entre aspas duplas."""
    linhas_limpas = []
    with open(caminho_arquivo, "r", encoding="utf-8-sig") as f:
        cabecalho = f.readline()
        linhas_limpas.append(cabecalho)
        for linha in f:
            linha = linha.strip()
            if linha.startswith('"') and linha.endswith('"'):
                linha = linha[1:-1].replace('""', '"')
            linhas_limpas.append(linha + "\n")
    return "".join(linhas_limpas)


def preencher_coordenadas_manuais(df, dicionario_coords, col_lat, col_lon):
    """Injeta as coordenadas manuais diretamente nas linhas corretas (baseado na linha do Excel)."""
    for linha_excel, (lat, lon) in dicionario_coords.items():
        # Converte a linha do Excel (1-based, com cabeçalho) para o índice do Pandas (0-based)
        idx_pandas = linha_excel - 2
        if idx_pandas in df.index:
            df.at[idx_pandas, col_lat] = lat
            df.at[idx_pandas, col_lon] = lon
            print(f"   [Manual] Linha {linha_excel} preenchida: Lat {lat}, Lon {lon}")
    return df


def obter_coordenadas(endereco, tentativas=3):
    """Consulta o endereço na internet e retorna (latitude, longitude)."""
    if pd.isna(endereco) or str(endereco).strip() == "":
        return None, None

    for _ in range(tentativas):
        try:
            local = geolocator.geocode(endereco, timeout=10)
            if local:
                time.sleep(1)
                return local.latitude, local.longitude
            else:
                time.sleep(1)
                return None, None
        except GeocoderTimedOut:
            time.sleep(2)
            continue
        except Exception as e:
            print(f"Erro na requisição ao buscar '{endereco}': {e}")
            time.sleep(1)
            return None, None
    return None, None


def unificar_categoria_escola(row):
    """Lê as colunas originais e define a nova categoria padronizada."""
    cat = str(row.get("Categoria Administrativa", "")).upper()
    dep = str(row.get("Dependência Administrativa", "")).upper()

    texto_combinado = f"{cat} {dep}"

    if "PRIVADA" in texto_combinado or "PARTICULAR" in texto_combinado:
        return "Privada"
    elif "ESTADUAL" in texto_combinado:
        return "Pública Estadual"
    elif "MUNICIPAL" in texto_combinado:
        return "Pública Municipal"
    else:
        return row.get("Categoria Administrativa", "")


# =======================================================
# 1. Processamento da planilha de Saúde
# =======================================================
try:
    print(f"\n--- Iniciando o processamento de '{arquivo_saude}' ---")
    df_saude = pd.read_csv(arquivo_saude, encoding="utf-8-sig", sep=",")

    # TRANSFORMAÇÕES
    # 1. Remove a primeira coluna (índice 0) que não possui cabeçalho
    df_saude = df_saude.drop(df_saude.columns[0], axis=1)

    # 2. Renomeia a coluna 'NO_FANTASIA' para 'NOME'
    df_saude = df_saude.rename(columns={"NO_FANTASIA": "NOME"})

    df_saude["NU_LATITUDE"] = pd.to_numeric(df_saude["NU_LATITUDE"], errors="coerce")
    df_saude["NU_LONGITUDE"] = pd.to_numeric(df_saude["NU_LONGITUDE"], errors="coerce")

    # 3. Preenche as coordenadas manuais antes de buscar na API
    print("Aplicando coordenadas manuais da base de Saúde...")
    df_saude = preencher_coordenadas_manuais(
        df_saude, coordenadas_manuais_saude, "NU_LATITUDE", "NU_LONGITUDE"
    )

    # Verifica o que ainda falta
    mask_saude = df_saude["NU_LATITUDE"].isna() | df_saude["NU_LONGITUDE"].isna()
    linhas_sem_coord_saude = df_saude[mask_saude]

    if not linhas_sem_coord_saude.empty:
        print(
            f"Encontradas {len(linhas_sem_coord_saude)} linhas sem coordenadas. Iniciando geocodificação via API..."
        )
        for index, row in linhas_sem_coord_saude.iterrows():
            logradouro = (
                str(row["NO_LOGRADOURO"]) if pd.notna(row["NO_LOGRADOURO"]) else ""
            )
            numero = str(row["NU_ENDERECO"]) if pd.notna(row["NU_ENDERECO"]) else ""
            bairro = str(row["NO_BAIRRO"]) if pd.notna(row["NO_BAIRRO"]) else ""
            cep = str(row["CO_CEP"]) if pd.notna(row["CO_CEP"]) else ""

            endereco_completo = (
                f"{logradouro}, {numero}, {bairro}, {cep}, Brasil".strip(" ,")
            )

            lat, lon = obter_coordenadas(endereco_completo)
            linha_excel = index + 2

            if lat is not None and lon is not None:
                df_saude.at[index, "NU_LATITUDE"] = lat
                df_saude.at[index, "NU_LONGITUDE"] = lon
                print(f"OK API (Linha {linha_excel}) -> {endereco_completo[:40]}...")
            else:
                falhas_saude.append((linha_excel, endereco_completo))
                print(f"FALHA API (Linha {linha_excel}) -> Não encontrado")
    else:
        print("Todas as linhas já possuem Latitude e Longitude.")

    # Remove colunas desnecessárias
    df_saude = df_saude.drop(columns=colunas_remover_saude, errors="ignore")

    saude_export = "estabelecimento_saude_filtrado_geolocalizado.csv"
    df_saude.to_csv(saude_export, index=False, encoding="utf-8-sig", sep=",")
    print(f"Sucesso! Planilha salva como '{saude_export}'.")

except FileNotFoundError:
    print(f"Erro: O arquivo '{arquivo_saude}' não foi encontrado.")
except Exception as e:
    print(f"Ocorreu um erro ao processar '{arquivo_saude}': {e}")


# =======================================================
# 2. Processamento da planilha de Escolas
# =======================================================
try:
    print(f"\n--- Iniciando o processamento de '{arquivo_escolas}' ---")

    conteudo_corrigido = limpar_linhas_csv(arquivo_escolas)
    df_escolas = pd.read_csv(io.StringIO(conteudo_corrigido), sep=",")
    df_escolas.columns = df_escolas.columns.str.strip()

    # TRANSFORMAÇÕES
    # 1. Unifica as categorias
    df_escolas["Categoria Administrativa"] = df_escolas.apply(
        unificar_categoria_escola, axis=1
    )

    # 2. Dropa a coluna 'Dependência Administrativa'
    if "Dependência Administrativa" in df_escolas.columns:
        df_escolas = df_escolas.drop(columns=["Dependência Administrativa"])

    df_escolas["Latitude"] = pd.to_numeric(df_escolas["Latitude"], errors="coerce")
    df_escolas["Longitude"] = pd.to_numeric(df_escolas["Longitude"], errors="coerce")

    # 3. Preenche as coordenadas manuais antes de buscar na API
    print("Aplicando coordenadas manuais da base de Escolas...")
    df_escolas = preencher_coordenadas_manuais(
        df_escolas, coordenadas_manuais_escolas, "Latitude", "Longitude"
    )

    # Verifica o que ainda falta
    mask_escolas = df_escolas["Latitude"].isna() | df_escolas["Longitude"].isna()
    linhas_sem_coord_escolas = df_escolas[mask_escolas]

    if not linhas_sem_coord_escolas.empty:
        print(
            f"Encontradas {len(linhas_sem_coord_escolas)} linhas sem coordenadas. Iniciando geocodificação via API..."
        )
        for index, row in linhas_sem_coord_escolas.iterrows():
            endereco = str(row["Endereço"]) if pd.notna(row["Endereço"]) else ""
            linha_excel = index + 2

            lat, lon = obter_coordenadas(endereco)
            if lat is not None and lon is not None:
                df_escolas.at[index, "Latitude"] = lat
                df_escolas.at[index, "Longitude"] = lon
                print(f"OK API (Linha {linha_excel}) -> {endereco[:40]}...")
            else:
                falhas_escolas.append((linha_excel, endereco))
                print(f"FALHA API (Linha {linha_excel}) -> Não encontrado")
    else:
        print("Todas as linhas já possuem Latitude e Longitude.")

    # Remove colunas desnecessárias
    df_escolas = df_escolas.drop(columns=colunas_remover_escolas, errors="ignore")

    escolas_export = "escolas_com_bairro_filtrado_geolocalizado.csv"
    df_escolas.to_csv(escolas_export, index=False, encoding="utf-8-sig", sep=",")
    print(f"Sucesso! Planilha salva como '{escolas_export}'.")

except FileNotFoundError:
    print(f"Erro: O arquivo '{arquivo_escolas}' não foi encontrado.")
except Exception as e:
    print(f"Ocorreu um erro ao processar '{arquivo_escolas}': {e}")


# =======================================================
# 3. Relatório Final de Falhas
# =======================================================
print("\n====================================================================")
print("             RELATÓRIO DE ENDEREÇOS NÃO ENCONTRADOS")
print("====================================================================")

if falhas_saude:
    print(f"\n[ SAÚDE ] - {len(falhas_saude)} endereço(s) não encontrado(s) pela API:")
    for linha, endereco in sorted(falhas_saude, key=lambda x: x[0]):
        print(f"Linha {linha:03d} | {endereco}")
else:
    print("\n[ SAÚDE ] - Todos os endereços pesquisados foram encontrados com sucesso!")

if falhas_escolas:
    print(
        f"\n[ ESCOLAS ] - {len(falhas_escolas)} endereço(s) não encontrado(s) pela API:"
    )
    for linha, endereco in sorted(falhas_escolas, key=lambda x: x[0]):
        print(f"Linha {linha:03d} | {endereco}")
else:
    print(
        "\n[ ESCOLAS ] - Todos os endereços pesquisados foram encontrados com sucesso!"
    )

print("\nProcessamento finalizado!")
