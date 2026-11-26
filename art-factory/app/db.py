from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "factory.db"
LORA_DIR = DATA_DIR / "lora-dataset"
COMICS_DIR = DATA_DIR / "comics"

_LOCK = threading.RLock()

DEFAULT_DUAL_PARAMS: dict[str, Any] = {
    "krea_steps": 8,
    "moss_steps": 25,
    "moss_cfg": 2.5,
    "moss_denoise": 0.36,
    "lora_krea_tjfilm": 0.75,
    "lora_krea_realism": 0.5,
    "lora_krea_softlight": 0.55,
    "lora_krea_filter": 0.6,
}

WORKFLOW_PRESETS: dict[str, dict[str, Any]] = {
    "moss": {
        "preset": "moss",
        "label": "单 MOSS 二次元画师（快、省额度、偏纯二次元）",
        "model_id": "moss-image-sft",
        "workflow_key": "moss-image-sft-t2i",
        "workflow_version": "1.0.0",
    },
    "dual": {
        "preset": "dual",
        "label": "Krea-2 + MOSS 双画师（实景电影光影 + 二次元精修 + 4 滤镜 LoRA）",
        "model_id": "krea2-moss-dual",
        "workflow_key": "krea2-moss-dual-t2i",
        "workflow_version": "1.1.1",
    },
}

_WORKFLOW_ALIASES: dict[str, str] = {
    "moss": "moss",
    "moss-image-sft": "moss",
    "moss-image-sft-t2i": "moss",
    "single": "moss",
    "fast": "moss",
    "old": "moss",
    "单画师": "moss",
    "单moss": "moss",
    "旧工作流": "moss",
    "旧": "moss",
    "dual": "dual",
    "krea": "dual",
    "krea2": "dual",
    "krea2-moss": "dual",
    "krea2-moss-dual": "dual",
    "krea2-moss-dual-t2i": "dual",
    "film": "dual",
    "cinema": "dual",
    "new": "dual",
    "双画师": "dual",
    "双采样": "dual",
    "新工作流": "dual",
    "新": "dual",
}


def resolve_workflow_preset(name: str | None) -> dict[str, Any] | None:
    if not name or not isinstance(name, str):
        return None
    key = _WORKFLOW_ALIASES.get(name.strip().lower().replace("_", "-"))
    if not key:
        key = _WORKFLOW_ALIASES.get(name.strip())
    return dict(WORKFLOW_PRESETS[key]) if key else None


def describe_workflow(workflow_key: str, workflow_version: str = "", model_id: str = "") -> dict[str, Any]:
    for preset in WORKFLOW_PRESETS.values():
        if preset["workflow_key"] == workflow_key:
            return dict(preset)
    return {
        "preset": workflow_key,
        "label": f"{workflow_key} v{workflow_version}".strip(),
        "model_id": model_id,
        "workflow_key": workflow_key,
        "workflow_version": workflow_version,
    }


DEFAULT_SETTINGS: dict[str, Any] = {
    "cruise_enabled": True,
    "daily_count": int(os.environ.get("DEFAULT_DAILY_COUNT", "16")),
    "gpu_accelerator": os.environ.get("DEFAULT_GPU_ACCELERATOR", "L4"),
    "quality_threshold": float(os.environ.get("DEFAULT_QUALITY_THRESHOLD", "7.5")),
    "workflow_key": os.environ.get("DEFAULT_WORKFLOW_KEY", "moss-image-sft-t2i"),
    "workflow_version": os.environ.get("DEFAULT_WORKFLOW_VERSION", "1.0.0"),
    "model_id": os.environ.get("DEFAULT_MODEL_ID", "moss-image-sft"),
    "dual_params": dict(DEFAULT_DUAL_PARAMS),
    "default_persona": "温柔靠谱的黑长直二次元学姐讲师（深蓝学院风西装外套、白衬衫、酒红领结、琥珀色眼眸）与爱提问的呆萌短发助手（浅米色针织毛衣、元气表情）",
    "used_ref_images": [],
}


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LORA_DIR.mkdir(parents=True, exist_ok=True)
    COMICS_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS queue_items (
                id TEXT PRIMARY KEY,
                group_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                negative TEXT NOT NULL DEFAULT '',
                width INTEGER NOT NULL DEFAULT 1024,
                height INTEGER NOT NULL DEFAULT 576,
                steps INTEGER NOT NULL DEFAULT 35,
                cfg REAL NOT NULL DEFAULT 2.5,
                shift REAL NOT NULL DEFAULT 5.0,
                panel_index INTEGER NOT NULL DEFAULT 0,
                meta_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                run_id TEXT,
                studio_job_id TEXT,
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                trigger_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                job_count INTEGER NOT NULL DEFAULT 0,
                gpu_accelerator TEXT NOT NULL DEFAULT 'L4',
                max_runtime_minutes INTEGER NOT NULL DEFAULT 30,
                actual_units REAL,
                ccu_after REAL,
                summary_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                finished_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS outputs (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                group_id TEXT,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL DEFAULT '',
                score REAL,
                review TEXT DEFAULT '',
                public_url TEXT NOT NULL,
                folder TEXT NOT NULL,
                lora_saved INTEGER NOT NULL DEFAULT 0,
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_items(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_queue_run ON queue_items(run_id);
            CREATE INDEX IF NOT EXISTS idx_outputs_created ON outputs(created_at DESC);
            """
        )
        now = int(time.time())
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value_json, updated_at) VALUES (?, ?, ?)",
                (k, json.dumps(v, ensure_ascii=False), now),
            )


@contextmanager
def _connect():
    with _LOCK:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def get_settings() -> dict[str, Any]:
    out = dict(DEFAULT_SETTINGS)
    with _connect() as conn:
        for row in conn.execute("SELECT key, value_json FROM settings").fetchall():
            try:
                out[row["key"]] = json.loads(row["value_json"])
            except Exception:
                pass
    return out


def set_setting(key: str, value: Any) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (key, json.dumps(value, ensure_ascii=False), now),
        )


def enqueue_items(items: list[dict[str, Any]]) -> list[str]:
    now = int(time.time())
    ids: list[str] = []
    with _connect() as conn:
        for it in items:
            iid = it.get("id") or uuid.uuid4().hex[:16]
            ids.append(iid)
            conn.execute(
                """
                INSERT INTO queue_items(
                    id, group_id, kind, title, prompt, negative, width, height, steps, cfg, shift,
                    panel_index, meta_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    iid,
                    it["group_id"],
                    it["kind"],
                    it.get("title", "未命名"),
                    it["prompt"],
                    it.get("negative", ""),
                    int(it.get("width", 1024)),
                    int(it.get("height", 576)),
                    int(it.get("steps", 35)),
                    float(it.get("cfg", 2.5)),
                    float(it.get("shift", 5.0)),
                    int(it.get("panel_index", 0)),
                    json.dumps(it.get("meta") or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
    return ids


def list_queue(status: str | None = "pending", limit: int = 200) -> list[dict[str, Any]]:
    with _connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM queue_items WHERE status=? ORDER BY created_at ASC, panel_index ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM queue_items ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
        res.append(d)
    return res


def list_items_by_run(run_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM queue_items WHERE run_id=? ORDER BY created_at ASC, panel_index ASC",
            (run_id,),
        ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
        res.append(d)
    return res


def clear_pending_queue() -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM queue_items WHERE status='pending'")
        return cur.rowcount


def mark_items_submitted(item_ids: list[str], run_id: str, job_map: dict[str, str]) -> None:
    now = int(time.time())
    with _connect() as conn:
        for iid in item_ids:
            conn.execute(
                "UPDATE queue_items SET status='submitted', run_id=?, studio_job_id=?, updated_at=? WHERE id=?",
                (run_id, job_map.get(iid), now, iid),
            )


def update_item_status(item_id: str, status: str, error: str | None = None) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            "UPDATE queue_items SET status=?, error=?, updated_at=? WHERE id=?",
            (status, error, now, item_id),
        )


def create_run(trigger_kind: str, job_count: int, gpu_accelerator: str, max_runtime_minutes: int) -> str:
    rid = "run_" + uuid.uuid4().hex[:12]
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO runs(id, trigger_kind, status, job_count, gpu_accelerator, max_runtime_minutes, created_at, updated_at)
            VALUES (?, ?, 'submitting', ?, ?, ?, ?, ?)
            """,
            (rid, trigger_kind, job_count, gpu_accelerator, max_runtime_minutes, now, now),
        )
    return rid


def update_run(
    run_id: str,
    *,
    batch_id: str | None = None,
    status: str | None = None,
    actual_units: float | None = None,
    ccu_after: float | None = None,
    summary: dict[str, Any] | None = None,
    error: str | None = None,
    finished: bool = False,
) -> None:
    now = int(time.time())
    sets = ["updated_at=?"]
    vals: list[Any] = [now]
    if batch_id is not None:
        sets.append("batch_id=?")
        vals.append(batch_id)
    if status is not None:
        sets.append("status=?")
        vals.append(status)
    if actual_units is not None:
        sets.append("actual_units=?")
        vals.append(actual_units)
    if ccu_after is not None:
        sets.append("ccu_after=?")
        vals.append(ccu_after)
    if summary is not None:
        sets.append("summary_json=?")
        vals.append(json.dumps(summary, ensure_ascii=False))
    if error is not None:
        sets.append("error=?")
        vals.append(error)
    if finished:
        sets.append("finished_at=?")
        vals.append(now)
    vals.append(run_id)
    with _connect() as conn:
        conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", vals)


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["summary"] = json.loads(d.pop("summary_json") or "{}")
    return d


def list_runs(limit: int = 10) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["summary"] = json.loads(d.pop("summary_json") or "{}")
        res.append(d)
    return res


def add_output(
    *,
    run_id: str | None,
    group_id: str | None,
    kind: str,
    title: str,
    prompt: str,
    score: float | None,
    review: str,
    public_url: str,
    folder: str,
    lora_saved: bool = False,
    meta: dict[str, Any] | None = None,
) -> str:
    oid = "out_" + uuid.uuid4().hex[:12]
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO outputs(
                id, run_id, group_id, kind, title, prompt, score, review,
                public_url, folder, lora_saved, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                oid,
                run_id,
                group_id,
                kind,
                title,
                prompt,
                score,
                review,
                public_url,
                folder,
                1 if lora_saved else 0,
                json.dumps(meta or {}, ensure_ascii=False),
                now,
            ),
        )
    return oid


def list_outputs(limit: int = 20, kind: str | None = None) -> list[dict[str, Any]]:
    with _connect() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM outputs WHERE kind=? ORDER BY created_at DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM outputs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
        res.append(d)
    return res


def count_lora_dataset() -> int:
    if not LORA_DIR.exists():
        return 0
    return sum(1 for p in LORA_DIR.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
