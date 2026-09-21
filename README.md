# Relatório de Adesões — Ata de Registro de Preços

Página web única (HTML/CSS/JS, sem backend) para análise descritiva e
estatística dos pedidos de adesão (caronas) por item de uma Ata de Registro
de Preços exportada do [Contratos.gov.br](https://contratos.gov.br).

## O que o relatório mostra

- Dados gerais da ata (número, órgão, unidade gerenciadora, fornecedor, vigência, valor)
- KPIs: total de itens, itens com participante registrado, itens com pedido
  pendente de análise, total de participações e % de itens que aceitam adesão
- Gráficos: itens com mais unidades participantes e unidades que mais aderiram
- Tabela de **itens com pedidos de adesão**, com busca por item/código/descrição,
  alternância entre "participantes registrados" / "pedidos pendentes" / "todos",
  e exportação para CSV/Excel

## Como usar

### 1. Gerar os dados a partir do relatório bruto

O relatório do Contratos.gov.br é exportado como texto (`.txt`). Rode o
parser para transformá-lo em `data/data.json`:

```bash
python3 parse_ata.py caminho/para/relatorio.txt -o data/data.json
```

### 2. Servir a página localmente

Como a página carrega `data/data.json` via `fetch`, é preciso um servidor
HTTP local (não funciona abrindo o `index.html` direto no navegador via
`file://`):

```bash
python3 -m http.server 8000
```

Depois abra http://localhost:8000 no navegador.

### 3. Publicar no GitHub Pages

1. Faça commit do `index.html`, `parse_ata.py` e `data/data.json`
2. No GitHub: Settings → Pages → Deploy from branch → `main` / `/ (root)`
3. A página fica disponível em `https://<usuario>.github.io/<repo>/`

Para atualizar com uma nova Ata, gere um novo `data/data.json` (passo 1) e
faça commit — a página é 100% estática e lê o JSON automaticamente.

## Estrutura

```
index.html      página única (HTML + CSS + JS, usa Chart.js via CDN)
parse_ata.py    parser do relatório .txt em data/data.json
data/data.json  dados estruturados consumidos pela página
```
