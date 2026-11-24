import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import schemas as s
from app.db import get_engine
from app.erros import Problema

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health", response_model=s.Health, summary="Healthcheck com ping no banco")
def health():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        log.warning("healthcheck: banco indisponível: %s", e)
        raise Problema(503, "banco de dados indisponível") from e
    return {"status": "ok", "banco": "ok"}
