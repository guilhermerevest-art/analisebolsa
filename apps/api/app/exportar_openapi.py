"""Gera o OpenAPI da API: `python -m app.exportar_openapi caminho/openapi.json`."""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    conteudo = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"
    if destino:
        destino.write_text(conteudo, encoding="utf-8")
    else:
        sys.stdout.write(conteudo)


if __name__ == "__main__":
    main()
