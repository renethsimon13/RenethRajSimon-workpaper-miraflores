"""Append-only event store. Postgres in production (DATABASE_URL), SQLite locally.

Nothing is ever updated or deleted: corrections, undo, reopening and amendments
are all new events. That is what makes 'who, why, when', version comparison and
'what changed since I last looked' fall out for free.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, Integer, LargeBinary, MetaData, String, Table, Text, create_engine, insert,
                        select)

_url = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(__file__), "..", "workpaper.db"))
if _url.startswith("postgres://"):
    _url = "postgresql+psycopg://" + _url[len("postgres://"):]
elif _url.startswith("postgresql://"):
    _url = "postgresql+psycopg://" + _url[len("postgresql://"):]

engine = create_engine(_url, pool_pre_ping=True, future=True)
meta = MetaData()

events = Table(
    "events", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", String(40), nullable=False),
    Column("actor", String(40), nullable=False),
    Column("type", String(60), nullable=False),
    Column("entity", String(200)),
    Column("batch", String(40)),
    Column("payload", Text, nullable=False),
)

files = Table(
    "files", meta,
    Column("id", String(40), primary_key=True),
    Column("name", String(300)),
    Column("mime", String(120)),
    Column("size", Integer),
    Column("uploaded_by", String(40)),
    Column("ts", String(40)),
    Column("data", LargeBinary),
)

meta.create_all(engine)
_lock = threading.Lock()
_cache: list[dict] | None = None
_listeners: list = []


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _row(r):
    return {"id": r.id, "ts": r.ts, "actor": r.actor, "type": r.type, "entity": r.entity, "batch": r.batch,
            "payload": json.loads(r.payload)}


def all_events() -> list[dict]:
    global _cache
    with _lock:
        if _cache is None:
            with engine.connect() as c:
                _cache = [_row(r) for r in c.execute(select(events).order_by(events.c.id))]
        return list(_cache)


def refresh():
    global _cache
    with _lock:
        _cache = None


def append(actor: str, type_: str, payload: dict, entity: str | None = None, batch: str | None = None,
           ts: str | None = None) -> dict:
    global _cache
    with _lock:
        with engine.begin() as c:
            res = c.execute(insert(events).values(ts=ts or now_iso(), actor=actor, type=type_, entity=entity,
                                                  batch=batch, payload=json.dumps(payload)))
            eid = res.inserted_primary_key[0]
        ev = {"id": eid, "ts": ts or now_iso(), "actor": actor, "type": type_, "entity": entity, "batch": batch,
              "payload": payload}
        if _cache is not None:
            _cache.append(ev)
    for fn in list(_listeners):
        try:
            fn(ev)
        except Exception:
            pass
    return ev


def reset():
    global _cache
    with _lock:
        with engine.begin() as c:
            c.execute(events.delete())
            c.execute(files.delete())
        _cache = []


def save_file(name, mime, data: bytes, uploaded_by) -> dict:
    fid = new_id("file")
    with engine.begin() as c:
        c.execute(insert(files).values(id=fid, name=name, mime=mime, size=len(data), uploaded_by=uploaded_by,
                                       ts=now_iso(), data=data))
    return {"id": fid, "name": name, "mime": mime, "size": len(data)}


def get_file(fid):
    with engine.connect() as c:
        r = c.execute(select(files).where(files.c.id == fid)).first()
        return r


def subscribe(fn):
    _listeners.append(fn)
    return lambda: _listeners.remove(fn)
