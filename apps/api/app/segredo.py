"""Cifra segredos guardados no banco (como a chave da instância do WhatsApp).

A chave de cifra vem do INTERNAL_JWT_SECRET, que a API e o worker já têm. Se ele mudar, o
segredo guardado fica ilegível e precisa ser cadastrado de novo no /admin.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SegredoIlegivel(Exception):
    pass


def _fernet(segredo_app: str) -> Fernet:
    if not segredo_app:
        raise SegredoIlegivel("INTERNAL_JWT_SECRET não definido")
    chave = hashlib.sha256(f"analisebolsa:segredos:{segredo_app}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(valor: str, segredo_app: str) -> str:
    return _fernet(segredo_app).encrypt(valor.encode()).decode()


def decifrar(cifrado: str, segredo_app: str) -> str:
    try:
        return _fernet(segredo_app).decrypt(cifrado.encode()).decode()
    except InvalidToken as e:
        raise SegredoIlegivel("não foi possível ler a chave guardada") from e
