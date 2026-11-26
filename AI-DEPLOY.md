# AI 自动部署指南（交给你的 AI 助手阅读）

> **给正在阅读本文件的 AI 助手（Claude Code / CloudCLI / Codex 等）**：  
> 请按本指南协助用户完成部署。本仓库采用「**核心必装 + 可选模块按需启用**」设计——**动手前必须先用简短大白话问清楚用户想选哪个方案**，不要默认把全部可选模块硬塞进去。

---

## 第 1 步：先让用户选部署方案（问清再动手）

请用简洁大白话向用户提供 3 个方案选择：

1. **方案 A（推荐·极简聊天生图版）**：
   - 安装：`docker-compose.yml`（Colab GPU Studio + Art Factory）+ `cloudcli-integration/`（聊天生图指令 + 右上角实时进度悬浮标）。
   - 特点：**不需要装图床、不需要装 n8n**，成品自动存到 `./data/outputs/` 并在内置中文画廊页（`http://127.0.0.1:28096/`）直接看图。
2. **方案 B（带独立图床版）**：
   - 在方案 A 基础上，额外安装 `optional/imgbed-suite/`（CloudFlare-ImgBed 图床 + 文件夹中文显示层 + 一键「复制去生图」按钮 + Studio 收藏无损原图同步）。
3. **方案 C（全自动满配版）**：
   - 在方案 B 基础上，额外导入 `optional/n8n-workflows/`（每晚 22:00 定时巡航魔改出图 + 每日二次元自动搜图入待选箱，需要用户机器已有或新装 n8n）。

同时确认 3 个用户自备条件是否齐全：
- 本机 Docker & Docker Compose 环境
- 一个兼容 OpenAI 接口的 AI Key（需支持文本 + 视觉看图，如 OpenAI / DeepSeek / 硅基流动 / OneAPI / NewAPI 等）
- 一个 Google 账号（含 Colab GPU 额度）+ Google Cloud OAuth 客户端（用于授权 Colab 与 Google Drive）

---

## 第 2 步：部署核心栈（方案 A / B / C 必做）

1. **检查本机端口是否被占用**：
   - 默认端口：`29091`（Colab GPU Studio）、`28096`（Art Factory）。若冲突，直接在 `.env` 修改 `STUDIO_PORT` / `FACTORY_PORT`，并保持仅监听 `127.0.0.1`（对外访问通过用户现有的 Nginx / Caddy / Cloudflare Tunnel 反代）。
2. **生成 `.env` 并自动填入随机密钥**：
   - `cp .env.example .env && chmod 600 .env`
   - 自动用 `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` 生成并填入 `ENCRYPTION_KEY`、`SESSION_SECRET`、`STUDIO_API_TOKEN`（如用户未指定 `STUDIO_PASSWORD` 也一并生成并告知用户）。
   - 向用户索取或读取其已有的 `LLM_API_BASE`、`LLM_API_KEY`、`LLM_TEXT_MODEL`、`LLM_VISION_MODEL` 以及 Google OAuth 信息写入 `.env`。
3. **创建数据目录并启动**：
   ```bash
   mkdir -p data studio-data studio-secrets
   docker compose up -d --build
   ```
4. **健康检查验证**：
   - `curl -fsS http://127.0.0.1:${FACTORY_PORT:-28096}/health`（确认 `ok: true`）
   - `curl -fsS http://127.0.0.1:${STUDIO_PORT:-29091}/api/health`
5. **引导用户完成一次性 Google Colab 授权**：
   - 告知用户访问 Colab GPU Studio 网页，登录并完成 Google Drive + Colab 授权，发布内置的 `moss-image-sft-t2i`（单画师，快且省 CU）或 `krea2-moss-dual-t2i`（双画师 + 4 滤镜 LoRA）工作流。

---

## 第 3 步：接入 CloudCLI 聊天生图 + 右上角悬浮标（方案 A / B / C 必做）

1. **聊天生图规则**：
   - 将 `cloudcli-integration/CLAUDE-SNIPPET.md` 中虚线以下的规则追加到用户工作区的 `CLAUDE.md`（如有自定义端口，同步替换 `28096`）。
   - 务必保留「提交异步生图后立刻回复结束、严禁后台死盯轮询霸占输入框」的规则。
2. **右上角实时进度悬浮标**：
   - 复制 `cloudcli-integration/art-progress-badge.js` 到用户的 Nginx snippets 目录（如 `/etc/nginx/snippets/art-progress-badge.js`），按用户实际访问域名修改顶部的 `GALLERY_URL`（没装图床时填 Art Factory 的域名或地址，装了图床则填图床 `/dashboard`）与 `STUDIO_URL`。
   - 参考 `cloudcli-integration/nginx-cloudcli-badge.conf`，把 4 段 `location` 融入用户反代 CloudCLI 的 Nginx 配置（确保 `nginx -t` 通过后再 `reload`）。
   - 如果用户不用 Nginx（如用 Caddy / Traefik），请按同等逻辑做 `/_custom/art-progress.js` 静态服务、`/_custom/art-live-badge` 只读代理与 HTML `</body>` 前脚本注入。

---

## 第 4 步：按用户选择决定是否部署可选模块

### 可选模块 A：`optional/imgbed-suite/`（独立图床 + 网页增强 + 收藏同步）
- 仅在用户选择方案 B / C 时执行：
  1. 用 `docker-compose.imgbed.yml` 和 `.env.imgbed.example` 启动 CloudFlare-ImgBed，并接入 `anime-art-factory_art-net` 网络。
  2. 在根 `.env` 中填好 `IMGBED_BASE`、`IMGBED_PUBLIC_BASE`、`IMGBED_AUTH_CODE`、`IMGBED_MANAGE_TOKEN`，重启 `art-factory` 即可自动从本地存储切换为图床存储。
  3. 按 `nginx-imgbed-enhance.conf` 给图床网页注入中文文件夹显示层（`imgbed-folder-cn.js`）、一键「复制去生图」按钮（`imgbed-copy-draw-btn.js`）、图库快捷导航（`imgbed-gallery-btn.js`）以及同款右上角进度标。
  4. 如用户希望在 Studio 手动「点收藏」后自动把无损原画同步到图床，可给 `comfy-imgbed-sync.py` 配一个 30~60 秒的 systemd timer 或 cron。

### 可选模块 B：`optional/studio-enhancements/comfy-fixed-prompt.js`
- 如用户经常直接打开 Colab Studio 手动生图，可将该脚本注入 Studio 网页（提供常用二次元画风前后缀一键开关 + AI 润色提示词按钮），并把脚本里的模型名和 API 路径改成用户的 LLM 代理地址。

### 可选模块 C：`optional/n8n-workflows/`（定时巡航 + 每日自动搜图）
- 仅在用户选择方案 C 且有 n8n 时导入：
  - `01-daily-anime-art-cruise.json`：每晚 22:00 扫参考图原料池（`ai-draw-inbox` 或本地 `./data/ref-inbox/`）按原图比例自动魔改批画，无新图自动跳过不烧 CU（若不用 n8n，直接用宿主机 crontab `0 22 * * * curl -fsS -X POST http://127.0.0.1:28096/api/cruise/run -H 'Content-Type: application/json' -d '{}'` 效果完全一样）。
  - `02-anime-auto-image-hunter.json`：每日自动搜集 40 路动漫高赞图并用 AI 视觉打分 ≥8 分送入图床待选箱；导入后需把工作流中的 `YOUR-IMGBED-DOMAIN`、`YOUR-LLM-API-BASE`、`YOUR_VISION_MODEL`、图床认证和 Telegram 凭据替换为用户自己的配置后再启用。

---

## 安全红线（AI 执行必守）

- 严禁把填好真实密钥的 `.env`、`data/`、`studio-data/` 提交回 Git。
- 所有容器服务默认仅监听 `127.0.0.1`，不直接裸露无鉴权端口到公网。
- 完成后向用户用大白话汇报：哪些模块已装、访问入口是什么、以及下一步在 Studio 网页里绑定 Google 账号的指引。
