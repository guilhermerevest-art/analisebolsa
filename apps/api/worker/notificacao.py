"""Envio de e-mail por SMTP, atrás de uma interface simples (troca de provedor = configuração)."""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol

from app.config import Settings


class Enviador(Protocol):
    def enviar(self, para: str, assunto: str, texto: str, html: str) -> None: ...


class EnviadorSmtp:
    def __init__(self, host: str, porta: int, usuario: str, senha: str, remetente: str):
        self.host, self.porta, self.usuario, self.senha = host, porta, usuario, senha
        self.remetente = remetente

    def enviar(self, para: str, assunto: str, texto: str, html: str) -> None:
        msg = EmailMessage()
        msg["From"] = formataddr(("analisebolsa", self.remetente))
        msg["To"] = para
        msg["Subject"] = assunto
        msg.set_content(texto)
        msg.add_alternative(html, subtype="html")
        if self.porta == 465:
            conexao = smtplib.SMTP_SSL(self.host, self.porta, timeout=30)
        else:
            conexao = smtplib.SMTP(self.host, self.porta, timeout=30)
        with conexao as smtp:
            if self.porta != 465:
                smtp.starttls()
            if self.usuario:
                smtp.login(self.usuario, self.senha)
            smtp.send_message(msg)


def enviador_configurado(settings: Settings) -> Enviador | None:
    if not settings.smtp_host or not settings.email_remetente:
        return None
    return EnviadorSmtp(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_usuario,
        settings.smtp_senha,
        settings.email_remetente,
    )
