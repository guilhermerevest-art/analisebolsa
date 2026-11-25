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

    @property
    def lista_fontes_cotacoes(self) -> list[str]:
        return [f.strip() for f in self.fontes_cotacoes.split(",") if f.strip()]

    @property
    def lista_fontes_proventos(self) -> list[str]:
        return [f.strip() for f in self.fontes_proventos.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
