"""Telefone para o WhatsApp: normaliza para E.164 sem o "+" e mascara para exibição (puro)."""

import re


def normalizar_telefone(valor: str) -> str | None:
    """Aceita "(11) 98765-4321", "+55 11 98765-4321" etc. Sem DDI, assume o Brasil (55).

    Devolve só dígitos com o DDI ("5511987654321"), ou None se não parece um telefone.
    """
    texto = valor.strip()
    digitos = re.sub(r"\D", "", texto)
    internacional = texto.startswith("+") or texto.startswith("00")
    if texto.startswith("00"):
        digitos = digitos[2:]
    if not internacional:
        # Sem "+" ou "00", é um número brasileiro: com ou sem o 0 de longa distância e o 55.
        if digitos.startswith("0"):
            digitos = digitos[1:]
        if len(digitos) in (10, 11):
            digitos = "55" + digitos
        elif not (digitos.startswith("55") and len(digitos) in (12, 13)):
            return None
    if digitos.startswith("55"):
        nacional = digitos[2:]
        # DDD de 11 a 99; celular com 9 dígitos começando por 9, ou fixo com 8.
        if not re.fullmatch(r"[1-9][1-9](9\d{8}|[2-8]\d{7})", nacional):
            return None
        return digitos
    return digitos if 8 <= len(digitos) <= 15 else None


def mascarar_telefone(e164: str) -> str:
    """ "5511987654321" -> "+55 (11) 9****-4321"."""
    if e164.startswith("55") and len(e164) in (12, 13):
        ddd, numero = e164[2:4], e164[4:]
        return f"+55 ({ddd}) {numero[0]}****-{numero[-4:]}"
    return f"+{e164[:2]} ****{e164[-4:]}"
