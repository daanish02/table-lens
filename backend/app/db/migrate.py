from pathlib import Path
from sqlalchemy import text, Engine

from app.logging.logger import get_logger

log = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(engine: Engine) -> None:
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        log.info("migrate.apply", file=path.name)
        with engine.connect() as conn:
            conn.execute(text(path.read_text()))
            conn.commit()
