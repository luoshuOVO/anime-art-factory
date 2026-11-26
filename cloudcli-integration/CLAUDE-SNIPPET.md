# 把下面这段内容复制到你 CloudCLI 工作区的 `CLAUDE.md` 里即可

复制虚线以下内容到 `CLAUDE.md` 后，你就能直接用自然语言跟 Claude 聊天生图（例如：「帮我画 4 张银发水手服少女」「把这段文字做成 4 格科普漫画」「切到双画师」「现在画到第几张了」），**完全不需要 n8n**！

---

## 二次元画图工坊（`art-factory`，地址 `http://127.0.0.1:28096`）

- **不卡会话铁律**：调用画图/漫画接口并拿到提交成功响应后，**立刻简短汇报给用户并结束本轮回复**；严禁挂后台轮询脚本死盯到画完而霸占聊天输入框。实时进度由网页右上角悬浮标（`art-progress-badge.js`）展示，画完后自动弹窗提醒。
- **用户说想画什么（灵感生图）**：
  ```bash
  curl -sS -X POST http://127.0.0.1:28096/api/wish \
    -H 'Content-Type: application/json' \
    -d '{"idea":"用户的画面想法","count":4,"aspect":"random","mode":"now"}'
  ```
  - `aspect` 可选：`random`（默认 7 比例随机洗牌）、`portrait`（竖图）、`landscape`（横图）、`square`（方图）
  - `mode`：`now` 立刻开机画；`later` 先攒进待画队列省 CU
  - `workflow`（选填）：`moss`（单 MOSS 画师）或 `dual`（Krea-2+MOSS 双画师），不传跟随默认
  - `ref_image_url`（选填）：传入参考图 URL 做风格参考二创
- **用户想把文章/文字做成二次元科普条漫**：
  ```bash
  curl -sS -X POST http://127.0.0.1:28096/api/comic \
    -H 'Content-Type: application/json' \
    -d '{"text":"文章正文或知识点","style":"explainer","panels":4,"mode":"now"}'
  ```
  - `style` 可选：`explainer`（科普条漫）、`four_panel`（四格日常）、`story`（番剧分镜）；也可传 `url` 代替 `text`
- **用户随时追问进度 / 剩余 CU**：单次秒查即可
  ```bash
  curl -sS http://127.0.0.1:28096/api/live-badge
  ```
- **切换画师 / 队列控制 / 查看最近成品**：
  ```bash
  # 查详细状态 / 队列立刻发车 / 清空队列 / 切默认画师(moss或dual) / 看最近成品
  curl -sS -X POST http://127.0.0.1:28096/api/control \
    -H 'Content-Type: application/json' \
    -d '{"cmd":"status"}'
  # cmd 可选：status | flush | clear_queue | set_workflow (value:"moss"|"dual") | recent
  ```
