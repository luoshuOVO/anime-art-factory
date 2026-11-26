(() => {
  if (window.__studioFixedPromptInstalled) return;
  window.__studioFixedPromptInstalled = true;

  const KEY_TEXT = "studio-fixed-prompt-text-v1";
  const KEY_ON = "studio-fixed-prompt-enabled-v1";
  const DEFAULT_TEXT = "日系精致二次元插画，动画电影光影，干净线条，非写实";

  const PRESETS = [
    { label: "剧场版二次元", text: "日系精致二次元插画，动画电影光影，干净线条，非写实" },
    { label: "精致厚涂", text: "日系二次元精致厚涂插画，轻小说封面质感，细腻光影与发丝细节，非写实" },
    { label: "番剧截图", text: "日本动画番剧截图，精致赛璐璐平涂，清晰线稿，柔和阴影，非写实" },
    { label: "清空", text: "" },
  ];

  const BLIND_BOX_THEMES = [
    "雨后黄昏的东京天桥与霓虹倒影",
    "月光下的哥特古堡阳台与红茶",
    "大雪纷飞的日式山顶神社鸟居与灯笼",
    "夏日靠海的复古电车车厢与透进来的阳光",
    "深夜满天繁星的校园天台与微风",
    "秋日落满金黄银杏叶的坡道与校服",
    "樱花纷飞的古风庭院木廊与纸伞",
    "悬浮着发光魔法书的温暖古旧图书馆",
    "冬日雨夜街角温暖的复古咖啡馆落地窗",
    "赛博朋克雨夜霓虹小巷与透明雨伞",
    "山坡盛开向日葵与白色风车的夏日午后",
    "古风元宵灯会河畔与漂浮的莲花灯",
    "清晨阳光斜射进来的安静教室课桌",
    "爬满绿植与玻璃穹顶的阳光花房温室",
    "星光璀璨的livehouse乐队舞台与吉他",
    "海边白色灯塔与橘粉色晚霞防波堤",
    "森林深处萤火虫飞舞的神秘泉水边",
    "深夜亮着暖光的日系街角便利店门口",
    "云海之上的蒸汽朋克飞艇甲板",
    "圣诞飘雪夜亮灯的欧式橱窗街道",
    "夏日祭典烟花绽放的河堤与浴衣",
    "阳光洒落的欧式童话甜品店与草莓蛋糕",
    "竹林清风中的国风侠女与纸鸢",
    "水族馆幽蓝巨大玻璃幕墙与游动水母",
  ];

  let lastThemeIdx = -1;
  let undoValue = null;

  function getPrefix() {
    try {
      const v = localStorage.getItem(KEY_TEXT);
      return v === null ? DEFAULT_TEXT : v;
    } catch {
      return DEFAULT_TEXT;
    }
  }
  function setPrefix(val) {
    try { localStorage.setItem(KEY_TEXT, val); } catch {}
  }
  function isEnabled() {
    try {
      const v = localStorage.getItem(KEY_ON);
      return v === null ? true : v === "1";
    } catch {
      return true;
    }
  }
  function setEnabled(flag) {
    try { localStorage.setItem(KEY_ON, flag ? "1" : "0"); } catch {}
  }

  function joinPrompt(prefixRaw, bodyRaw) {
    const p = (prefixRaw || "").trim();
    const b = (bodyRaw || "").trim();
    if (!p) return bodyRaw;
    if (!b) return p;
    const pNoPunct = p.replace(/[，,。.\s]+$/u, "");
    if (b.startsWith(p) || (pNoPunct && b.startsWith(pNoPunct))) {
      return bodyRaw;
    }
    const sep = /[，,。.\n\s]$/u.test(p) ? "" : "，";
    return p + sep + b;
  }

  function patchJobObj(obj, prefix) {
    if (!obj || typeof obj !== "object" || !obj.params || typeof obj.params !== "object") return false;
    const params = obj.params;
    if (typeof params.prompt !== "string") return false;
    const merged = joinPrompt(prefix, params.prompt);
    if (merged !== params.prompt) {
      params.prompt = merged;
      return true;
    }
    return false;
  }

  // Intercept POST /api/gpu/jobs and /api/gpu/batches to prepend fixed prompt cleanly
  const origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    try {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
      if (
        method === "POST" &&
        isEnabled() &&
        /\/api\/(?:gpu\/)?(?:jobs|batches)(?:\?|$)/.test(url) &&
        init &&
        typeof init.body === "string"
      ) {
        const prefix = getPrefix().trim();
        if (prefix) {
          const data = JSON.parse(init.body);
          let changed = false;
          if (Array.isArray(data.jobs)) {
            for (const j of data.jobs) {
              if (patchJobObj(j, prefix)) changed = true;
            }
          } else {
            changed = patchJobObj(data, prefix);
          }
          if (changed) {
            init = Object.assign({}, init, { body: JSON.stringify(data) });
          }
        }
      }
    } catch (err) {
      console.warn("[fixed-prompt] passthrough on error:", err);
    }
    return origFetch(input, init);
  };

  function setReactTextareaValue(ta, value) {
    const desc = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value");
    if (desc && desc.set) {
      desc.set.call(ta, value);
    } else {
      ta.value = value;
    }
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    ta.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function pickTheme() {
    let idx = Math.floor(Math.random() * BLIND_BOX_THEMES.length);
    if (idx === lastThemeIdx) idx = (idx + 1) % BLIND_BOX_THEMES.length;
    lastThemeIdx = idx;
    return BLIND_BOX_THEMES[idx];
  }

  async function callMagpiePrompt(mode, userSeed) {
    const systemPrompt =
      "你是顶级二次元AI绘画提示词专家，专为MOSS-Image/Anima等中文自然语言生图模型写画面描写。" +
      "规则：1)只输出一段纯中文画面描写（65~115字），禁止输出标题、引号、序号、Markdown或任何解释；" +
      "2)不要写画风总标签（如“日系二次元插画”“非写实”等，因为系统已自动加在开头）；" +
      "3)重点把人物外貌（发色发型瞳色）、精致服装配饰、自然动作神态、景别构图、背景环境与具体光影氛围写生动有画面感。";

    let userPrompt;
    if (mode === "random") {
      const theme = pickTheme();
      userPrompt = `请以「${theme}」为灵感，随机创作一个极具美感与故事感的二次元角色画面描写，人物发色、服装和细节要有新鲜感。直接输出提示词正文：`;
    } else {
      userPrompt = `请把用户的简短想法扩写成一段生动细腻的二次元画面描写，必须保留用户提到的所有核心元素，并补全服装细节、姿态表情、景别构图和氛围光影。\n用户想法：${userSeed}\n直接输出扩写后的提示词正文：`;
    }

    const resp = await origFetch("/_custom/ai-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: mode === "random" ? 0.95 : 0.75,
        max_tokens: 240,
      }),
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const json = await resp.json();
    let text = (json && json.choices && json.choices[0] && json.choices[0].message && json.choices[0].message.content) || "";
    text = text.replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
    text = text.replace(/^["'“”「」『』]+|["'“”「」『』]+$/g, "").trim();
    text = text.replace(/^(?:提示词|画面描写|扩写结果)[：:]\s*/u, "").trim();
    if (!text) throw new Error("空响应");
    return text;
  }

  function injectStyle() {
    if (document.getElementById("studio-fixed-prompt-style")) return;
    const style = document.createElement("style");
    style.id = "studio-fixed-prompt-style";
    style.textContent = `
      #studio-fixed-prompt-card {
        background: #ffffff;
        border: 1px solid #e4e4e7;
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 12px;
        box-sizing: border-box;
      }
      #studio-fixed-prompt-card .sfp-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 10px;
      }
      #studio-fixed-prompt-card .sfp-title {
        font-size: 14px;
        font-weight: 600;
        color: #18181b;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #studio-fixed-prompt-card .sfp-toggle {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: #52525b;
        cursor: pointer;
        user-select: none;
      }
      #studio-fixed-prompt-card .sfp-toggle input {
        width: 14px;
        height: 14px;
        accent-color: #18181b;
        cursor: pointer;
        margin: 0;
      }
      #studio-fixed-prompt-card textarea {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #d4d4d8;
        border-radius: 10px;
        padding: 9px 11px;
        font-size: 13px;
        line-height: 1.5;
        color: #18181b;
        background: #fafafa;
        resize: vertical;
        font-family: inherit;
        outline: none;
        transition: border-color 0.15s, background 0.15s;
      }
      #studio-fixed-prompt-card textarea:focus {
        border-color: #18181b;
        background: #ffffff;
      }
      #studio-fixed-prompt-card.sfp-disabled textarea {
        opacity: 0.55;
      }
      #studio-fixed-prompt-card .sfp-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
      }
      #studio-fixed-prompt-card .sfp-chip {
        border: 1px solid #e4e4e7;
        background: #f4f4f5;
        color: #27272a;
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 12px;
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
      }
      #studio-fixed-prompt-card .sfp-chip:hover {
        background: #e4e4e7;
        border-color: #a1a1aa;
      }
      #studio-fixed-prompt-card .sfp-ai-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px dashed #e4e4e7;
      }
      #studio-fixed-prompt-card .sfp-ai-btn {
        border: 1px solid #18181b;
        background: #18181b;
        color: #ffffff;
        border-radius: 9px;
        padding: 5px 12px;
        font-size: 12.5px;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.15s, background 0.15s;
      }
      #studio-fixed-prompt-card .sfp-ai-btn.secondary {
        background: #ffffff;
        color: #18181b;
        border-color: #d4d4d8;
      }
      #studio-fixed-prompt-card .sfp-ai-btn.secondary:hover:not(:disabled) {
        background: #f4f4f5;
        border-color: #a1a1aa;
      }
      #studio-fixed-prompt-card .sfp-ai-btn:hover:not(:disabled) {
        opacity: 0.88;
      }
      #studio-fixed-prompt-card .sfp-ai-btn:disabled {
        opacity: 0.5;
        cursor: wait;
      }
      #studio-fixed-prompt-card .sfp-status {
        font-size: 12px;
        color: #71717a;
        margin-left: auto;
      }
      #studio-fixed-prompt-card .sfp-status.err {
        color: #dc2626;
      }
      #studio-fixed-prompt-card .sfp-note {
        margin-top: 7px;
        font-size: 11.5px;
        color: #71717a;
      }
    `;
    document.head.appendChild(style);
  }

  function buildCard() {
    const card = document.createElement("section");
    card.id = "studio-fixed-prompt-card";
    const on = isEnabled();
    if (!on) card.classList.add("sfp-disabled");

    const head = document.createElement("div");
    head.className = "sfp-head";

    const title = document.createElement("div");
    title.className = "sfp-title";
    title.textContent = "固定提示词（自动拼在开头）";

    const toggleLabel = document.createElement("label");
    toggleLabel.className = "sfp-toggle";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = on;
    const toggleText = document.createElement("span");
    toggleText.textContent = on ? "已开启" : "已关闭";
    toggleLabel.append(checkbox, toggleText);
    head.append(title, toggleLabel);

    const ta = document.createElement("textarea");
    ta.rows = 2;
    ta.placeholder = "例如：日系精致二次元插画，动画电影光影，干净线条，非写实";
    ta.value = getPrefix();

    checkbox.addEventListener("change", () => {
      const checked = checkbox.checked;
      setEnabled(checked);
      toggleText.textContent = checked ? "已开启" : "已关闭";
      card.classList.toggle("sfp-disabled", !checked);
    });
    ta.addEventListener("input", () => {
      setPrefix(ta.value);
    });

    const chips = document.createElement("div");
    chips.className = "sfp-chips";
    for (const p of PRESETS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sfp-chip";
      btn.textContent = p.label;
      btn.addEventListener("click", () => {
        ta.value = p.text;
        setPrefix(p.text);
        if (p.text && !checkbox.checked) {
          checkbox.checked = true;
          setEnabled(true);
          toggleText.textContent = "已开启";
          card.classList.remove("sfp-disabled");
        }
      });
      chips.appendChild(btn);
    }

    // AI helper row: 🎲 灵感盲盒 + ✨ 一句话扩写 + ↩ 撤销
    const aiRow = document.createElement("div");
    aiRow.className = "sfp-ai-row";

    const btnRandom = document.createElement("button");
    btnRandom.type = "button";
    btnRandom.className = "sfp-ai-btn";
    btnRandom.textContent = "🎲 灵感盲盒";

    const btnExpand = document.createElement("button");
    btnExpand.type = "button";
    btnExpand.className = "sfp-ai-btn secondary";
    btnExpand.textContent = "✨ 一句话扩写";

    const btnUndo = document.createElement("button");
    btnUndo.type = "button";
    btnUndo.className = "sfp-ai-btn secondary";
    btnUndo.textContent = "↩ 撤销";
    btnUndo.style.display = "none";

    const statusEl = document.createElement("span");
    statusEl.className = "sfp-status";
    statusEl.textContent = "直连本机免费 AI (~2秒)";

    function setBusy(busy, msg, isErr) {
      btnRandom.disabled = busy;
      btnExpand.disabled = busy;
      statusEl.textContent = msg || "";
      statusEl.classList.toggle("err", !!isErr);
    }

    async function runAI(mode) {
      const promptTa = document.querySelector('textarea[aria-label="提示词"]');
      if (!promptTa) return;
      const current = (promptTa.value || "").trim();
      if (mode === "expand" && !current) {
        setBusy(false, "请先在下方框里敲几个词（如：海边 白毛 制服），或点灵感盲盒", true);
        promptTa.focus();
        return;
      }
      undoValue = promptTa.value;
      setBusy(true, mode === "random" ? "正在抽二次元灵感…" : "正在扩写画面细节…", false);
      try {
        const result = await callMagpiePrompt(mode, current);
        setReactTextareaValue(promptTa, result);
        btnUndo.style.display = "inline-block";
        setBusy(false, "已填入下方提示词，按 Ctrl+Enter 即可生图", false);
      } catch (err) {
        setBusy(false, `生成失败（${err.message || err}），请重试`, true);
      }
    }

    btnRandom.addEventListener("click", () => runAI("random"));
    btnExpand.addEventListener("click", () => runAI("expand"));
    btnUndo.addEventListener("click", () => {
      const promptTa = document.querySelector('textarea[aria-label="提示词"]');
      if (promptTa && undoValue !== null) {
        setReactTextareaValue(promptTa, undoValue);
        undoValue = null;
        btnUndo.style.display = "none";
        setBusy(false, "已恢复原内容", false);
      }
    });

    aiRow.append(btnRandom, btnExpand, btnUndo, statusEl);

    const note = document.createElement("div");
    note.className = "sfp-note";
    note.textContent = "下方「提示词」只需写人物与场景（或点上方按钮自动生成）；点「立即生成」自动拼接不重复。";

    card.append(head, ta, chips, aiRow, note);
    return card;
  }

  function findPromptCard(textarea) {
    let el = textarea.parentElement;
    for (let i = 0; i < 6 && el && el.parentElement; i++) {
      if (el.tagName === "SECTION" || (el.className && /card|panel|section|block/i.test(String(el.className)))) {
        return el;
      }
      el = el.parentElement;
    }
    return textarea.parentElement ? textarea.parentElement.parentElement : null;
  }

  function ensureMounted() {
    const promptTa = document.querySelector('textarea[aria-label="提示词"]');
    if (!promptTa) return;
    const promptCard = findPromptCard(promptTa);
    if (!promptCard || !promptCard.parentElement) return;
    const existing = document.getElementById("studio-fixed-prompt-card");
    if (existing) {
      if (existing.nextElementSibling !== promptCard) {
        promptCard.parentElement.insertBefore(existing, promptCard);
      }
      return;
    }
    injectStyle();
    const card = buildCard();
    promptCard.parentElement.insertBefore(card, promptCard);
  }

  const mo = new MutationObserver(() => ensureMounted());
  function start() {
    ensureMounted();
    mo.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
