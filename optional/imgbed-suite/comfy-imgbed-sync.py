#!/usr/bin/env python3
"""可选脚本：将 Colab GPU Studio 中手动「点收藏」的无损原图自动同步到 CloudFlare-ImgBed。

用法（全部通过环境变量传入，无任何硬编码密钥）：
  STUDIO_BASE=http://127.0.0.1:29091 \
  STUDIO_API_TOKEN=你的Token \
  IMGBED_BASE=http://127.0.0.1:29093 \
  IMGBED_AUTH_CODE=你的上传码 \
  python3 comfy-imgbed-sync.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

STUDIO_BASE = os.environ.get("STUDIO_BASE", "http://127.0.0.1:29091").rstrip("/")
STUDIO_TOKEN = os.environ.get("STUDIO_API_TOKEN", "")
IMGBED_BASE = os.environ.get("IMGBED_BASE", "").rstrip("/")
IMGBED_AUTH = os.environ.get("IMGBED_AUTH_CODE", "")
IMGBED_CHANNEL = os.environ.get("IMGBED_UPLOAD_CHANNEL", "cfr2")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "ai-art")
STATE_FILE = Path(os.environ.get("SYNC_STATE_FILE", "./comfy-imgbed-synced.json"))


def studio_get_json(path: str) -> dict:
    req = urllib.request.Request(
        f"{STUDIO_BASE}{path}",
        headers={"Authorization": f"Bearer {STUDIO_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def studio_download(asset_id: str) -> bytes:
    req = urllib.request.Request(
        f"{STUDIO_BASE}/api/assets/{asset_id}/download",
        headers={"Authorization": f"Bearer {STUDIO_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def upload_to_imgbed(img_bytes: bytes, filename: str) -> str:
    boundary = f"----SyncBoundary{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + img_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    qs = urllib.parse.urlencode(
        {
            "authCode": IMGBED_AUTH,
            "uploadChannel": IMGBED_CHANNEL,
            "uploadFolder": UPLOAD_FOLDER,
            "serverCompress": "false",
            "uploadNameType": "origin",
        }
    )
    req = urllib.request.Request(
        f"{IMGBED_BASE}/upload?{qs}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main() -> int:
    if not (STUDIO_TOKEN and IMGBED_BASE and IMGBED_AUTH):
        print("请先设置 STUDIO_API_TOKEN、IMGBED_BASE 和 IMGBED_AUTH_CODE 环境变量", file=sys.stderr)
        return 1

    synced: set[str] = set()
    if STATE_FILE.exists():
        try:
            synced = set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except Exception:
            synced = set()

    assets = studio_get_json("/api/assets?favorited=true&limit=100").get("data") or []
    if isinstance(assets, dict):
        assets = assets.get("items") or []

    uploaded = 0
    for a in assets:
        aid = str(a.get("id") or "")
        if not aid or aid in synced:
            continue
        raw = studio_download(aid)
        fname = a.get("filename") or f"studio_{aid}.png"
        upload_to_imgbed(raw, fname)
        synced.add(aid)
        uploaded += 1
        print(f"已同步收藏原画: {fname}")

    STATE_FILE.write_text(json.dumps(sorted(synced), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"同步完成，本次新增 {uploaded} 张。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
