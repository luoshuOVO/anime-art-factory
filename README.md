# 二次元自动化生图工坊（Anime Art Factory）

一套**模块化**的二次元自动化生图工作流：核心支持 **直接和 CloudCLI / Claude 聊天生图 + 网页右上角实时进度悬浮标 + AI 自动写词质检 + 科普条漫**，并附带完整可选模块（独立图床增强套装、Studio 画风助手、n8n 定时巡航与自动搜图）。

> **最省事的用法（交给你的 AI 一键部署）**：  
> 直接把本仓库链接发给你的 Claude Code / CloudCLI / Codex，对它说：  
> **「阅读这个仓库的 `AI-DEPLOY.md`，先问我想要极简版还是带图床/巡航的完整版，再帮我部署。」**

---

## 模块一览（核心必装 + 可选按需留）

| 层级 | 目录 | 干什么用的 | 是否必装 |
|---|---|---|---|
| **核心引擎** | [`docker-compose.yml`](./docker-compose.yml) + [`art-factory/`](./art-factory/) | Colab GPU 出图面板 + 自研画图编排（7 比例随机构图、大人物/关键词必中写词铁律、AI 视觉质检拦废图、中文科普条漫、单/双画师热切换、内置中文画廊） | 必装 |
| **核心交互** | [`cloudcli-integration/`](./cloudcli-integration/) | CloudCLI 聊天生图规则（提交秒释放不卡输入框）+ 右上角可拖动进度悬浮标 & 画完页内弹窗 | 推荐必装 |
| **可选模块 A** | [`optional/imgbed-suite/`](./optional/imgbed-suite/) | 独立图床（CloudFlare-ImgBed）+ 文件夹中文显示 + 一键「复制去生图」按钮 + 图库体验优化 + Studio 收藏原画自动同步 | 按需选装 |
| **可选模块 B** | [`optional/studio-enhancements/`](./optional/studio-enhancements/) | Colab Studio 网页固定二次元画风前后缀 & AI 润色助手 | 按需选装 |
| **可选模块 C** | [`optional/n8n-workflows/`](./optional/n8n-workflows/) | 每日 22:00 定时巡航魔改出图 + 每日二次元自动搜图（AI 严选 ≥8 分） | 按需选装 |

> **零外部依赖说明**：只装核心部分时，**完全不需要 n8n、不需要额外装图床、不需要爬虫**，成品自动存本地 `./data/outputs/` 并在内置中文画廊（`http://127.0.0.1:28096/`）查看。

---

## 核心链路示意图

```text
你在 CloudCLI 里说一句话（如“画 4 张银发水手服少女”）
        │
        ▼  AI 调本机接口下单后立刻结束回复（不卡聊天框）
  art-factory（AI 发散提示词 + 7 比例洗牌 + AI 视觉质检 + 科普条漫排版）
        │
        ├──▶ Colab GPU Studio（自动抢 Google Colab 显卡批量连画，画完自动关机省 CU）
        │
        ├──▶ 成品入库（内置本地画廊 / 可选自动上传独立图床 + 自动攒 LoRA 素材集）
        │
        └──▶ CloudCLI 右上角悬浮标（实时显示进度/显卡/剩余 CU，画完页内弹窗提醒）
```

---

## 手动快速起步（如果不让 AI 代装）

### 前置准备（3 样东西）
1. 一台能跑 Docker & Docker Compose 的机器（不吃本地显卡）。
2. 一个 Google 账号（含 Colab GPU 额度）+ Google Cloud OAuth 客户端。
3. 一个兼容 OpenAI 格式的 AI Key（支持文本 + 视觉看图，任意厂商或中转均可）。

### 5 步启动核心版
```bash
# 1. 克隆并复制配置模板
git clone https://github.com/luoshuOVO/anime-art-factory.git
cd anime-art-factory
cp .env.example .env

# 2. 编辑 .env，填入 AI 接口、随机安全密钥、Google OAuth 三组必填项
# 3. 启动核心栈
mkdir -p data studio-data studio-secrets
docker compose up -d --build
```
4. 打开 `http://127.0.0.1:29091` 登录 Colab GPU Studio，绑定 Google 账号并发布工作流（推荐先用 `moss-image-sft-t2i`，熟了再开 `krea2-moss-dual-t2i` 双画师 + 4 LoRA）。
5. 按 [`cloudcli-integration/`](./cloudcli-integration/) 里的说明把规则贴进 `CLAUDE.md` 并注入 Nginx 悬浮标即可开聊生图！

---

## 开源致谢

- 底层 Colab GPU 调度与 ComfyUI 执行引擎引用开源项目 [`Naoya666/colab-comfy-studio`](https://github.com/Naoya666/colab-comfy-studio)（**AGPL-3.0**），独立图床可选模块引用 [`MarSeventh/CloudFlare-ImgBed`](https://github.com/MarSeventh/CloudFlare-ImgBed)。本仓库仅提供编排配置、自研业务层与脱敏模板，不含上游源码及任何个人凭据。
