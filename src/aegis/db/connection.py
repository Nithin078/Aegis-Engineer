"""SQLite engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from aegis.db.migrations import apply_migrations

_engines: dict[str, Engine] = {}


def get_engine(db_path: Path | str, *, echo: bool = False) -> Engine:
    """Get or create a SQLite engine for the given path. Auto-migrates once."""
    path = Path(db_path).expanduser().resolve()
    key = str(path)
    if key not in _engines:
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False allows use from async later; still single-writer SQLite.
        engine = create_engine(
            f"sqlite:///{path}",
            echo=echo,
            connect_args={"check_same_thread": False},
        )
        apply_migrations(engine)
        _engines[key] = engine
    return _engines[key]


def reset_engine_cache() -> None:
    """Drop cached engines (used in tests)."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()


@contextmanager
def get_session(db_path: Path | str, *, echo: bool = False) -> Iterator[Session]:
    """Yield a SQLModel session bound to the given database path."""
    engine = get_engine(db_path, echo=echo)
    with Session(engine) as session:
        yield session


def init_db(db_path: Path | str, *, echo: bool = False) -> Engine:
    """Ensure the database file exists and schema is applied."""
    return get_engine(db_path, echo=echo)
