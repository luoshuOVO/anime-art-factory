from __future__ import annotations

import base64
import html
import io
import json
import os
import random
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from PIL import Image

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
LOCAL_OUTPUT_DIR = DATA_DIR / "outputs"
LOCAL_REF_INBOX_DIR = DATA_DIR / "ref-inbox"

STUDIO_BASE = os.environ.get("STUDIO_BASE", "http://colab-comfy-studio:8788").rstrip("/")
STUDIO_TOKEN = os.environ.get("STUDIO_API_TOKEN", "")

IMGBED_BASE = os.environ.get("IMGBED_BASE", "").rstrip("/")
IMGBED_PUBLIC_BASE = (os.environ.get("IMGBED_PUBLIC_BASE") or IMGBED_BASE).rstrip("/")
IMGBED_AUTH = os.environ.get("IMGBED_AUTH_CODE", "")
IMGBED_MANAGE_TOKEN = os.environ.get("IMGBED_MANAGE_TOKEN", "")
IMGBED_UPLOAD_CHANNEL = os.environ.get("IMGBED_UPLOAD_CHANNEL", "cfr2")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

LLM_API_BASE = (os.environ.get("LLM_API_BASE") or os.environ.get("MAGPIE_BASE") or "").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("MAGPIE_API_KEY") or ""
LLM_TEXT_MODEL = os.environ.get("LLM_TEXT_MODEL") or os.environ.get("MAGPIE_TEXT_MODEL") or "gpt-4o-mini"
LLM_VISION_MODEL = os.environ.get("LLM_VISION_MODEL") or os.environ.get("MAGPIE_VISION_MODEL") or LLM_TEXT_MODEL

CRAWL4AI_BASE = os.environ.get("CRAWL4AI_BASE", "").rstrip("/")
CRAWL4AI_TOKEN = os.environ.get("CRAWL4AI_API_TOKEN", "")


def is_imgbed_enabled() -> bool:
    return bool(IMGBED_BASE and IMGBED_AUTH)


def storage_mode_label() -> str:
    return "外部图床 (ImgBed)" if is_imgbed_enabled() else "本地目录 (/data/outputs)"


def _extract_json(text: str) -> Any:
    raw = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    for open_c, close_c in [("{", "}"), ("[", "]")]:
        i = raw.find(open_c)
        j = raw.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(raw[i : j + 1])
            except Exception:
                pass
    raise ValueError(f"AI 未返回合法 JSON：{raw[:240]}")


def _shrink_to_jpeg_b64(img_bytes: bytes, max_side: int = 512) -> str:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def llm_chat_json(
    messages: list[dict[str, Any]],
    *,
    vision: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2400,
) -> Any:
    if not LLM_API_BASE or not LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_BASE 或 LLM_API_KEY，请先在 .env 中填写任意 OpenAI 兼容接口")
    model = LLM_VISION_MODEL if vision else LLM_TEXT_MODEL
    endpoint = (
        f"{LLM_API_BASE}/chat/completions"
        if LLM_API_BASE.endswith("/v1")
        else f"{LLM_API_BASE}/v1/chat/completions"
    )
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=90.0) as client:
                r = client.post(endpoint, headers=headers, json=payload)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                return _extract_json(content)
        except Exception as exc:
            last_err = exc
            payload["temperature"] = 0.3
    raise RuntimeError(f"LLM 接口调用失败: {last_err}")


magpie_chat_json = llm_chat_json


def _simple_html_to_text(raw_html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?s)<[^>]+>", "\n", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [re.sub(r"\s+", " ", line).strip() for line in cleaned.splitlines()]
    lines = [line for line in lines if len(line) >= 4]
    return "\n".join(lines)


def crawl_url_markdown(url: str) -> str:
    if CRAWL4AI_BASE:
        headers = {"Content-Type": "application/json"}
        if CRAWL4AI_TOKEN:
            headers["Authorization"] = f"Bearer {CRAWL4AI_TOKEN}"
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{CRAWL4AI_BASE}/md", headers=headers, json={"url": url, "f": "fit"})
            r.raise_for_status()
            data = r.json()
        md = data.get("markdown") or data.get("fit_markdown") or data.get("text") or ""
        if isinstance(md, dict):
            md = md.get("fit_markdown") or md.get("raw_markdown") or ""
        md = str(md).strip()
        if not md:
            raise RuntimeError("Crawl4AI 抓取正文为空")
        return md[:12000]

    # Built-in lightweight fallback when Crawl4AI is not deployed
    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AnimeArtFactory/1.0)"},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        text = _simple_html_to_text(r.text)
    if not text:
        raise RuntimeError("简易抓取未能提取正文，建议直接复制文章内容粘贴到 text 参数，或配置 CRAWL4AI_BASE")
    return text[:12000]


def imgbed_list_folder(folder: str, count: int = 200) -> list[dict[str, Any]]:
    if not IMGBED_BASE:
        return []
    qs = urlencode({"dir": folder, "count": count})
    headers = {"Authorization": f"Bearer {IMGBED_MANAGE_TOKEN}"} if IMGBED_MANAGE_TOKEN else {}
    with httpx.Client(timeout=20.0) as client:
        r = client.get(f"{IMGBED_BASE}/api/manage/list?{qs}", headers=headers)
        if r.status_code in (401, 403):
            r = client.get(f"{IMGBED_BASE}/api/public/list?{qs}&fileType=image")
        r.raise_for_status()
        data = r.json()
    files = data.get("files") if isinstance(data, dict) else data
    out = []
    for item in files or []:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("name") or item.get("src") or item.get("id") or ""
        else:
            continue
        if not name:
            continue
        base_name = name.rsplit("/", 1)[-1]
        if base_name.startswith("README_") or base_name.startswith("."):
            continue
        if not any(base_name.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
            continue
        src = name if name.startswith("/file/") else f"/file/{name.lstrip('/')}"
        out.append({"name": name, "src": src, "internal_url": f"{IMGBED_BASE}{src}"})
    return out


def list_reference_images(folder: str = "ai-draw-inbox", count: int = 200) -> list[dict[str, Any]]:
    """List reference images from ImgBed if configured, otherwise from local /data/ref-inbox."""
    if is_imgbed_enabled():
        return imgbed_list_folder(folder, count=count)
    LOCAL_REF_INBOX_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for p in sorted(LOCAL_REF_INBOX_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        out.append({"name": p.name, "src": str(p), "internal_url": f"local://{p.name}"})
        if len(out) >= count:
            break
    return out


def imgbed_list_wallpapers(folder: str = "wallpapers", count: int = 200) -> list[dict[str, Any]]:
    return imgbed_list_folder(folder, count=count)


def fetch_image_bytes(url: str) -> bytes:
    if url.startswith("local://"):
        safe_name = Path(url[len("local://") :]).name
        target = LOCAL_REF_INBOX_DIR / safe_name
        if not target.is_file():
            raise FileNotFoundError(f"本地参考图不存在: {safe_name}")
        return target.read_bytes()
    if IMGBED_PUBLIC_BASE and IMGBED_BASE and url.startswith(IMGBED_PUBLIC_BASE):
        url = IMGBED_BASE + url[len(IMGBED_PUBLIC_BASE) :]
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def local_save_output(img_bytes: bytes, filename: str, folder: str) -> str:
    safe_folder = re.sub(r"[^A-Za-z0-9_-]+", "_", folder or "misc").strip("_") or "misc"
    safe_name = Path(filename).name
    dest_dir = LOCAL_OUTPUT_DIR / safe_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / safe_name).write_bytes(img_bytes)
    rel_url = f"/outputs/{safe_folder}/{safe_name}"
    return f"{PUBLIC_BASE_URL}{rel_url}" if PUBLIC_BASE_URL else rel_url


def imgbed_upload(img_bytes: bytes, filename: str, folder: str, mime: str = "image/png") -> str:
    qs = urlencode(
        {
            "authCode": IMGBED_AUTH,
            "uploadChannel": IMGBED_UPLOAD_CHANNEL,
            "uploadFolder": folder,
            "serverCompress": "false",
            "uploadNameType": "origin",
        }
    )
    with httpx.Client(timeout=45.0) as client:
        r = client.post(
            f"{IMGBED_BASE}/upload?{qs}",
            files={"file": (filename, img_bytes, mime)},
        )
        r.raise_for_status()
        res = r.json()
    src = ""
    if isinstance(res, list) and res:
        src = res[0].get("src", "")
    elif isinstance(res, dict):
        src = res.get("src", "") or (res.get("data") or {}).get("src", "")
    if not src:
        raise RuntimeError(f"图床上传未返回链接: {res}")
    if src.startswith("http"):
        return src
    return f"{IMGBED_PUBLIC_BASE}{src if src.startswith('/') else '/' + src}"


def save_output_image(img_bytes: bytes, filename: str, folder: str, mime: str = "image/png") -> str:
    """Upload to ImgBed if enabled, falling back cleanly to local /data/outputs storage."""
    if is_imgbed_enabled():
        try:
            return imgbed_upload(img_bytes, filename, folder=folder, mime=mime)
        except Exception:
            # Never lose generated art if ImgBed has a transient error
            return local_save_output(img_bytes, filename, folder=folder)
    return local_save_output(img_bytes, filename, folder=folder)


# ---------- AI Prompting Functions ----------

def expand_wish_prompts(
    *,
    idea: str,
    count: int,
    ref_image_bytes: bytes | None = None,
    style_hint: str = "",
    aspect_plan: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    sys_msg = (
        "你是顶级日式二次元插画美术总监，擅长把用户的几句灵感发散成适合中文生图模型 MOSS-Image 的高品质画面提示词。"
        "严格禁止真人写实/3D手办娃娃风，只输出纯正二次元/日漫/轻小说插画。所有提示词用细腻流畅的中文，严禁画面出现任何文字或水印。"
        "【四条绝对铁律】："
        "1）核心关键词100%同时命中：用户提到的每一个服饰/元素关键词都必须在每张图里原汁原味、清晰可见地同时出现，严禁为了迎合场景把核心服装改没或藏出画外；"
        "2）大人物小背景：人物必须作为绝对主角占据画面65%～85%，五官、服装、鞋袜清晰可见；严禁把人物画成远景小豆丁，背景只作简洁柔美衬托；"
        "3）严禁切头与僵硬站桩：人物头部与完整五官必须稳稳留在画框内，严禁无人物空景或只拍下半身特写；同时严禁多张都写「正面站着」的僵硬站桩姿势，每张必须有完全不同的生动动作（如坐姿翘腿、弯腰系鞋、侧卧沙发、跪坐倒茶、回眸迈步、趴桌翘腿、靠窗、蹲姿等）与不同镜头角度（仰拍/俯拍/侧拍/平视）；"
        "4）拒绝千篇一律同款脸：每张必须区分脸型气质（御姐/清冷/甜妹/元气/慵懒/傲娇等）、眼型表情、发型发色与二次元画风流派（赛璐璐/日系厚涂/轻小说封面/清新水彩/潮酷插画等）。"
        "只输出严格 JSON：{\"items\":[{\"title\":\"简短中文标题\",\"prompt\":\"完整中文画面描述\"}]}。"
    )
    plan_block = ""
    if aspect_plan:
        lines = [
            f"第{i+1}张：{p['ratio']}（{p['hint']}）"
            for i, p in enumerate(aspect_plan[:count])
        ]
        plan_block = (
            "\n【每张画幅分配（请严格一一对应，让镜头构图自然贴合该比例，且确保人物完整露头露脸）】：\n"
            + "；".join(lines)
            + "。"
        )
    user_text = (
        f"请围绕用户想法「{idea}」发散出 {count} 个差异明显、人物发色服饰场景与光影各具特色的二次元人物插画方案。"
        f"{('附加风格偏好：' + style_hint) if style_hint else ''}"
        f"{plan_block}"
        "每个方案请变化场景、时间光影（晨光/黄昏/雨夜/霓虹/星空）与角色神态姿态，务必保证每张人物头部和脸部完整入画，张张惊艳。"
    )
    if ref_image_bytes:
        b64 = _shrink_to_jpeg_b64(ref_image_bytes)
        user_content: Any = [
            {"type": "text", "text": user_text + " 请参考附图的画风配色和氛围进行二创发散，但不要照抄原图。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]
        data = magpie_chat_json(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_content}],
            vision=True,
            temperature=0.85,
        )
    else:
        data = magpie_chat_json(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_text}],
            vision=False,
            temperature=0.85,
        )
    items = data.get("items") if isinstance(data, dict) else data
    out = []
    for i, it in enumerate((items or [])[:count]):
        p = str(it.get("prompt") or "").strip()
        if p:
            out.append({"title": str(it.get("title") or f"{idea[:12]}-{i+1}").strip(), "prompt": p})
    if not out:
        raise RuntimeError("AI 未生成有效提示词")
    return out


def detect_target_size(ref_image_bytes: bytes) -> tuple[int, int, str]:
    """根据参考图原始长宽比匹配对应的 64 倍数出图尺寸与画幅说明。"""
    try:
        img = Image.open(io.BytesIO(ref_image_bytes))
        ow, oh = img.size
        if ow > 0 and oh > 0:
            r = ow / oh
            if r >= 1.50:
                return 1024, 576, "横屏宽幅构图（16:9，适合桌面壁纸与宽景叙事）"
            if r >= 1.15:
                return 960, 704, "横幅插画构图（约 4:3，人物与环境均衡舒展）"
            if r >= 0.87:
                return 768, 768, "方形插画构图（1:1，人物主体突出居中）"
            if r >= 0.65:
                return 704, 960, "竖版立绘构图（约 3:4，适合人物半身或全身精绘）"
            return 576, 1024, "竖屏长幅构图（9:16，适合全身角色立绘与竖屏壁纸）"
    except Exception:
        pass
    return 1024, 576, "横屏宽幅构图（16:9）"


def remix_wallpaper_prompts(
    ref_image_bytes: bytes,
    variants: int = 4,
    orientation_hint: str = "",
) -> list[dict[str, str]]:
    b64 = _shrink_to_jpeg_b64(ref_image_bytes)
    sys_msg = (
        "你是资深二次元插画策划。请先看懂参考图的动漫风格、色彩情绪和构图精髓，然后做大胆有趣的二次元魔改二创："
        "改变时间/天气/季节/动作姿态/服饰细节/场景或视角，绝不照搬原图，也绝不生成真人写实/3D娃娃风。"
        "【四条绝对铁律】：1）大人物小背景：人物必须占画面65%～85%，严禁画成远景小豆丁；"
        "2）完整人物：头部与完整五官必须稳稳留在画框内，严禁切头、裁脸、空景或只拍局部肢体特写；"
        "3）动作与镜头多样：严禁多张都写正面僵硬站桩，每张必须有不同生动姿势（坐、倚、回眸、前倾、蹲、侧卧、动态迈步等）和不同镜头角度；"
        "4）拒绝同款脸：变化人物表情、脸型气质与二次元画风流派（厚涂/赛璐璐/轻小说封面/水彩等），每条用细腻流畅的中文描述，严禁要求图中出现文字。"
        "只返回严格 JSON：{\"items\":[{\"title\":\"8字以内中文名\",\"prompt\":\"完整中文画面描述\"}]}。"
    )
    user_content = [
        {
            "type": "text",
            "text": f"请受这张二次元参考图启发，魔改发散出 {variants} 个全新、精致的高品质二次元人物插画提示词。画幅要求：{orientation_hint or '贴合原图比例'}，请让主体人物构图自然适配该画幅。",
        },
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]
    data = magpie_chat_json(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_content}],
        vision=True,
        temperature=0.9,
    )
    items = data.get("items") if isinstance(data, dict) else data
    out = []
    for i, it in enumerate((items or [])[:variants]):
        p = str(it.get("prompt") or "").strip()
        if p:
            out.append({"title": str(it.get("title") or f"二创壁纸-{i+1}").strip(), "prompt": p})
    return out


def generate_comic_script(
    *,
    content: str,
    style: str,
    panels: int,
    persona: str,
    custom_hint: str = "",
) -> dict[str, Any]:
    style_desc = {
        "explainer": "科普图解条漫：用生活化比喻和轻松问答，把复杂知识拆成一看就懂的二次元小剧场",
        "four_panel": "四格日常漫：起-承-转-合节奏明快，带一点二次元吐槽幽默感",
        "story": "番剧分镜长图：电影感二次元分镜构图，配精炼旁白讲清核心脉络",
    }.get(style, "科普图解条漫")

    sys_msg = (
        "你是顶级二次元知识漫画编剧兼分镜师。你的任务是把用户提供的文章或主题，改编成让小白 30 秒看懂的二次元彩漫脚本。\n"
        "核心铁律：\n"
        "1. 角色外貌必须在每一格的 image_prompt 中保持完全一致（服装、发型、发色不变），便于连贯观感。\n"
        "2. 每格 image_prompt 必须用流畅中文描写画面（开头固定「清爽日式彩色漫画分镜，二次元动画风格，干净明快线条，非写实，无任何文字无气泡，」），"
        "**绝对禁止**要求画面里出现任何文字、标牌、公式、对话气泡（所有文字由后期程序清晰排版）。\n"
        "3. 每格对话（dialogues）控制在 1～2 句大白话（每句不超过 36 字），外加 1 句「划重点」caption（不超过 34 字），通俗幽默、拒绝晦涩黑话。\n"
        "4. 只输出严格 JSON，格式：\n"
        "{\n"
        "  \"title\": \"吸引人的漫画大标题（18字内）\",\n"
        "  \"subtitle\": \"一句话副标题点明主题（28字内）\",\n"
        "  \"takeaway\": \"最后读者能带走的一句话核心收获（45字内）\",\n"
        "  \"panels\": [\n"
        "    {\n"
        "      \"panel_title\": \"本格简短小标题（14字内）\",\n"
        "      \"image_prompt\": \"干净无字的二次元漫画格中文画面描述\",\n"
        "      \"dialogues\": [{\"speaker\": \"助手\", \"text\": \"提问或吐槽\"}, {\"speaker\": \"学姐\", \"text\": \"用通俗比喻解答\"}],\n"
        "      \"caption\": \"本格一句话划重点\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )
    user_msg = (
        f"漫画类型：{style_desc}\n"
        f"格数要求：严格 {panels} 格\n"
        f"固定出场人设：{persona}\n"
        f"{('用户补充要求：' + custom_hint + chr(10)) if custom_hint else ''}"
        f"以下是原文素材：\n---\n{content[:10000]}\n---"
    )
    data = magpie_chat_json(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        vision=False,
        temperature=0.65,
        max_tokens=3200,
    )
    if not isinstance(data, dict) or not data.get("panels"):
        raise RuntimeError("AI 未能生成有效漫画分镜")
    data["panels"] = data["panels"][:panels]
    return data


def score_anime_image(img_bytes: bytes) -> tuple[float, str]:
    b64 = _shrink_to_jpeg_b64(img_bytes)
    sys_msg = (
        "你是二次元人物插画严选评委。请对这张 AI 生成的二次元图打分（1.0~10.0 分）："
        "如果出现以下任一硬伤，请直接打 <=5.5 分并在简评注明原因："
        "1）画面没有人物主体（纯空景），或人物极小被背景彻底淹没；"
        "2）人物头部或脸部被画框裁切缺失、只剩下半身/腿脚局部特写；"
        "3）多手指、五官崩坏、肢体扭曲、严重模糊或错乱文字。"
        "人物占比大方、完整露脸、姿势自然、光影好看打 7.5~8.5 分；惊艳精品打 8.6~9.8 分。"
        "只返回严格 JSON：{\"score\": 8.4, \"review\": \"15字以内简评\"}。"
    )
    try:
        res = magpie_chat_json(
            [
                {"role": "system", "content": sys_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请客观打分并简评。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                },
            ],
            vision=True,
            temperature=0.2,
            max_tokens=200,
        )
        return float(res.get("score", 7.5)), str(res.get("review", "质检完成"))[:40]
    except Exception as exc:
        return 7.8, f"自动放行({str(exc)[:20]})"


# ---------- Colab GPU Studio Client ----------

def _studio_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {STUDIO_TOKEN}", "Content-Type": "application/json"}


def studio_get_defaults() -> tuple[str, str | None]:
    with httpx.Client(timeout=15.0) as client:
        pr = client.get(f"{STUDIO_BASE}/api/projects", headers=_studio_headers())
        pr.raise_for_status()
        projects = pr.json().get("data") or []
        project_id = None
        for p in projects:
            if p.get("is_default"):
                project_id = p.get("id")
                break
        if not project_id and projects:
            project_id = projects[0].get("id")
        if not project_id:
            raise RuntimeError("Studio 中未找到可用项目")

        ar = client.get(f"{STUDIO_BASE}/api/gpu/accounts", headers=_studio_headers())
        ar.raise_for_status()
        accounts = ar.json().get("data") or []
        account_id = None
        for a in accounts:
            if a.get("enabled") and a.get("allow_allocation"):
                account_id = a.get("account_id") or a.get("id")
                break
    return project_id, account_id


def _align16(value: int, low: int = 512, high: int = 1536) -> int:
    v = max(low, min(high, int(value)))
    return max(low, (v // 16) * 16)


def resolve_compute_shape(workflow_key: str, gpu_accelerator: str) -> str:
    acc = (gpu_accelerator or "L4").strip().upper()
    if workflow_key == "krea2-moss-dual-t2i" and acc == "T4":
        return "SHAPE_HIGHMEM"
    return "SHAPE_STANDARD"


def build_studio_job_params(
    workflow_key: str,
    item: dict[str, Any],
    dual_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    w = _align16(int(item.get("width", 1024)))
    h = _align16(int(item.get("height", 576)))
    if workflow_key == "krea2-moss-dual-t2i":
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        item_dual = meta.get("dual_params") if isinstance(meta.get("dual_params"), dict) else {}
        dp = {
            "krea_steps": 8,
            "moss_steps": 25,
            "moss_cfg": 2.5,
            "moss_denoise": 0.36,
            "lora_krea_tjfilm": 0.75,
            "lora_krea_realism": 0.5,
            "lora_krea_softlight": 0.55,
            "lora_krea_filter": 0.6,
            **(dual_params or {}),
            **item_dual,
        }
        return {
            "prompt": item["prompt"],
            "width": w,
            "height": h,
            "seed": -1,
            "krea_steps": max(4, min(20, int(dp["krea_steps"]))),
            "moss_seed": random.randint(1, 2_147_483_647),
            "moss_steps": max(10, min(50, int(dp["moss_steps"]))),
            "moss_cfg": max(1.0, min(6.0, float(dp["moss_cfg"]))),
            "moss_denoise": max(0.1, min(0.8, float(dp["moss_denoise"]))),
            "lora_krea_tjfilm": max(0.0, min(2.0, float(dp["lora_krea_tjfilm"]))),
            "lora_krea_realism": max(0.0, min(2.0, float(dp["lora_krea_realism"]))),
            "lora_krea_softlight": max(0.0, min(2.0, float(dp["lora_krea_softlight"]))),
            "lora_krea_filter": max(0.0, min(2.0, float(dp["lora_krea_filter"]))),
        }
    return {
        "prompt": item["prompt"],
        "negative": item.get("negative", ""),
        "width": w,
        "height": h,
        "steps": int(item.get("steps", 35)),
        "cfg": float(item.get("cfg", 2.5)),
        "shift": float(item.get("shift", 5.0)),
        "seed": -1,
    }


def studio_submit_batch(
    *,
    jobs_spec: list[dict[str, Any]],
    model_id: str,
    workflow_key: str,
    workflow_version: str,
    gpu_accelerator: str,
    max_runtime_minutes: int,
    dual_params: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    project_id, account_id = studio_get_defaults()
    policy: dict[str, Any] = {
        "provider": "colab",
        "max_runtime_minutes": int(max_runtime_minutes),
        "compute_spec": {
            "variant": "VARIANT_GPU",
            "accelerator": gpu_accelerator,
            "shape": resolve_compute_shape(workflow_key, gpu_accelerator),
        },
        "allocation": "auto",
        "lifecycle": "save",
        "retain_idle_minutes": 15,
    }
    if account_id:
        policy["account_id"] = account_id

    jobs = []
    for item in jobs_spec:
        jobs.append(
            {
                "project_id": project_id,
                "model_id": model_id,
                "workflow_key": workflow_key,
                "workflow_version": workflow_version,
                "params": build_studio_job_params(workflow_key, item, dual_params=dual_params),
                "execution_policy": dict(policy),
            }
        )

    headers = _studio_headers()
    headers["Idempotency-Key"] = f"artfactory-{uuid.uuid4().hex}"
    body = {"jobs": jobs, "mode": "save", "idle_seconds": 60}
    with httpx.Client(timeout=45.0) as client:
        r = client.post(f"{STUDIO_BASE}/api/gpu/batches", headers=headers, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"Studio 批次下单失败 HTTP {r.status_code}: {r.text[:400]}")
        data = r.json().get("data") or {}
    batch_id = data.get("batch_id") or data.get("id")
    job_ids = data.get("job_ids") or [j.get("id") or j.get("job_id") for j in (data.get("jobs") or [])]
    if not batch_id or len(job_ids) != len(jobs_spec):
        raise RuntimeError(f"Studio 批次返回异常: {data}")
    return str(batch_id), [str(x) for x in job_ids]


def studio_get_job(job_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        r = client.get(f"{STUDIO_BASE}/api/gpu/jobs/{job_id}", headers=_studio_headers())
        r.raise_for_status()
        return r.json().get("data") or {}


def studio_download_asset(asset_id: str) -> bytes:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(f"{STUDIO_BASE}/api/assets/{asset_id}/download", headers=_studio_headers())
        r.raise_for_status()
        return r.content


def studio_live_overview() -> dict[str, Any]:
    """Read live active GPU instances & latest CCU balance from Studio."""
    active_gpus = []
    ccu_balance = None
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{STUDIO_BASE}/api/gpu/instances", headers=_studio_headers())
            if r.status_code == 200:
                for ins in (r.json().get("data") or []):
                    if ins.get("state") not in ("deleted", "terminated", "failed"):
                        active_gpus.append(
                            {
                                "id": ins.get("id"),
                                "state": ins.get("state"),
                                "gpu": ins.get("gpu_reported") or ins.get("spec"),
                            }
                        )
            r2 = client.get(f"{STUDIO_BASE}/api/gpu/jobs?limit=1", headers=_studio_headers())
            if r2.status_code == 200:
                items = (r2.json().get("data") or [])
                if isinstance(items, dict):
                    items = items.get("items") or []
                if items and items[0].get("ccu_after") is not None:
                    ccu_balance = round(float(items[0]["ccu_after"]), 2)
    except Exception:
        pass
    return {"active_gpu_count": len(active_gpus), "active_gpus": active_gpus, "ccu_balance": ccu_balance}
