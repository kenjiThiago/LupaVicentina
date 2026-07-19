# 🌿 Dashboard COOP Clima São Vicente

Painel web **100% estático** de utilidade pública para os moradores de São Vicente (SP):
demografia, escolas e unidades de saúde, bairro a bairro. Não há backend nem banco de
dados — um script de ETL em Python lê as planilhas, trata os dados e **gera um único
`index.html` com todos os dados JSON embutidos**, pronto para hospedar no GitHub Pages.

## Estrutura do projeto

```
dashboard/
├── dados_tratados/
│   ├── dados_censo_limpos.csv           # demografia por bairro (Censo)
│   ├── escolas_final.csv                # catálogo de escolas
│   └── estabelecimento_saude_final.csv  # estabelecimentos de saúde (CNES)
├── etl.py            # script de ETL: lê os CSVs, trata e injeta o JSON no template
├── template.html     # template do dashboard (HTML/CSS/JS + marcador __DATA_JSON__)
├── index.html        # ARQUIVO FINAL gerado pelo ETL (não editar à mão)
└── README.md
```

## Como executar

### 1. Pré-requisitos

- Python 3.9 ou superior
- Pandas: `pip install pandas`

### 2. Gerar o dashboard

```bash
cd dashboard
python etl.py
```

Saída esperada:

```
OK: index.html gerado.
  bairros do censo: 29 | escolas: 241 | saúde: 427
  bairros extras (sem censo): 15
  registros sem coordenada válida (fora do mapa): 47
```

### 3. Visualizar localmente

Basta abrir o `index.html` no navegador, ou servir a pasta:

```bash
python -m http.server 8123
# depois acesse http://localhost:8123
```

### 4. Publicar no GitHub Pages

1. Faça commit do `index.html` gerado no repositório.
2. Em **Settings → Pages**, aponte para a branch/pasta que contém o `index.html`.
3. Pronto — o painel fica disponível em `https://<usuario>.github.io/<repo>/`.

Para atualizar os dados no futuro: substitua os CSVs em `dados_tratados/`, rode
`python etl.py` de novo e faça commit do novo `index.html`.

## O que o painel oferece

- **Filtro global por bairro** (dropdown) — KPIs, gráficos, mapa e tabelas atualizam sem recarregar a página.
- **KPIs:** população, renda média (salários mínimos), densidade (hab/ha), escolas ativas, capacidade estimada de matrículas, unidades de saúde e unidades de saúde por 10 mil habitantes.
- **Gráficos (Chart.js):** composição populacional por cor/raça, escolas por categoria administrativa, oferta de ensino por etapa/modalidade, porte das escolas, serviços de saúde disponíveis e cobertura SUS.
- **Mapa interativo (Leaflet + OpenStreetMap):** escolas públicas (laranja), escolas privadas (azul), saúde SUS (verde) e demais unidades de saúde (marrom), com controle de camadas e popups de detalhes.
- **Rankings:** TOP 10 bairros por escolas, por unidades de saúde e por densidade demográfica.
- **Tabelas de detalhamento** em abas (Escolas / Saúde), com busca por nome, endereço ou bairro.

## Decisões de tratamento de dados (ETL)

| Problema encontrado nos dados | Tratamento aplicado |
|---|---|
| Nomes de bairro divergentes entre as bases (`Catiapoã` × `CATIAPOA`, abreviações `JD`/`PQ`/`VL`/`CJTO`, nomes truncados em 20 caracteres como `ESPLANADA DOS BARREI`) | Normalização (maiúsculas, sem acento, abreviações expandidas), tabela de apelidos (`VILA JOQUEI CLUBE` → `Jóckey Club` etc.) e casamento por prefixo para nomes truncados |
| Coordenadas da base de saúde sem ponto decimal (ex.: `-239575481911.0`) | Divisão sucessiva por 10 até a magnitude correta |
| Pontos geocodificados fora de São Vicente (ex.: escola em Araçatuba) | Excluídos do mapa (continuam nas tabelas); a legenda informa quantos ficaram de fora |
| 23 escolas paralisadas | Ficam nas tabelas com status "Paralisada", mas fora dos KPIs e gráficos |
| Porte "Mais de 1000 matrículas" (faixa aberta) | Capacidade contabilizada como 1.000 (piso da faixa) — por isso o KPI mostra "≈" |
| Bairros presentes só nas bases de escolas/saúde (ex.: Vila Mateo Bei) | Aparecem no dropdown em "Outros bairros (sem dados do censo)": mapa e tabelas funcionam; indicadores demográficos exibem "–" |
| Renda média da cidade | Média por bairro **ponderada pela população** |

## Identidade visual

- **Cores institucionais:** verde `#007a4a`, marrom `#874a33`, azul claro `#00a3e0`, laranja `#e87722`; fundo off-white `#f9f3f0` e verde escuro `#1a3c2c` em cabeçalho/rodapé.
- **Tipografia:** [Londrina Solid](https://fonts.google.com/specimen/Londrina+Solid) para títulos e [Roboto](https://fonts.google.com/specimen/Roboto) para textos, tabelas e KPIs (Google Fonts).
- Bibliotecas via CDN: Chart.js 4 e Leaflet 1.9 (necessário acesso à internet para carregar a página).
