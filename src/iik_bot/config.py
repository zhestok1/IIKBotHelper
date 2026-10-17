import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    database_path: Path
    content_path: Path | None
    log_level: str

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(Path.cwd() / ".env", override=False)
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL должен быть DEBUG, INFO, WARNING, ERROR или CRITICAL")
        return cls(
            token=os.getenv("BOT_TOKEN", "").strip(),
            database_path=Path(os.getenv("DATABASE_PATH", "data/bot.sqlite3")),
            content_path=Path(p) if (p := os.getenv("CONTENT_PATH")) else None,
            log_level=level,
        )
