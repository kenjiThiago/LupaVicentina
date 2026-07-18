# Lupa Vicentina

## Estrutura do Projeto

```text
├── dados.zip                   # Extraia este arquivo para gerar a pasta 'dados/'
├── codigo/
│   └── scripts/
│       └── process_census_data.py  # Script de processamento principal
└── README.md
```

## Configuração do Ambiente

**1. Extraia os dados**
Descompacte o arquivo `dados.zip` na raiz do projeto. Isso deve criar uma pasta chamada `dados/` com os arquivos CSV originais.

**2. Crie o ambiente virtual (venv)**
```bash
python -m venv venv
```

**3. Ative o ambiente virtual**
*   No **Windows**:
    ```bash
    venv\Scripts\activate
    ```
*   No **Linux/Mac**:
    ```bash
    source venv/bin/activate
    ```

**4. Instale as bibliotecas necessárias**
```bash
pip install -r requirements.txt
```

## Como Executar

Com o ambiente ativado e as dependências instaladas, rode o script:

```bash
python codigo/scripts/process_census_data.py
```

Após a execução, o arquivo final processado `dados_censo_limpos.csv` será criado dentro da pasta `dados/`.
