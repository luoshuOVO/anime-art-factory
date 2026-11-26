from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import clients, comic_renderer, db, web_ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("art-factory")

app = FastAPI(title="Anime Art & Comic Factory", version="1.5.0")

clients.LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
clients.LOCAL_REF_INBOX_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(clients.LOCAL_OUTPUT_DIR), check_dir=False), name="outputs")

_EXEC_LOCK = threading.Lock()
_ACTIVE_RUN_ID: str | None = None

# 多比例黄金画幅池（全部为 32/16 倍数，单图约 0.59~0.72MP，兼顾细节与省 CU）
ASPECT_POOL: list[dict[str, Any]] = [
    {"ratio": "16:9", "group": "landscape", "w": 1024, "h": 576, "hint": "横屏宽幅16:9，适合中远景环境人像与电影宽景"},
    {"ratio": "3:2",  "group": "landscape", "w": 1024, "h": 672, "hint": "横幅插画3:2，人物与场景故事感舒展平衡"},
    {"ratio": "4:3",  "group": "landscape", "w": 960,  "h": 704, "hint": "经典横幅4:3，人物清晰突出且兼顾背景氛围"},
    {"ratio": "1:1",  "group": "square",    "w": 832,  "h": 832, "hint": "方形插画1:1，人物主体居中紧凑饱满"},
    {"ratio": "3:4",  "group": "portrait",  "w": 704,  "h": 960, "hint": "经典竖版3:4，适合人物大半身或全身精致立绘"},
    {"ratio": "2:3",  "group": "portrait",  "w": 704,  "h": 1024, "hint": "竖版海报2:3，最适合完整展示人物全身穿搭与神态"},
    {"ratio": "9:16", "group": "portrait",  "w": 576,  "h": 1024, "hint": "竖屏长幅9:16，适合修长全身角色立绘与竖屏壁纸"},
]

ASPECT_PRESETS = {
    "landscape": (1024, 576),
    "portrait": (576, 1024),
    "square": (832, 832),
}


def _pick_aspect_plan(aspect: str, count: int) -> list[dict[str, Any]]:
    """为本批任务生成洗牌打散的画幅比例方案，避免连出单一比例。"""
    if aspect == "random":
        candidates = list(ASPECT_POOL)
    elif aspect in {"landscape", "portrait", "square"}:
        candidates = [p for p in ASPECT_POOL if p["group"] == aspect]
    else:
        candidates = list(ASPECT_POOL)

    plan: list[dict[str, Any]] = []
    bag: list[dict[str, Any]] = []
    while len(plan) < count:
        if not bag:
            bag = list(candidates)
            random.shuffle(bag)
            if plan and len(bag) > 1 and bag[0]["ratio"] == plan[-1]["ratio"]:
                bag.append(bag.pop(0))
        plan.append(bag.pop(0))
    return plan


@app.on_event("startup")
def _startup() -> None:
    global _ACTIVE_RUN_ID
    db.init_db()
    for run in db.list_runs(limit=5):
        if run["status"] in {"running", "postprocessing"}:
            if _EXEC_LOCK.acquire(blocking=False):
                _ACTIVE_RUN_ID = run["id"]
                t = threading.Thread(target=_monitor_run_thread, args=(run["id"],), daemon=True)
                t.start()
            break


def _safe_slug(text: str, max_len: int = 24) -> str:
    clean = re.sub(r"[^\w一-鿿-]+", "_", (text or "art")).strip("_")
    return (clean[:max_len] or "art")


def _calc_runtime_minutes(job_count: int, workflow_key: str = "") -> int:
    # Cold start + auto-retry buffer + per-image safety budget, capped at 120 min
    if workflow_key == "krea2-moss-dual-t2i":
        return min(120, max(35, 18 + job_count * 5))
    return min(120, max(25, 12 + job_count * 3))


def _resolve_active_workflow(settings: dict[str, Any], override: str | None = None) -> dict[str, Any]:
    if override and override.strip():
        preset = db.resolve_workflow_preset(override)
        if not preset:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的工作流：{override}（可选：moss / dual）",
            )
        return preset
    return db.describe_workflow(
        str(settings["workflow_key"]),
        str(settings["workflow_version"]),
        str(settings["model_id"]),
    )


def _save_lora_sample(title: str, prompt: str, img_bytes: bytes, score: float | None, meta: dict[str, Any]) -> bool:
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        stem = f"{ts}_{uuid.uuid4().hex[:6]}_{_safe_slug(title, 16)}"
        (db.LORA_DIR / f"{stem}.png").write_bytes(img_bytes)
        (db.LORA_DIR / f"{stem}.txt").write_text(prompt.strip() + "\n", encoding="utf-8")
        (db.LORA_DIR / f"{stem}.json").write_text(
            json.dumps({"title": title, "score": score, "prompt": prompt, "meta": meta}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        log.warning("保存 LoRA 训练集素材失败: %s", exc)
        return False


def _launch_batch_for_items(
    items: list[dict[str, Any]],
    trigger_kind: str,
    workflow_override: str | None = None,
) -> dict[str, Any]:
    global _ACTIVE_RUN_ID
    if not items:
        return {"started": False, "message": "当前没有待画任务"}
    if not _EXEC_LOCK.acquire(blocking=False):
        return {
            "started": False,
            "queued": True,
            "active_run_id": _ACTIVE_RUN_ID,
            "message": "当前已有一批任务正在 Colab 显卡上执行，本批已安全留在待画队列，稍后自动或手动发车即可。",
        }
    try:
        settings = db.get_settings()
        # Infer item-level workflow hint if caller did not explicitly pass override
        inferred_wf = workflow_override
        if not inferred_wf:
            item_wfs = {
                str((it.get("meta") or {}).get("workflow") or "").strip()
                for it in items
                if (it.get("meta") or {}).get("workflow")
            }
            if len(item_wfs) == 1:
                inferred_wf = next(iter(item_wfs))
        wf = _resolve_active_workflow(settings, inferred_wf)
        gpu_acc = str(settings.get("gpu_accelerator") or "L4")
        est_mins = _calc_runtime_minutes(len(items), wf["workflow_key"])
        run_id = db.create_run(trigger_kind, len(items), gpu_acc, est_mins)
        _ACTIVE_RUN_ID = run_id

        try:
            batch_id, job_ids = clients.studio_submit_batch(
                jobs_spec=items,
                model_id=wf["model_id"],
                workflow_key=wf["workflow_key"],
                workflow_version=wf["workflow_version"],
                gpu_accelerator=gpu_acc,
                max_runtime_minutes=est_mins,
                dual_params=settings.get("dual_params") if isinstance(settings.get("dual_params"), dict) else None,
            )
            job_map = {item["id"]: jid for item, jid in zip(items, job_ids)}
            db.mark_items_submitted([i["id"] for i in items], run_id, job_map)
            db.update_run(
                run_id,
                batch_id=batch_id,
                status="running",
                summary={"workflow": f"{wf['workflow_key']} v{wf['workflow_version']}", "workflow_label": wf["label"]},
            )
        except Exception as exc:
            db.update_run(run_id, status="failed", error=str(exc), finished=True)
            _ACTIVE_RUN_ID = None
            _EXEC_LOCK.release()
            raise

        t = threading.Thread(target=_monitor_run_thread, args=(run_id,), daemon=True)
        t.start()
        return {
            "started": True,
            "run_id": run_id,
            "batch_id": batch_id,
            "job_count": len(items),
            "gpu": gpu_acc,
            "workflow": f"{wf['workflow_key']} v{wf['workflow_version']}",
            "workflow_label": wf["label"],
            "max_runtime_minutes": est_mins,
            "message": f"已用【{wf['label']}】开机提交 {len(items)} 张任务至 Colab {gpu_acc}（开启自动抢卡 + 画完自动关机，最长保护时长 {est_mins} 分钟），画完后自动质检/拼漫画并保存至{clients.storage_mode_label()}。",
        }
    except Exception:
        if _EXEC_LOCK.locked() and _ACTIVE_RUN_ID is None:
            _EXEC_LOCK.release()
        raise


def _monitor_run_thread(run_id: str) -> None:
    global _ACTIVE_RUN_ID
    try:
        items = db.list_items_by_run(run_id)
        if not items:
            db.update_run(run_id, status="completed", summary={"note": "empty"}, finished=True)
            return

        settings = db.get_settings()
        threshold = float(settings.get("quality_threshold", 7.5))
        deadline = time.time() + max(1800, (len(items) * 240) + 1200)
        terminal = {"completed", "failed", "canceled", "cancelled", "timed_out"}

        job_states: dict[str, dict[str, Any]] = {}
        while time.time() < deadline:
            pending_count = 0
            for item in items:
                jid = item.get("studio_job_id")
                if not jid:
                    continue
                if jid in job_states and job_states[jid].get("state") in terminal:
                    continue
                try:
                    jdata = clients.studio_get_job(jid)
                    job_states[jid] = jdata
                    if jdata.get("state") not in terminal:
                        pending_count += 1
                except Exception as exc:
                    log.warning("轮询 job %s 异常: %s", jid, exc)
                    pending_count += 1
            if pending_count == 0:
                break
            time.sleep(15)

        db.update_run(run_id, status="postprocessing")

        total_units = 0.0
        last_ccu = None
        saved_urls: list[dict[str, Any]] = []
        failed_count = 0
        dropped_count = 0

        # Group comic items by group_id; process single art items directly
        comic_groups: dict[str, list[tuple[dict[str, Any], bytes | None]]] = defaultdict(list)

        for item in items:
            jid = item.get("studio_job_id") or ""
            jdata = job_states.get(jid) or {}
            st = jdata.get("state")
            if jdata.get("actual_units") is not None:
                try:
                    total_units += float(jdata["actual_units"])
                except Exception:
                    pass
            if jdata.get("ccu_after") is not None:
                try:
                    last_ccu = float(jdata["ccu_after"])
                except Exception:
                    pass

            asset_ids = jdata.get("output_asset_ids") or []
            if st != "completed" or not asset_ids:
                failed_count += 1
                db.update_item_status(item["id"], "failed", f"studio_state={st}")
                if item["kind"] == "comic":
                    comic_groups[item["group_id"]].append((item, None))
                continue

            try:
                img_bytes = clients.studio_download_asset(asset_ids[0])
            except Exception as exc:
                failed_count += 1
                db.update_item_status(item["id"], "failed", f"download_err={exc}")
                if item["kind"] == "comic":
                    comic_groups[item["group_id"]].append((item, None))
                continue

            db.update_item_status(item["id"], "completed")

            if item["kind"] == "comic":
                comic_groups[item["group_id"]].append((item, img_bytes))
            else:
                score, review = clients.score_anime_image(img_bytes)
                # 巡航按质检阈值(默认7.5)筛选；手动许愿也会自动拦掉硬伤废图(<=5.5，如切头/无人物/崩手)
                should_upload = (score >= threshold) or (item["kind"] == "wish" and score >= 6.0)
                if should_upload:
                    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                    fname = f"{item['kind']}_{ts}_{_safe_slug(item['title'], 14)}_{uuid.uuid4().hex[:5]}.png"
                    url = clients.save_output_image(img_bytes, fname, folder="ai-art-inbox", mime="image/png")
                    lora_saved = False
                    if score >= threshold:
                        lora_saved = _save_lora_sample(item["title"], item["prompt"], img_bytes, score, item.get("meta") or {})
                    db.add_output(
                        run_id=run_id,
                        group_id=item["group_id"],
                        kind=item["kind"],
                        title=item["title"],
                        prompt=item["prompt"],
                        score=score,
                        review=review,
                        public_url=url,
                        folder="ai-art-inbox",
                        lora_saved=lora_saved,
                        meta={**(item.get("meta") or {}), "filename": fname},
                    )
                    saved_urls.append({"kind": item["kind"], "title": item["title"], "score": score, "review": review, "url": url})
                else:
                    dropped_count += 1

        # Assemble completed comics
        for gid, entries in comic_groups.items():
            entries.sort(key=lambda pair: pair[0].get("panel_index", 0))
            valid_imgs = [b for _, b in entries if b]
            if not valid_imgs:
                continue
            first_meta = entries[0][0].get("meta") or {}
            script = first_meta.get("script") or {}
            panels_data = script.get("panels") or [e[0].get("meta", {}).get("panel") or {} for e in entries]
            panel_imgs = [b if b else b"" for _, b in entries]
            strip_bytes = comic_renderer.render_comic_strip(
                title=script.get("title") or entries[0][0]["title"],
                subtitle=script.get("subtitle") or "",
                takeaway=script.get("takeaway") or "",
                style=first_meta.get("style") or "explainer",
                source_hint=first_meta.get("source_hint") or "",
                panels=panels_data,
                panel_images=panel_imgs,
            )
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            comic_title = script.get("title") or entries[0][0]["title"]
            fname = f"comic_{ts}_{_safe_slug(comic_title, 16)}_{uuid.uuid4().hex[:5]}.png"
            (db.COMICS_DIR / fname).write_bytes(strip_bytes)
            url = clients.save_output_image(strip_bytes, fname, folder="comics", mime="image/png")
            db.add_output(
                run_id=run_id,
                group_id=gid,
                kind="comic",
                title=comic_title,
                prompt=json.dumps(script, ensure_ascii=False)[:2000],
                score=9.0,
                review=f"{len(valid_imgs)}/{len(entries)}格拼装完成",
                public_url=url,
                folder="comics",
                lora_saved=False,
                meta={"style": first_meta.get("style"), "source_hint": first_meta.get("source_hint")},
            )
            saved_urls.append({"kind": "comic", "title": comic_title, "url": url})

        summary = {
            "total_jobs": len(items),
            "saved_count": len(saved_urls),
            "dropped_low_score": dropped_count,
            "failed_jobs": failed_count,
            "outputs": saved_urls,
        }
        final_status = "completed" if saved_urls or failed_count < len(items) else "failed"
        db.update_run(
            run_id,
            status=final_status,
            actual_units=round(total_units, 4) if total_units else None,
            ccu_after=last_ccu,
            summary=summary,
            finished=True,
        )
        log.info("Run %s finished: %s", run_id, summary)
        job_ids = [it["studio_job_id"] for it in items if it.get("studio_job_id")]
        if job_ids:
            threading.Thread(
                target=_settle_run_billing,
                args=(run_id, job_ids),
                daemon=True,
            ).start()
    except Exception as exc:
        log.exception("Monitor run %s crashed", run_id)
        db.update_run(run_id, status="failed", error=str(exc), finished=True)
    finally:
        _ACTIVE_RUN_ID = None
        try:
            _EXEC_LOCK.release()
        except RuntimeError:
            pass


def _settle_run_billing(run_id: str, job_ids: list[str]) -> None:
    """Re-query Studio after runtime teardown (~60s) so async-backfilled actual_units & ccu_after are exact."""
    for delay in (35, 35):
        time.sleep(delay)
        total_units = 0.0
        last_ccu = None
        all_settled = True
        for jid in job_ids:
            try:
                jd = clients.studio_get_job(jid)
                if jd.get("actual_units") is not None:
                    total_units += float(jd["actual_units"])
                else:
                    all_settled = False
                if jd.get("ccu_after") is not None:
                    last_ccu = float(jd["ccu_after"])
            except Exception:
                all_settled = False
        if total_units > 0 or last_ccu is not None:
            db.update_run(
                run_id,
                actual_units=round(total_units, 4) if total_units else None,
                ccu_after=last_ccu,
            )
            log.info("Settled billing for %s: actual_units=%.4f ccu_after=%s", run_id, total_units, last_ccu)
        if all_settled:
            break



def _build_live_stage(runs: list[dict[str, Any]], live_gpu: dict[str, Any]) -> dict[str, Any]:
    active_run = next((r for r in runs if r["status"] in {"submitting", "running", "postprocessing"}), None)
    if not active_run:
        gpu_cnt = live_gpu.get("active_gpu_count", 0)
        return {
            "phase": "idle",
            "stage_text": (
                f"空闲待命中（当前仍有 {gpu_cnt} 台 Colab 显卡未释放，建议核查）"
                if gpu_cnt > 0
                else "空闲待命中（无存活 Colab 显卡，0 消耗）"
            ),
            "progress": None,
        }
    rid = active_run["id"]
    if active_run["status"] == "submitting":
        return {"phase": "submitting", "stage_text": "正在打包提示词并向 Studio 下单…", "progress": f"0/{active_run['job_count']}"}
    if active_run["status"] == "postprocessing":
        return {
            "phase": "postprocessing",
            "stage_text": "全部画图已完成，正在 AI 质检 / 拼装中文漫画并保存成品…",
            "progress": f"{active_run['job_count']}/{active_run['job_count']}",
        }

    items = db.list_items_by_run(rid)
    total = len(items) or active_run["job_count"]
    done = 0
    failed = 0
    running_gpu = None
    retry_note = None
    for it in items:
        jid = it.get("studio_job_id")
        if not jid:
            continue
        try:
            jd = clients.studio_get_job(jid)
            st = jd.get("state")
            if st == "completed":
                done += 1
            elif st in {"failed", "canceled", "cancelled", "timed_out"}:
                failed += 1
            elif st == "running":
                running_gpu = jd.get("gpu_reported") or active_run.get("gpu_accelerator") or "L4"
            ar = jd.get("allocation_retry") or {}
            if ar.get("active") and not running_gpu:
                retry_note = f"正在自动排队抢 {active_run.get('gpu_accelerator','L4')} 显卡（第 {ar.get('attempt', 1)}/{ar.get('max_retries', 25)} 次尝试）"
        except Exception:
            pass

    if retry_note:
        stage_text = retry_note
        phase = "retrying_gpu"
    elif running_gpu and done == 0:
        stage_text = f"已抢到 {running_gpu}，正在开机加载模型并画第 1/{total} 张"
        phase = "drawing"
    elif running_gpu:
        stage_text = f"{running_gpu} 正在连续作画中（已完成 {done}/{total} 张）"
        phase = "drawing"
    else:
        stage_text = f"排队等待分配 {active_run.get('gpu_accelerator','L4')} 显卡（已完成 {done}/{total} 张）"
        phase = "queued"

    return {
        "phase": phase,
        "run_id": rid,
        "stage_text": stage_text,
        "progress": f"{done}/{total}",
        "completed": done,
        "failed": failed,
        "total": total,
    }


# ---------- Request Models ----------

class WishRequest(BaseModel):
    idea: str = Field(..., min_length=1, max_length=1000)
    count: int = Field(default=6, ge=1, le=20)
    aspect: Literal["random", "landscape", "portrait", "square"] = "random"
    style_hint: str = ""
    ref_image_url: str = ""
    workflow: str = ""
    mode: Literal["now", "later"] = "later"


class ComicRequest(BaseModel):
    url: str = ""
    text: str = ""
    style: Literal["explainer", "four_panel", "story"] = "explainer"
    panels: int = Field(default=4, ge=3, le=6)
    persona: str = ""
    custom_hint: str = ""
    workflow: str = ""
    mode: Literal["now", "later"] = "now"


class CruiseRequest(BaseModel):
    count: int | None = Field(default=None, ge=4, le=40)
    workflow: str = ""
    force: bool = False


class ControlRequest(BaseModel):
    cmd: Literal[
        "status",
        "flush",
        "clear_queue",
        "pause_cruise",
        "resume_cruise",
        "set_daily_count",
        "set_workflow",
        "list_workflows",
        "set_dual_params",
        "recent",
    ] = "status"
    value: Any = None
    limit: int = Field(default=10, ge=1, le=50)


# ---------- API Endpoints ----------

@app.get("/", response_class=HTMLResponse)
def index_page() -> HTMLResponse:
    return HTMLResponse(web_ui.INDEX_HTML)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "active_run_id": _ACTIVE_RUN_ID,
        "lora_samples": db.count_lora_dataset(),
        "storage_mode": clients.storage_mode_label(),
    }


@app.post("/api/wish")
def api_wish(req: WishRequest) -> dict[str, Any]:
    wf_chosen = _resolve_active_workflow(db.get_settings(), req.workflow) if req.workflow.strip() else None
    ref_bytes = None
    if req.ref_image_url.strip():
        ref_bytes = clients.fetch_image_bytes(req.ref_image_url.strip())

    aspect_plan = _pick_aspect_plan(req.aspect, req.count)
    expanded = clients.expand_wish_prompts(
        idea=req.idea.strip(),
        count=req.count,
        ref_image_bytes=ref_bytes,
        style_hint=req.style_hint.strip(),
        aspect_plan=aspect_plan,
    )
    gid = "wish_" + uuid.uuid4().hex[:10]
    queue_payload = []
    for idx, item in enumerate(expanded):
        slot = aspect_plan[idx % len(aspect_plan)]
        queue_payload.append(
            {
                "group_id": gid,
                "kind": "wish",
                "title": item["title"],
                "prompt": item["prompt"],
                "width": slot["w"],
                "height": slot["h"],
                "panel_index": idx,
                "meta": {
                    "idea": req.idea,
                    "aspect": req.aspect,
                    "ratio": slot["ratio"],
                    "target_size": f"{slot['w']}x{slot['h']}",
                    "ref_image_url": req.ref_image_url,
                    **({"workflow": wf_chosen["preset"]} if wf_chosen else {}),
                },
            }
        )
    ids = db.enqueue_items(queue_payload)

    launch_info = None
    if req.mode == "now":
        pending = [it for it in db.list_queue("pending") if it["id"] in set(ids)]
        launch_info = _launch_batch_for_items(
            pending,
            trigger_kind="wish_now",
            workflow_override=wf_chosen["preset"] if wf_chosen else None,
        )

    return {
        "ok": True,
        "group_id": gid,
        "mode": req.mode,
        "count": len(expanded),
        "prompts_preview": [
            {
                "title": x["title"],
                "ratio": aspect_plan[i % len(aspect_plan)]["ratio"],
                "size": f"{aspect_plan[i % len(aspect_plan)]['w']}x{aspect_plan[i % len(aspect_plan)]['h']}",
                "prompt": x["prompt"][:90] + "...",
            }
            for i, x in enumerate(expanded)
        ],
        "launch": launch_info,
        "message": (
            launch_info["message"]
            if launch_info
            else f"已将「{req.idea[:20]}」发散成 {len(expanded)} 张二次元方案并攒入待画队列（省 CU 晚班车统一开机，或随时说一声立刻发车）。"
        ),
    }


@app.post("/api/comic")
def api_comic(req: ComicRequest) -> dict[str, Any]:
    if not req.url.strip() and not req.text.strip():
        raise HTTPException(status_code=400, detail="请至少提供文章链接(url)或正文内容(text)")

    source_hint = ""
    raw_content = req.text.strip()
    if req.url.strip():
        source_hint = req.url.strip()
        crawled = clients.crawl_url_markdown(source_hint)
        raw_content = (raw_content + "\n\n" + crawled).strip() if raw_content else crawled

    settings = db.get_settings()
    wf_chosen = _resolve_active_workflow(settings, req.workflow) if req.workflow.strip() else None
    persona = req.persona.strip() or str(settings.get("default_persona"))
    panels_n = 4 if req.style == "four_panel" else req.panels

    script = clients.generate_comic_script(
        content=raw_content,
        style=req.style,
        panels=panels_n,
        persona=persona,
        custom_hint=req.custom_hint.strip(),
    )

    gid = "comic_" + uuid.uuid4().hex[:10]
    queue_payload = []
    for idx, p in enumerate(script["panels"]):
        queue_payload.append(
            {
                "group_id": gid,
                "kind": "comic",
                "title": script.get("title") or "科普图解漫画",
                "prompt": p["image_prompt"],
                "width": 1024,
                "height": 576,
                "panel_index": idx,
                "meta": {
                    "style": req.style,
                    "source_hint": source_hint,
                    "script": script if idx == 0 else None,
                    "panel": p,
                    **({"workflow": wf_chosen["preset"]} if wf_chosen else {}),
                },
            }
        )
    ids = db.enqueue_items(queue_payload)

    launch_info = None
    if req.mode == "now":
        pending = [it for it in db.list_queue("pending") if it["id"] in set(ids)]
        launch_info = _launch_batch_for_items(
            pending,
            trigger_kind="comic_now",
            workflow_override=wf_chosen["preset"] if wf_chosen else None,
        )

    return {
        "ok": True,
        "group_id": gid,
        "mode": req.mode,
        "comic_title": script.get("title"),
        "subtitle": script.get("subtitle"),
        "panels_count": len(script["panels"]),
        "storyboard_preview": [
            {"panel": i + 1, "title": p.get("panel_title"), "caption": p.get("caption")}
            for i, p in enumerate(script["panels"])
        ],
        "launch": launch_info,
        "message": (
            launch_info["message"]
            if launch_info
            else f"已把文章拆解成 {len(script['panels'])} 格《{script.get('title')}》科普漫画脚本并存入待画队列，随时可发车或等晚班车一起画。"
        ),
    }


@app.post("/api/cruise/run")
def api_cruise_run(req: CruiseRequest) -> dict[str, Any]:
    settings = db.get_settings()
    pending_before = db.list_queue("pending")

    if not settings.get("cruise_enabled", True) and not req.force:
        if pending_before:
            launch = _launch_batch_for_items(pending_before, trigger_kind="queue_evening_flush")
            return {"ok": True, "cruise_skipped": True, "flushed_pending": len(pending_before), "launch": launch}
        return {"ok": True, "cruise_skipped": True, "message": "自动巡航已暂停且队列为空，今日不烧卡。"}

    target = int(req.count or settings.get("daily_count") or 16)
    need = max(0, target - len(pending_before))

    generated_count = 0
    if need > 0:
        # Strict human-in-the-loop rule: only remix reference images placed into ImgBed ai-draw-inbox or local /data/ref-inbox
        draw_refs = clients.list_reference_images("ai-draw-inbox", count=200)
        used = set(settings.get("used_ref_images") or [])
        fresh = [w for w in draw_refs if w["name"] not in used]

        if not fresh and not pending_before:
            inbox_hint = "图床 ai-draw-inbox" if clients.is_imgbed_enabled() else "本地 ./data/ref-inbox 目录"
            return {
                "ok": True,
                "cruise_skipped": True,
                "reason": "ref_inbox_empty",
                "message": f"今日绘图原料池（{inbox_hint}）里没有新放进来的参考图，待画队列也为空，今晚不开机不烧 CU。",
            }

        per_ref = 4
        ref_needed = max(1, (need + per_ref - 1) // per_ref)
        chosen = fresh[:ref_needed]

        new_items: list[dict[str, Any]] = []
        gid = "cruise_" + datetime.now().strftime("%Y%m%d") + "_" + uuid.uuid4().hex[:5]
        for ref in chosen:
            if len(new_items) >= need:
                break
            try:
                raw_img = clients.fetch_image_bytes(ref["internal_url"])
                target_w, target_h, orient_hint = clients.detect_target_size(raw_img)
                remixed = clients.remix_wallpaper_prompts(
                    raw_img,
                    variants=min(per_ref, need - len(new_items)),
                    orientation_hint=orient_hint,
                )
                used.add(ref["name"])
                for r_item in remixed:
                    new_items.append(
                        {
                            "group_id": gid,
                            "kind": "cruise",
                            "title": r_item["title"],
                            "prompt": r_item["prompt"],
                            "width": target_w,
                            "height": target_h,
                            "meta": {
                                "ref_wallpaper": ref["name"],
                                "target_size": f"{target_w}x{target_h}",
                            },
                        }
                    )
            except Exception as exc:
                log.warning("魔改参考壁纸 %s 失败: %s", ref["name"], exc)

        if new_items:
            db.enqueue_items(new_items)
            generated_count = len(new_items)

    all_pending = db.list_queue("pending")
    if not all_pending:
        return {"ok": False, "message": "未生成新巡航提示词且待画队列为空"}

    wf_override = req.workflow.strip() or None
    launch = _launch_batch_for_items(all_pending, trigger_kind="daily_cruise", workflow_override=wf_override)
    if (launch.get("started") or launch.get("ok")) and generated_count > 0:
        db.set_setting("used_ref_images", list(used)[-180:])
    return {
        "ok": True,
        "cruise_generated": generated_count,
        "previous_queued": len(pending_before),
        "total_batch": len(all_pending),
        "launch": launch,
    }


@app.post("/api/control")
def api_control(req: ControlRequest) -> dict[str, Any]:
    cmd = req.cmd
    if cmd == "pause_cruise":
        db.set_setting("cruise_enabled", False)
        return {"ok": True, "message": "已暂停每日自动巡航（不影响你随时手动许愿或文章转漫画）。"}
    if cmd == "resume_cruise":
        db.set_setting("cruise_enabled", True)
        return {"ok": True, "message": "已恢复每日自动巡航。"}
    if cmd == "set_daily_count":
        try:
            n = max(4, min(50, int(req.value)))
        except Exception:
            raise HTTPException(status_code=400, detail="请提供 4~50 之间的整数张数")
        db.set_setting("daily_count", n)
        return {"ok": True, "daily_count": n, "message": f"每日自动巡航张数已设为 {n} 张。"}
    if cmd == "set_workflow":
        preset = db.resolve_workflow_preset(str(req.value or ""))
        if not preset:
            raise HTTPException(
                status_code=400,
                detail="未知工作流，请传 moss（单 MOSS 二次元画师）或 dual（Krea-2 + MOSS 双画师）",
            )
        db.set_setting("workflow_key", preset["workflow_key"])
        db.set_setting("workflow_version", preset["workflow_version"])
        db.set_setting("model_id", preset["model_id"])
        return {
            "ok": True,
            "workflow_preset": preset["preset"],
            "workflow": f"{preset['workflow_key']} v{preset['workflow_version']}",
            "workflow_label": preset["label"],
            "message": f"默认自动画图工作流已切换为：{preset['label']}（{preset['workflow_key']} v{preset['workflow_version']}）。",
        }
    if cmd == "list_workflows":
        settings = db.get_settings()
        cur = db.describe_workflow(
            str(settings["workflow_key"]),
            str(settings["workflow_version"]),
            str(settings["model_id"]),
        )
        return {
            "ok": True,
            "current": cur,
            "available_workflows": list(db.WORKFLOW_PRESETS.values()),
            "dual_params": settings.get("dual_params") or dict(db.DEFAULT_DUAL_PARAMS),
        }
    if cmd == "set_dual_params":
        if not isinstance(req.value, dict):
            raise HTTPException(status_code=400, detail='请传入双画师参数字典，如 {"moss_denoise": 0.4, "lora_krea_tjfilm": 0.6}')
        settings = db.get_settings()
        merged = dict(db.DEFAULT_DUAL_PARAMS)
        if isinstance(settings.get("dual_params"), dict):
            merged.update(settings["dual_params"])
        allowed = set(db.DEFAULT_DUAL_PARAMS.keys())
        updated_keys = []
        for k, v in req.value.items():
            if k in allowed:
                merged[k] = int(v) if k in ("krea_steps", "moss_steps") else float(v)
                updated_keys.append(k)
        if not updated_keys:
            raise HTTPException(status_code=400, detail=f"未包含有效参数，支持：{sorted(allowed)}")
        db.set_setting("dual_params", merged)
        return {"ok": True, "updated": updated_keys, "dual_params": merged, "message": f"已更新双画师参数：{', '.join(updated_keys)}"}
    if cmd == "clear_queue":
        removed = db.clear_pending_queue()
        return {"ok": True, "removed": removed, "message": f"已清空待画队列中的 {removed} 项任务。"}
    if cmd == "flush":
        pending = db.list_queue("pending")
        if not pending:
            return {"ok": True, "started": False, "message": "待画队列当前为空，没有需要发车的任务。"}
        launch = _launch_batch_for_items(pending, trigger_kind="manual_flush")
        return {"ok": True, "launch": launch, "message": launch["message"]}
    if cmd == "recent":
        outputs = db.list_outputs(limit=req.limit)
        return {
            "ok": True,
            "count": len(outputs),
            "lora_dataset_count": db.count_lora_dataset(),
            "outputs": [
                {
                    "kind": o["kind"],
                    "title": o["title"],
                    "score": o["score"],
                    "review": o["review"],
                    "url": o["public_url"],
                    "folder": o["folder"],
                    "created_at": datetime.fromtimestamp(o["created_at"]).strftime("%Y-%m-%d %H:%M"),
                }
                for o in outputs
            ],
        }

    # default: status
    settings = db.get_settings()
    pending = db.list_queue("pending")
    runs = db.list_runs(limit=5)
    outputs = db.list_outputs(limit=6)
    live_gpu = clients.studio_live_overview()
    live_stage = _build_live_stage(runs, live_gpu)
    try:
        draw_refs = clients.imgbed_list_folder("ai-draw-inbox", count=200)
        used = set(settings.get("used_ref_images") or [])
        inbox_new = sum(1 for w in draw_refs if w["name"] not in used)
    except Exception:
        inbox_new = None
    return {
        "ok": True,
        "live_stage": live_stage,
        "active_gpu_count": live_gpu["active_gpu_count"],
        "ccu_balance": live_gpu["ccu_balance"] or (runs[0]["ccu_after"] if runs and runs[0].get("ccu_after") else None),
        "ai_draw_inbox_new_count": inbox_new,
        "cruise_enabled": settings["cruise_enabled"],
        "daily_count": settings["daily_count"],
        "gpu": settings["gpu_accelerator"],
        "workflow": f"{settings['workflow_key']} v{settings['workflow_version']}",
        "workflow_preset": db.describe_workflow(str(settings["workflow_key"]), str(settings["workflow_version"]), str(settings["model_id"]))["preset"],
        "workflow_label": db.describe_workflow(str(settings["workflow_key"]), str(settings["workflow_version"]), str(settings["model_id"]))["label"],
        "available_workflows": [
            {"preset": p["preset"], "label": p["label"], "workflow": f"{p['workflow_key']} v{p['workflow_version']}"}
            for p in db.WORKFLOW_PRESETS.values()
        ],
        "active_run_id": _ACTIVE_RUN_ID,
        "pending_queue_count": len(pending),
        "pending_preview": [{"kind": p["kind"], "title": p["title"]} for p in pending[:10]],
        "lora_dataset_count": db.count_lora_dataset(),
        "recent_runs": [
            {
                "run_id": r["id"],
                "trigger": r["trigger_kind"],
                "status": r["status"],
                "jobs": r["job_count"],
                "actual_units": r["actual_units"],
                "ccu_after": r["ccu_after"],
                "saved": (r.get("summary") or {}).get("saved_count"),
                "error": r["error"],
            }
            for r in runs
        ],
        "recent_outputs": [
            {"kind": o["kind"], "title": o["title"], "score": o["score"], "url": o["public_url"]}
            for o in outputs
        ],
    }


@app.post("/api/comic/preview-render")
def api_comic_preview_render() -> dict[str, Any]:
    """Zero-CU self-test: verify Chinese Noto CJK font & vertical comic layout rendering."""
    from PIL import Image, ImageDraw
    import io

    sample_imgs = []
    colors = [(219, 234, 254), (252, 231, 243), (220, 252, 231), (254, 249, 195)]
    for i, col in enumerate(colors):
        im = Image.new("RGB", (1024, 576), col)
        d = ImageDraw.Draw(im)
        d.ellipse((380, 140, 644, 404), fill=(255, 255, 255), outline=(30, 41, 59), width=6)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        sample_imgs.append(buf.getvalue())

    out = comic_renderer.render_comic_strip(
        title="一图看懂：为什么批量开一次卡最省 CU？",
        subtitle="告别单张反复冷启动，把 2500 CU 花在刀刃上",
        takeaway="把灵感攒成一批一次开机画完，省掉重复热身开销，还能自动质检攒 LoRA 素材！",
        style="explainer",
        source_hint="系统排版自检",
        panels=[
            {
                "panel_title": "痛点：每画一张就重开机",
                "dialogues": [
                    {"speaker": "助手", "text": "学姐，我每次想画一张就开一次卡，怎么 CU 掉这么快？"},
                    {"speaker": "学姐", "text": "因为每次开机热身加拉模型都要耗好几分钟，画 1 张太亏啦！"},
                ],
                "caption": "单张冷启动成本远高于实际画图耗时",
            },
            {
                "panel_title": "解法：攒一波批量连画",
                "dialogues": [
                    {"speaker": "学姐", "text": "把灵感先丢进待画池，晚上开机一次连画 16 张，画完秒关机！"},
                ],
                "caption": "同实例串行复用 L4，单张只需约 25 秒",
            },
        ],
        panel_images=sample_imgs[:2],
    )
    out_path = db.COMICS_DIR / "selftest_preview.png"
    out_path.write_bytes(out)
    return {"ok": True, "bytes": len(out), "saved": str(out_path)}


_BADGE_CACHE_LOCK = threading.Lock()
_BADGE_CACHE_DATA: dict[str, Any] | None = None
_BADGE_CACHE_TS: float = 0.0


@app.get("/api/live-badge")
def api_live_badge() -> dict[str, Any]:
    """Lightweight cached read-only status endpoint for CloudCLI / ImgBed corner progress widget."""
    global _BADGE_CACHE_DATA, _BADGE_CACHE_TS
    now = time.time()
    with _BADGE_CACHE_LOCK:
        if _BADGE_CACHE_DATA is not None:
            is_busy = bool(_BADGE_CACHE_DATA.get("active")) or int(_BADGE_CACHE_DATA.get("active_gpu_count") or 0) > 0
            ttl = 5.0 if is_busy else 12.0
            if now - _BADGE_CACHE_TS < ttl:
                return _BADGE_CACHE_DATA

    settings = db.get_settings()
    pending = db.list_queue("pending")
    runs = db.list_runs(limit=3)
    try:
        live_gpu = clients.studio_live_overview()
    except Exception:
        live_gpu = {"active_gpu_count": 0, "ccu_balance": None}
    live_stage = _build_live_stage(runs, live_gpu)
    wf_desc = db.describe_workflow(
        str(settings["workflow_key"]),
        str(settings["workflow_version"]),
        str(settings["model_id"]),
    )
    latest = runs[0] if runs else None
    latest_run = None
    if latest:
        summary = latest.get("summary") or {}
        latest_run = {
            "run_id": latest["id"],
            "trigger": latest["trigger_kind"],
            "status": latest["status"],
            "jobs": latest["job_count"],
            "saved": summary.get("saved_count"),
            "failed": summary.get("failed_jobs"),
            "actual_units": latest["actual_units"],
            "ccu_after": latest["ccu_after"],
            "error": latest["error"],
            "created_at": latest["created_at"],
            "finished_at": latest["finished_at"],
        }

    ccu = live_gpu.get("ccu_balance")
    if ccu is None and latest and latest.get("ccu_after") is not None:
        ccu = latest.get("ccu_after")

    payload = {
        "ok": True,
        "active": live_stage.get("phase") != "idle",
        "phase": live_stage.get("phase") or "idle",
        "stage_text": live_stage.get("stage_text") or "",
        "progress": live_stage.get("progress"),
        "completed": int(live_stage.get("completed") or 0),
        "failed": int(live_stage.get("failed") or 0),
        "total": int(live_stage.get("total") or 0),
        "active_gpu_count": int(live_gpu.get("active_gpu_count") or 0),
        "ccu_balance": round(float(ccu), 2) if ccu is not None else None,
        "pending_queue_count": len(pending),
        "workflow_label": wf_desc["label"],
        "latest_run": latest_run,
        "server_time": int(time.time()),
    }
    with _BADGE_CACHE_LOCK:
        _BADGE_CACHE_DATA = payload
        _BADGE_CACHE_TS = time.time()
    return payload
