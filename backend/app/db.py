"""SQLite engine + session helpers. File-based so `make demo` needs no server."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# check_same_thread=False so FastAPI's threadpool can share the engine.
engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables. Import models first so they register on SQLModel."""
    from . import models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)


def reset_db() -> None:
    """Drop and recreate — used by the synthetic data generator."""
    from . import models  # noqa: F401

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    # expire_on_commit=False keeps ORM objects readable after commit, so the
    # demo scripts and API can build reports without re-querying.
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def session_dep() -> Iterator[Session]:
    """FastAPI dependency: yields a session, commits on success."""
    with get_session() as s:
        yield s
