"""Simple schema migration helpers."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, select

from aegis.db.models import SchemaMeta

CURRENT_SCHEMA_VERSION = "1"


def apply_migrations(engine: object) -> None:
    """Create tables if needed and stamp schema version.

    Phase 1 uses create_all. Future versions will add versioned ALTER steps.
    """
    SQLModel.metadata.create_all(engine)  # type: ignore[arg-type]

    with Session(engine) as session:  # type: ignore[arg-type]
        row = session.get(SchemaMeta, "schema_version")
        if row is None:
            session.add(SchemaMeta(key="schema_version", value=CURRENT_SCHEMA_VERSION))
            session.commit()
        elif row.value != CURRENT_SCHEMA_VERSION:
            # Placeholder for future upgrade path.
            row.value = CURRENT_SCHEMA_VERSION
            session.add(row)
            session.commit()


def get_schema_version(engine: object) -> str | None:
    with Session(engine) as session:  # type: ignore[arg-type]
        row = session.exec(select(SchemaMeta).where(SchemaMeta.key == "schema_version")).first()
        return row.value if row else None
