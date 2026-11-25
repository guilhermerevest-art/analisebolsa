"""O pacote da função na Vercel não pode deixar de fora módulos que a API importa."""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _ignorados() -> set[str]:
    linhas = (RAIZ / ".vercelignore").read_text().splitlines()
    return {linha.strip().strip("/") for linha in linhas if linha.strip()}


def _imports_locais(pasta: Path) -> set[str]:
    locais = {p.name for p in RAIZ.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    achados: set[str] = set()
    for arquivo in pasta.rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text())):
            if isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
                nomes = [no.module]
            elif isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            else:
                continue
            achados |= {n.split(".")[0] for n in nomes} & locais
    return achados


def test_api_nao_importa_pacote_ignorado_na_vercel():
    vistos: set[str] = set()
    fila = ["app"]
    while fila:
        pacote = fila.pop()
        if pacote in vistos:
            continue
        vistos.add(pacote)
        fila.extend(_imports_locais(RAIZ / pacote) - vistos)
    assert not (vistos & _ignorados()), vistos & _ignorados()
