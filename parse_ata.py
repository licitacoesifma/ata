"""
Parser do relatório "Ata de Registro de Preços" (Contratos.gov.br) em texto
puro para um data.json estruturado, consumido pela página estática (index.html).

Uso:
    python3 parse_ata.py <arquivo_origem.txt> [-o data/data.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

NOISE_LINE_PATTERNS = [
    re.compile(r"^## \d+/\d+$"),
    re.compile(r"gerado através do Contratos\.gov\.br"),
]


def clean_text(raw: str) -> str:
    lines = raw.splitlines()
    kept = []
    for i, line in enumerate(lines):
        if any(p.search(line) for p in NOISE_LINE_PATTERNS):
            continue
        # remove o cabeçalho de página repetido (aparece página a página)
        if line.strip() == "Relatório Ata de Registro de Preços":
            continue
        if line.startswith("Unidade Gerenciadora "):
            continue
        kept.append(line)
    return "\n".join(kept)


def to_number(value: str):
    if value is None:
        return None
    v = value.strip().replace(".", "").replace(",", ".")
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return value.strip()


def parse_header(text: str) -> dict:
    header = {}

    m = re.search(r"nº\s*(\d+/\d+)(\d{2}/\d{2}/\d{4})(https://\S+)", text)
    if m:
        header["ata_numero"] = m.group(1)
        header["ultima_atualizacao"] = m.group(2)
        header["link_pncp"] = m.group(3)

    m = re.search(r"de (\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4})", text)
    if m:
        header["vigencia_inicial"] = m.group(1)
        header["vigencia_final"] = m.group(2)

    m = re.search(
        r"VigênciaÓrgão:Unidade gerenciadora:\s*\n.*?\n((?:##.*\n)+?)## Valor Contratado:",
        text,
    )
    if m:
        block_lines = [l.strip("# ").strip() for l in m.group(1).splitlines() if l.strip("# ").strip()]
        # a última linha "## CODIGO - NOME" é a unidade gerenciadora; o resto é o órgão
        if block_lines:
            header["unidade_gerenciadora"] = block_lines[-1]
            header["orgao"] = " ".join(block_lines[:-1])

    m = re.search(r"Valor Contratado:\s*\n## (R\$ [\d.,]+)", text)
    if m:
        header["valor_contratado"] = m.group(1)

    m = re.search(r"## Fornecedor\s*\n## (.+)", text)
    if m:
        header["fornecedor_principal"] = m.group(1).strip()

    m = re.search(r"## Objeto:\s*\n((?:.+\n)+?)## \d", text)
    if m:
        header["objeto"] = " ".join(l.strip() for l in m.group(1).splitlines() if l.strip())

    m = re.search(
        r"Número da compra / Ano:Modalidade da compra:Data da assinatura:\s*\n## (\d+/\d{4})(\d{2}\s*-\s*[^\d]+?)(\d{2}/\d{2}/\d{4})",
        text,
    )
    if m:
        header["compra_numero_ano"] = m.group(1)
        header["compra_modalidade"] = m.group(2).strip()
        header["compra_data_assinatura"] = m.group(3)

    return header


UNIT_LINE_RE = re.compile(r"^(\d+)(.*?)(Participante|Gerenciadora)(\d*)$")


def parse_units_block(block_text: str):
    units = []
    for line in block_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("CódigoUnidadeTipo da unidade"):
            continue
        m = UNIT_LINE_RE.match(line)
        if m:
            codigo, nome, tipo, _resto = m.groups()
            units.append({
                "codigo": codigo,
                "nome": nome.strip(),
                "tipo": tipo,
            })
    return units


def parse_items(text: str):
    items = []
    blocks = re.split(r"## DETALHAMENTO DO ITEM (\d+)", text)
    # re.split with a capturing group returns: [pre, num1, block1, num2, block2, ...]
    for i in range(1, len(blocks), 2):
        numero = blocks[i]
        block = blocks[i + 1]

        item = {"numero": numero}

        m = re.search(r"detalhada:\s*(.*?)Código do\s*item:", block, re.DOTALL)
        if m:
            desc_lines = [l.strip("# ").strip() for l in m.group(1).splitlines() if l.strip("# ").strip()]
            item["descricao"] = " ".join(desc_lines)

        m = re.search(r"Código do\s*item:\s*##\s*(\d+)", block)
        if m:
            item["codigo_catalogo"] = m.group(1)

        m = re.search(r"Tipo do item:\s*##\s*(\S+)", block)
        if m:
            item["tipo"] = m.group(1)

        m = re.search(r"Quantidade\s+homologada:\s*##\s*([\d.,]+)", block)
        if m:
            item["qtd_homologada"] = to_number(m.group(1))

        m = re.search(r"Vigência inicial:\s*##\s*([\d/]+)", block)
        if m:
            item["vigencia_inicial"] = m.group(1)

        m = re.search(r"Vigência final:\s*##\s*([\d/]+)", block)
        if m:
            item["vigencia_final"] = m.group(1)

        # bloco de unidades (Gerenciadora + Participantes)
        m = re.search(
            r"UNIDADE\(S\) ITEM.*?\n(.*?)(?:ADESÕES\(S\) ITEM|EMPENHO\(S\) ITEM|CONTRATO\(S\) ITEM|$)",
            block,
            re.DOTALL,
        )
        unidades = parse_units_block(m.group(1)) if m else []
        item["unidades"] = unidades
        item["participantes"] = [u for u in unidades if u["tipo"] == "Participante"]
        item["qtd_participantes"] = len(item["participantes"])

        # bloco de adesões
        m = re.search(
            r"ADESÕES\(S\) ITEM.*?\n(.*?)(?:EMPENHO\(S\) ITEM|CONTRATO\(S\) ITEM|## DETALHAMENTO|$)",
            block,
            re.DOTALL,
        )
        ades_text = m.group(1) if m else ""

        m = re.search(r"máxima para adesão\s*##\s*([\d.,]+)", ades_text)
        item["qtd_maxima_adesao"] = to_number(m.group(1)) if m else None

        m = re.search(r"disponivel para adesão:\s*##\s*([\d.,]+)", ades_text)
        item["qtd_disponivel_adesao"] = to_number(m.group(1)) if m else None

        m = re.search(r"aguardando análise:\s*##\s*([\d.,]+)", ades_text)
        item["qtd_aguardando_analise"] = to_number(m.group(1)) if m else None

        m = re.search(r"Aceita adesão\s*##\s*(Sim|Não)", ades_text)
        item["aceita_adesao"] = m.group(1) if m else None

        item["tem_participante_registrado"] = item["qtd_participantes"] > 0
        aguardando = item["qtd_aguardando_analise"] or 0
        item["tem_pedido_pendente"] = isinstance(aguardando, (int, float)) and aguardando > 0
        item["teve_pedido_adesao"] = item["tem_participante_registrado"] or item["tem_pedido_pendente"]

        items.append(item)

    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origem", type=Path, help="arquivo .txt bruto do Contratos.gov.br")
    parser.add_argument("-o", "--saida", type=Path, default=Path("data/data.json"))
    args = parser.parse_args()

    raw = args.origem.read_text(encoding="utf-8")
    text = clean_text(raw)

    header = parse_header(text)
    items = parse_items(text)

    resultado = {
        "gerado_em": None,
        "ata": header,
        "itens": items,
        "resumo": {
            "total_itens": len(items),
            "itens_aceita_adesao": sum(1 for it in items if it.get("aceita_adesao") == "Sim"),
            "itens_com_participante_registrado": sum(1 for it in items if it["tem_participante_registrado"]),
            "itens_com_pedido_pendente": sum(1 for it in items if it["tem_pedido_pendente"]),
            "total_participacoes": sum(it["qtd_participantes"] for it in items),
        },
    }

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: {len(items)} itens processados -> {args.saida}", file=sys.stderr)
    print(json.dumps(resultado["resumo"], ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
