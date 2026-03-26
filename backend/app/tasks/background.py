"""Background task system with ThreadPoolExecutor.

Manages async task execution for long-running operations like PDF extraction.
"""

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Task

# Max 3 Worker fuer parallele Tasks
_executor = ThreadPoolExecutor(max_workers=3)


def _get_db() -> Session:
    """Eigene DB-Session fuer Background-Threads (nicht FastAPI-Dependency)."""
    return SessionLocal()


def update_task(task_id: str, **kwargs):
    """Update task fields in the database."""
    db = _get_db()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            for key, value in kwargs.items():
                setattr(task, key, value)
            db.commit()
    finally:
        db.close()


def run_in_background(bg_task_id: str, fn: Callable, *args, **kwargs):
    """Submit a function to run in a background thread.

    The function receives a `on_progress(pct, message)` callback as first argument,
    followed by *args and **kwargs.

    On success: sets status=completed, progress=100
    On failure: sets status=failed, error=traceback
    """

    def _wrapper():
        def on_progress(pct: int, message: str):
            update_task(bg_task_id, progress=min(pct, 99), message=message, status="running")

        update_task(bg_task_id, status="running", progress=0, message="Gestartet")

        try:
            result_path = fn(on_progress, *args, **kwargs)
            update_task(
                bg_task_id,
                status="completed",
                progress=100,
                message="Fertig",
                result_path=str(result_path) if result_path else None,
            )
        except Exception:
            tb = traceback.format_exc()
            update_task(bg_task_id, status="failed", error=tb, message="Fehler")

    _executor.submit(_wrapper)
