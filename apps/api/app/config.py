"""Configuração lida das variáveis de ambiente (seção 8 da spec)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/analisebolsa_dev"
    internal_jwt_secret: str = ""
    # Chave enviada pela web em X-Internal-Key. Obrigatória quando a API fica exposta (Vercel).
    internal_api_key: str = ""
    # Sem pool próprio e sem prepared statements, para o pooler do Postgres em serverless.
    db_serverless: bool = False
    web_internal_url: str = ""
    brapi_token: str = ""
    fontes_cotacoes: str = "yahoo,brapi"
    fontes_proventos: str = "brapi,yahoo"
    http_timeout_s: float = 20.0
    pausa_entre_tickers_s: float = 0.3
    # Push (Web Push): chaves VAPID geradas com `python -m app.notificacao vapid`. A pública vai
    # para o navegador; a privada só assina os envios. Sem as duas, o push fica desligado.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    # Contato exigido pelos serviços de push ("mailto:..." ou "https://..."); sem ele, o site.
    vapid_contato: str = ""
    # WhatsApp Cloud API (Meta): token do usuário do sistema e id do número de envio. Sem os
    # dois, o WhatsApp fica desligado. Os modelos precisam estar aprovados no WhatsApp Manager.
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_url: str = "https://graph.facebook.com"
    whatsapp_api_versao: str = "v23.0"
    whatsapp_modelo_alertas: str = "alertas_disparados"
    whatsapp_modelo_codigo: str = "codigo_verificacao"
    whatsapp_idioma: str = "pt_BR"
    # Endereço público do site, usado nos links enviados (cai para WEB_INTERNAL_URL).
    site_url: str = ""

    @property
    def url_publica(self) -> str:
        return (self.site_url or self.web_internal_url).rstrip("/")

    @property
    def lista_fontes_cotacoes(self) -> list[str]:
        return [f.strip() for f in self.fontes_cotacoes.split(",") if f.strip()]

    @property
    def lista_fontes_proventos(self) -> list[str]:
        return [f.strip() for f in self.fontes_proventos.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
