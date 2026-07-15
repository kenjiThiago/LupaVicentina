import pandas as pd
from geopy.geocoders import Nominatim
import time


def normalizar_coordenada(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, str):
        valor = valor.strip().replace(",", ".")
        if valor == "":
            return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


# 1. Inicializa o serviço de busca de endereços (geocoder)
# Crie um user_agent com o nome do seu projeto
geolocator = Nominatim(user_agent="meu_mapa_escolas")

# =====================================================================
# AJUSTE 1: Coloque o nome correto do seu arquivo CSV aqui
# =====================================================================
nome_do_arquivo = "escolas.csv"
df = pd.read_csv(nome_do_arquivo)

print("Visualizando as primeiras linhas para confirmar a leitura:")
print(df.head())
print("-" * 50)


# 2. Função que recebe latitude/longitude e devolve o bairro
def obter_bairro(lat, lon):
    lat = normalizar_coordenada(lat)
    lon = normalizar_coordenada(lon)

    if lat is None or lon is None:
        return None

    # Corrige linhas em que latitude/longitude vieram invertidas.
    if abs(lat) > 90 and abs(lon) <= 90:
        lat, lon = lon, lat

    # Evita chamadas inválidas para o geocoder.
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None

    try:
        # Consulta a coordenada no OpenStreetMap
        location = geolocator.reverse((lat, lon), timeout=10)
        if location is None:
            return None
        address = location.raw.get("address", {})

        # O bairro pode estar em diferentes chaves dependendo de como foi mapeado
        bairro = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("city_district")
        )

        # IMPORTANTE: Pausa de 1 segundo para respeitar o limite da API gratuita
        time.sleep(1)

        return bairro
    except Exception as e:
        print(f"Erro ao buscar bairro para as coordenadas {lat}, {lon}: {e}")
        # Se der erro (ex: falha de internet), devolve vazio e continua
        return None


# =====================================================================
# AJUSTE 2: Verifique se o nome das colunas de latitude e longitude
# estão exatamente iguais aos que estão na sua planilha (maiúsculas/minúsculas importam).
# =====================================================================
coluna_latitude = "Latitude"
coluna_longitude = "Longitude"

print("\nBuscando os bairros... (isso vai levar 1 segundo por linha da planilha)")

# 3. Aplica a função em cada linha do DataFrame e cria a nova coluna 'bairro_encontrado'
df["bairro_encontrado"] = df.apply(
    lambda linha: obter_bairro(linha[coluna_latitude], linha[coluna_longitude]), axis=1
)

# =====================================================================
# AJUSTE 3: Nome do novo arquivo que será salvo com os bairros
# =====================================================================
nome_arquivo_saida = "escolas_completo.csv"

# 4. Salva o novo DataFrame em um arquivo CSV (index=False evita criar uma coluna extra de numeração)
df.to_csv(nome_arquivo_saida, index=False)

print(f"\nPronto! Planilha salva com sucesso como: {nome_arquivo_saida}")
