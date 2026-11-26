from __future__ import annotations

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>二次元自动化画图工坊</title>
<style>
  :root {
    --bg: #0f172a;
    --panel: #1e293b;
    --panel-2: #0b1220;
    --border: #334155;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #ec4899;
    --accent-2: #38bdf8;
    --ok: #22c55e;
    --warn: #f59e0b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 24px 16px 60px; }
  header {
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
    gap: 12px; margin-bottom: 18px;
  }
  h1 { margin: 0; font-size: 22px; display: flex; align-items: center; gap: 10px; }
  .pill {
    font-size: 12px; padding: 3px 10px; border-radius: 999px;
    background: rgba(236, 72, 153, 0.16); color: #f9a8d4; border: 1px solid rgba(236, 72, 153, 0.35);
  }
  .status-bar {
    background: var(--panel); border: 1px solid var(--border); border-radius: 14px;
    padding: 14px 18px; margin-bottom: 18px;
    display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px;
  }
  .stat { display: flex; flex-direction: column; gap: 2px; }
  .stat-label { font-size: 12px; color: var(--muted); }
  .stat-val { font-size: 15px; font-weight: 600; }
  .stage-line {
    grid-column: 1 / -1; padding-top: 8px; border-top: 1px solid var(--border);
    font-size: 13px; color: #cbd5e1; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .tab {
    background: var(--panel); color: var(--muted); border: 1px solid var(--border);
    padding: 9px 16px; border-radius: 10px; cursor: pointer; font-size: 14px; font-weight: 600;
  }
  .tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 14px;
    padding: 20px; margin-bottom: 18px;
  }
  .hidden { display: none; }
  .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
  label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
  input, select, textarea {
    width: 100%; background: var(--panel-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px;
    font-size: 14px; font-family: inherit;
  }
  textarea { min-height: 92px; resize: vertical; }
  .row { margin-bottom: 14px; }
  .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
  button.btn {
    border: none; border-radius: 10px; padding: 10px 18px; font-size: 14px; font-weight: 600;
    cursor: pointer; background: var(--accent); color: #fff;
  }
  button.btn.secondary { background: #334155; color: var(--text); }
  button.btn.blue { background: #0284c7; color: #fff; }
  button.btn:disabled { opacity: 0.55; cursor: not-allowed; }
  .toast {
    margin-top: 12px; padding: 12px 14px; border-radius: 10px; font-size: 13px;
    background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.35);
    white-space: pre-wrap; word-break: break-word;
  }
  .toast.err { background: rgba(239, 68, 68, 0.14); border-color: rgba(239, 68, 68, 0.45); color: #fecaca; }
  .gallery {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px;
  }
  .art-item {
    background: var(--panel-2); border: 1px solid var(--border); border-radius: 12px;
    overflow: hidden; display: flex; flex-direction: column;
  }
  .art-item img {
    width: 100%; height: 220px; object-fit: cover; cursor: zoom-in; background: #020617;
  }
  .art-meta { padding: 10px 12px; font-size: 12px; }
  .art-title { font-weight: 600; font-size: 13px; margin-bottom: 4px; color: var(--text); }
  .art-sub { color: var(--muted); }
  .modal {
    position: fixed; inset: 0; background: rgba(2, 6, 23, 0.88);
    display: none; align-items: center; justify-content: center; padding: 20px; z-index: 99;
  }
  .modal.open { display: flex; }
  .modal img { max-width: 95vw; max-height: 92vh; border-radius: 10px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>二次元自动化画图工坊 <span class="pill">AI 写词 · 自动质检 · 省 CU 批画</span></h1>
    <button class="btn secondary" onclick="refreshAll()">刷新状态</button>
  </header>

  <div class="status-bar" id="statusBar">
    <div class="stat"><span class="stat-label">当前状态</span><span class="stat-val" id="stPhase">加载中…</span></div>
    <div class="stat"><span class="stat-label">默认画师工作流</span><span class="stat-val" id="stWf">-</span></div>
    <div class="stat"><span class="stat-label">待画队列</span><span class="stat-val" id="stQueue">-</span></div>
    <div class="stat"><span class="stat-label">Colab 剩余 CU</span><span class="stat-val" id="stCcu">-</span></div>
    <div class="stage-line">
      <span id="stStage">正在读取运行状态…</span>
      <span id="stStorage"></span>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('wish', this)">灵感生图</button>
    <button class="tab" onclick="switchTab('comic', this)">文章转科普漫画</button>
    <button class="tab" onclick="switchTab('control', this)">队列与工作流</button>
    <button class="tab" onclick="switchTab('gallery', this)">最近成品画廊</button>
  </div>

  <section id="tab-wish" class="card">
    <div class="row">
      <label>你想画什么？（直接用中文描述角色、服装、场景或氛围）</label>
      <textarea id="wishIdea" placeholder="例如：银发红瞳的少女穿着黑色水手服和白丝，在黄昏雨后的东京电车站台撑着透明雨伞回眸微笑"></textarea>
    </div>
    <div class="grid-2 row">
      <div>
        <label>发散张数（1~20）</label>
        <input id="wishCount" type="number" min="1" max="20" value="4" />
      </div>
      <div>
        <label>画幅比例</label>
        <select id="wishAspect">
          <option value="random" selected>随机 7 比例洗牌（推荐）</option>
          <option value="portrait">竖版立绘（3:4 / 2:3 / 9:16）</option>
          <option value="landscape">横版壁纸（16:9 / 3:2 / 4:3）</option>
          <option value="square">方形插画（1:1）</option>
        </select>
      </div>
      <div>
        <label>画师工作流</label>
        <select id="wishWorkflow">
          <option value="">跟随默认设置</option>
          <option value="dual">Krea-2 + MOSS 双画师（电影光影 + 二次元）</option>
          <option value="moss">单 MOSS 画师（快、省 CU、纯二次元）</option>
        </select>
      </div>
      <div>
        <label>附加画风偏好（选填）</label>
        <input id="wishStyle" placeholder="例如：京阿尼柔光、新海诚光影、轻小说封面" />
      </div>
    </div>
    <div class="row">
      <label>参考图链接（选填，留空则纯文生图）</label>
      <input id="wishRef" placeholder="https://..." />
    </div>
    <div class="actions">
      <button class="btn" id="btnWishNow" onclick="submitWish('now')">立刻开机开画</button>
      <button class="btn secondary" id="btnWishLater" onclick="submitWish('later')">先攒进待画队列（省 CU）</button>
    </div>
    <div id="wishMsg" class="toast hidden"></div>
  </section>

  <section id="tab-comic" class="card hidden">
    <div class="row">
      <label>文章链接（选填）</label>
      <input id="comicUrl" placeholder="https://... （或直接在下面粘贴正文）" />
    </div>
    <div class="row">
      <label>文章正文 / 科普主题（选填，与链接二选一即可）</label>
      <textarea id="comicText" placeholder="粘贴一段你想做成二次元科普条漫的文章、笔记或知识点…"></textarea>
    </div>
    <div class="grid-2 row">
      <div>
        <label>漫画类型</label>
        <select id="comicStyle">
          <option value="explainer" selected>科普图解条漫</option>
          <option value="four_panel">四格日常漫</option>
          <option value="story">番剧分镜长图</option>
        </select>
      </div>
      <div>
        <label>分镜格数（3~6）</label>
        <input id="comicPanels" type="number" min="3" max="6" value="4" />
      </div>
      <div>
        <label>固定角色人设（选填）</label>
        <input id="comicPersona" placeholder="留空使用默认：温柔学姐 + 好奇助手" />
      </div>
      <div>
        <label>补充要求（选填）</label>
        <input id="comicHint" placeholder="例如：风格轻松搞笑、适合新手看懂" />
      </div>
    </div>
    <div class="actions">
      <button class="btn" id="btnComicNow" onclick="submitComic('now')">立刻生成科普条漫</button>
      <button class="btn secondary" id="btnComicLater" onclick="submitComic('later')">仅写分镜并攒入队列</button>
    </div>
    <div id="comicMsg" class="toast hidden"></div>
  </section>

  <section id="tab-control" class="card hidden">
    <div class="actions" style="margin-bottom: 14px;">
      <button class="btn" onclick="runControl('flush')">把待画队列立刻发车</button>
      <button class="btn blue" onclick="runCruise()">触发参考图二创巡航</button>
      <button class="btn secondary" onclick="runControl('set_workflow', 'dual')">默认切到双画师 (dual)</button>
      <button class="btn secondary" onclick="runControl('set_workflow', 'moss')">默认切到单 MOSS (moss)</button>
      <button class="btn secondary" onclick="runControl('clear_queue')">清空待画队列</button>
    </div>
    <p style="font-size:13px; color: var(--muted); margin: 0 0 10px;">
      提示：想用「参考图二创巡航」，把喜欢的参考图放进图床 <code>ai-draw-inbox</code>（未配图床时放到服务器 <code>./data/ref-inbox/</code> 目录），点击触发即可按原图比例自动魔改，没有新图不会开机烧 CU。
    </p>
    <div id="ctrlMsg" class="toast hidden"></div>
    <div id="queueList" style="margin-top: 14px; font-size: 13px; color: var(--muted);"></div>
  </section>

  <section id="tab-gallery" class="card hidden">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
      <span style="font-size:14px; color:var(--muted);">最近质检通过的成品（点击图片查看大图）</span>
      <button class="btn secondary" onclick="loadGallery()">刷新画廊</button>
    </div>
    <div id="galleryGrid" class="gallery"></div>
  </section>
</div>

<div class="modal" id="imgModal" onclick="this.classList.remove('open')">
  <img id="modalImg" src="" alt="preview" />
</div>

<script>
function showToast(id, msg, isErr=false) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'toast' + (isErr ? ' err' : '');
}
function switchTab(name, btn) {
  document.querySelectorAll('section[id^="tab-"]').forEach(s => s.classList.add('hidden'));
  document.getElementById('tab-' + name).classList.remove('hidden');
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (name === 'gallery') loadGallery();
  if (name === 'control') refreshStatusDetail();
}
async function apiPost(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || data.message || ('HTTP ' + r.status));
  return data;
}
async function refreshBadge() {
  try {
    const [badge, health] = await Promise.all([
      fetch('/api/live-badge').then(r => r.json()),
      fetch('/health').then(r => r.json())
    ]);
    document.getElementById('stPhase').textContent = badge.active ? ('运行中 ' + (badge.progress || '')) : '空闲待命';
    document.getElementById('stWf').textContent = (badge.workflow_label || '-').split('（')[0];
    document.getElementById('stQueue').textContent = (badge.pending_queue_count ?? 0) + ' 项';
    document.getElementById('stCcu').textContent = badge.ccu_balance != null ? (badge.ccu_balance + ' CU') : '待首次查询';
    document.getElementById('stStage').textContent = badge.stage_text || '';
    document.getElementById('stStorage').textContent = '存图模式：' + (health.storage_mode || '本地目录');
  } catch (e) {
    document.getElementById('stStage').textContent = '状态读取失败：' + e.message;
  }
}
async function refreshStatusDetail() {
  try {
    const d = await apiPost('/api/control', { cmd: 'status' });
    const list = d.pending_preview || [];
    document.getElementById('queueList').innerHTML = list.length
      ? '<b>当前待画队列预览：</b><br>' + list.map((x, i) => `${i+1}. [${x.kind}] ${x.title}`).join('<br>')
      : '当前待画队列为空。';
  } catch (e) {}
}
async function submitWish(mode) {
  const idea = document.getElementById('wishIdea').value.trim();
  if (!idea) return showToast('wishMsg', '请先写下你想画的画面灵感', true);
  showToast('wishMsg', '正在请 AI 发散提示词并提交任务，请稍候…');
  try {
    const data = await apiPost('/api/wish', {
      idea,
      count: Number(document.getElementById('wishCount').value || 4),
      aspect: document.getElementById('wishAspect').value,
      workflow: document.getElementById('wishWorkflow').value,
      style_hint: document.getElementById('wishStyle').value.trim(),
      ref_image_url: document.getElementById('wishRef').value.trim(),
      mode
    });
    const preview = (data.prompts_preview || []).map((p, i) => `${i+1}. [${p.ratio}] ${p.title}`).join('\\n');
    showToast('wishMsg', (data.message || '提交成功') + (preview ? '\\n\\n本批方案：\\n' + preview : ''));
    refreshBadge();
  } catch (e) {
    showToast('wishMsg', '提交失败：' + e.message, true);
  }
}
async function submitComic(mode) {
  const url = document.getElementById('comicUrl').value.trim();
  const text = document.getElementById('comicText').value.trim();
  if (!url && !text) return showToast('comicMsg', '请至少填写文章链接或正文内容', true);
  showToast('comicMsg', '正在请 AI 拆解分镜脚本并提交任务，请稍候…');
  try {
    const data = await apiPost('/api/comic', {
      url, text,
      style: document.getElementById('comicStyle').value,
      panels: Number(document.getElementById('comicPanels').value || 4),
      persona: document.getElementById('comicPersona').value.trim(),
      custom_hint: document.getElementById('comicHint').value.trim(),
      mode
    });
    showToast('comicMsg', data.message || '漫画任务已提交');
    refreshBadge();
  } catch (e) {
    showToast('comicMsg', '提交失败：' + e.message, true);
  }
}
async function runControl(cmd, value=null) {
  showToast('ctrlMsg', '正在执行…');
  try {
    const data = await apiPost('/api/control', { cmd, value });
    showToast('ctrlMsg', data.message || JSON.stringify(data, null, 2));
    refreshBadge();
    refreshStatusDetail();
  } catch (e) {
    showToast('ctrlMsg', '执行失败：' + e.message, true);
  }
}
async function runCruise() {
  showToast('ctrlMsg', '正在扫描参考图原料池并触发巡航…');
  try {
    const data = await apiPost('/api/cruise/run', {});
    showToast('ctrlMsg', (data.launch && data.launch.message) || data.message || '巡航已触发');
    refreshBadge();
  } catch (e) {
    showToast('ctrlMsg', '触发失败：' + e.message, true);
  }
}
async function loadGallery() {
  const grid = document.getElementById('galleryGrid');
  grid.innerHTML = '<div style="color:var(--muted)">加载中…</div>';
  try {
    const data = await apiPost('/api/control', { cmd: 'recent', limit: 30 });
    const items = data.items || [];
    if (!items.length) {
      grid.innerHTML = '<div style="color:var(--muted)">暂时还没有成品，去「灵感生图」画第一批吧！</div>';
      return;
    }
    grid.innerHTML = items.map(it => `
      <div class="art-item">
        <img src="${it.public_url}" loading="lazy" onclick="openModal('${it.public_url}')" alt="${it.title || ''}" />
        <div class="art-meta">
          <div class="art-title">${it.title || '未命名'}</div>
          <div class="art-sub">评分：${it.score ?? '-'} · ${it.review || it.kind}</div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    grid.innerHTML = '<div style="color:#fca5a5">加载失败：' + e.message + '</div>';
  }
}
function openModal(src) {
  document.getElementById('modalImg').src = src;
  document.getElementById('imgModal').classList.add('open');
}
function refreshAll() { refreshBadge(); refreshStatusDetail(); }
refreshBadge();
setInterval(refreshBadge, 15000);
</script>
</body>
</html>
"""
