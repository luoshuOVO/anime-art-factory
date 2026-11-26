# 可选增强模块清单（按需自选）

核心生图 + CloudCLI 聊天 + 右上角悬浮标**不依赖以下任何模块**。如需扩展体验，可按需挑选启用（交给 AI 部署时直接告诉它要哪几个即可）：

## 模块 A：`imgbed-suite/`（独立图床 + 网页体验增强 + 收藏同步）
- `docker-compose.imgbed.yml` + `.env.imgbed.example`：一键部署 CloudFlare-ImgBed 图床。
- `imgbed-folder-cn.js`：无侵入给图床文件夹加上中文名字（底层路径保持英文不变）。
- `imgbed-copy-draw-btn.js`：图床图库里新增一键「复制去生图」防重按钮，把喜欢的参考图直接抄送进 `ai-draw-inbox`。
- `imgbed-gallery-btn.js`：图床首页「进入图库」快捷按钮 + 图库顶部返回键 + 大图点空白处关闭。
- `nginx-imgbed-enhance.conf`：将以上 3 个 JS + 同款生图进度悬浮标无侵入注入图床的 Nginx 配置模板。
- `comfy-imgbed-sync.py`：把在 Colab Studio 里手动点收藏的无损原图自动同步到图床 `ai-art/` 目录。

## 模块 B：`studio-enhancements/`（Colab Studio 网页增强）
- `comfy-fixed-prompt.js`：注入 Colab Studio 网页，提供固定二次元画风前后缀开关 + 一键 AI 润色提示词按钮（使用前需在脚本里替换成你自己的 LLM 代理地址与模型名）。

## 模块 C：`n8n-workflows/`（定时全自动巡航 & 每日自动搜图，需 n8n）
- `01-daily-anime-art-cruise.json`：每晚 22:00 自动触发画图工坊巡航，只魔改用户手动放进参考池的新图，没有新图绝不开机烧 CU（不装 n8n 也可以用宿主机 `crontab` 一行 `curl` 代替）。
- `02-anime-auto-image-hunter.json`：每日 40 路广域搜集高质量二次元人物图 + AI 视觉审美打分 ≥8 分送入图床待选箱（导入后需替换其中的图床域名、LLM 地址、视觉模型名和 Telegram 通知配置）。
