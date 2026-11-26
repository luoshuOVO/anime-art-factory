(function () {
  if (window.__artProgressBadgeInstalled) return;
  window.__artProgressBadgeInstalled = true;

  // 可通过页面前置 window.__ART_BADGE_CONFIG__ 覆盖，或直接改下面三行地址
  var CFG = window.__ART_BADGE_CONFIG__ || {};
  var API_URL = CFG.apiUrl || '/_custom/art-live-badge';
  var GALLERY_URL = CFG.galleryUrl || 'http://127.0.0.1:28096/';
  var STUDIO_URL = CFG.studioUrl || 'http://127.0.0.1:29091/';
  var STYLE_ID = 'art-factory-badge-style';
  var ROOT_ID = 'art-factory-badge-root';
  var KEY_POS = 'art_factory_badge_pos_v1';
  var KEY_DISMISSED_RUN = 'art_factory_badge_dismissed_run_v1';

  var lastData = null;
  var wasActive = false;
  var initialized = false;
  var popoverOpen = false;
  var timerId = null;
  var origTitle = null;
  var titleFlashing = false;
  var lastNotifiedRun = '';
  var pollInFlight = false;

  // Single global drag state (prevents leaking window event listeners on re-render)
  var drag = {
    active: false,
    moved: false,
    deferredRender: false,
    startX: 0,
    startY: 0,
    startTop: 0,
    startRight: 0,
    justDraggedAt: 0,
  };

  function isDark() {
    try {
      if (document.documentElement.classList.contains('dark')) return true;
      if (document.body && document.body.classList.contains('dark')) return true;
      if (document.documentElement.getAttribute('data-theme') === 'dark') return true;
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    } catch (e) {
      return false;
    }
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent =
      '#' + ROOT_ID + '{position:fixed;z-index:2147483000;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;user-select:none;-webkit-user-select:none;}' +
      '.pab-pill{display:inline-flex;align-items:center;gap:8px;padding:7px 12px;border-radius:999px;cursor:pointer;font-size:12.5px;font-weight:600;line-height:1.2;position:relative;overflow:hidden;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);box-shadow:0 6px 20px rgba(0,0,0,0.16);border:1px solid rgba(148,163,184,0.32);transition:transform .15s ease,box-shadow .15s ease,opacity .2s ease;}' +
      '.pab-pill:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(0,0,0,0.22);}' +
      '.pab-light .pab-pill{background:rgba(255,255,255,0.92);color:#0f172a;}' +
      '.pab-dark .pab-pill{background:rgba(24,24,27,0.9);color:#f8fafc;border-color:rgba(255,255,255,0.16);}' +
      '.pab-dot{width:8px;height:8px;border-radius:50%;flex:none;}' +
      '.pab-dot-active{background:#8b5cf6;box-shadow:0 0 0 0 rgba(139,92,246,0.7);animation:pab-pulse 1.5s infinite;}' +
      '.pab-dot-done{background:#10b981;}' +
      '.pab-dot-warn{background:#f59e0b;box-shadow:0 0 0 0 rgba(245,158,11,0.7);animation:pab-pulse-warn 1.5s infinite;}' +
      '@keyframes pab-pulse{0%{box-shadow:0 0 0 0 rgba(139,92,246,0.55);}70%{box-shadow:0 0 0 8px rgba(139,92,246,0);}100%{box-shadow:0 0 0 0 rgba(139,92,246,0);}}' +
      '@keyframes pab-pulse-warn{0%{box-shadow:0 0 0 0 rgba(245,158,11,0.55);}70%{box-shadow:0 0 0 8px rgba(245,158,11,0);}100%{box-shadow:0 0 0 0 rgba(245,158,11,0);}}' +
      '.pab-bar{position:absolute;left:0;bottom:0;height:2.5px;background:linear-gradient(90deg,#8b5cf6,#ec4899);transition:width .4s ease;}' +
      '.pab-x{margin-left:2px;width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:13px;line-height:1;opacity:.65;border:none;background:transparent;color:inherit;cursor:pointer;padding:0;}' +
      '.pab-x:hover{opacity:1;background:rgba(148,163,184,0.22);}' +
      '.pab-pop{position:absolute;top:calc(100% + 8px);right:0;width:296px;max-width:calc(100vw - 24px);border-radius:14px;padding:13px 14px;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);box-shadow:0 14px 36px rgba(0,0,0,0.24);border:1px solid rgba(148,163,184,0.3);font-size:12.5px;line-height:1.5;}' +
      '.pab-light .pab-pop{background:rgba(255,255,255,0.96);color:#1e293b;}' +
      '.pab-dark .pab-pop{background:rgba(24,24,27,0.95);color:#f1f5f9;border-color:rgba(255,255,255,0.16);}' +
      '.pab-pop-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;font-weight:700;font-size:13px;}' +
      '.pab-pop-row{display:flex;justify-content:space-between;gap:8px;margin:4px 0;font-size:12px;opacity:.9;}' +
      '.pab-pop-stage{padding:7px 9px;border-radius:8px;margin:6px 0 8px;font-size:12px;background:rgba(139,92,246,0.1);}' +
      '.pab-pbar-bg{height:6px;border-radius:999px;background:rgba(148,163,184,0.25);overflow:hidden;margin:6px 0 8px;}' +
      '.pab-pbar-fg{height:100%;border-radius:999px;background:linear-gradient(90deg,#8b5cf6,#ec4899);transition:width .4s ease;}' +
      '.pab-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;}' +
      '.pab-btn{flex:1;min-width:84px;text-align:center;text-decoration:none;padding:6px 10px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid rgba(148,163,184,0.35);background:transparent;color:inherit;transition:background .15s;}' +
      '.pab-btn:hover{background:rgba(148,163,184,0.16);}' +
      '.pab-btn-primary{background:#7c3aed;color:#fff !important;border-color:#7c3aed;}' +
      '.pab-btn-primary:hover{background:#6d28d9;}' +
      '.pab-note{margin-top:8px;font-size:11px;opacity:.65;}' +
      '.pab-toast{position:fixed;right:18px;bottom:92px;z-index:2147483001;width:320px;max-width:calc(100vw - 32px);border-radius:14px;padding:13px 14px;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);box-shadow:0 16px 40px rgba(0,0,0,0.28);border:1px solid rgba(16,185,129,0.45);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;animation:pab-slide .25s ease;}' +
      '.pab-toast.pab-light{background:rgba(255,255,255,0.97);color:#0f172a;}' +
      '.pab-toast.pab-dark{background:rgba(24,24,27,0.96);color:#f8fafc;}' +
      '@keyframes pab-slide{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:translateY(0);}}';
    document.head.appendChild(s);
  }

  function restoreTitle() {
    if (titleFlashing && origTitle !== null) {
      document.title = origTitle;
      titleFlashing = false;
    }
  }

  function flashTitle(prefix) {
    if (!titleFlashing) {
      origTitle = document.title;
      titleFlashing = true;
    }
    document.title = prefix + ' ' + (origTitle || '');
  }

  function loadPos() {
    try {
      var raw = localStorage.getItem(KEY_POS);
      if (!raw) return null;
      var p = JSON.parse(raw);
      if (typeof p.top === 'number' && typeof p.right === 'number') return p;
    } catch (e) {}
    return null;
  }

  function savePos(top, right) {
    try {
      localStorage.setItem(KEY_POS, JSON.stringify({ top: Math.round(top), right: Math.round(right) }));
    } catch (e) {}
  }

  function applyPos(root) {
    if (!root) return;
    var saved = loadPos();
    var top = saved ? saved.top : 56;
    var right = saved ? saved.right : 16;
    var maxTop = Math.max(8, window.innerHeight - 48);
    var maxRight = Math.max(8, window.innerWidth - 140);
    top = Math.min(Math.max(8, top), maxTop);
    right = Math.min(Math.max(8, right), maxRight);
    root.style.top = top + 'px';
    root.style.right = right + 'px';
  }

  function startDrag(root, cx, cy) {
    var rect = root.getBoundingClientRect();
    drag.active = true;
    drag.moved = false;
    drag.startX = cx;
    drag.startY = cy;
    drag.startTop = rect.top;
    drag.startRight = window.innerWidth - rect.right;
  }

  function moveDrag(cx, cy) {
    if (!drag.active) return;
    var root = document.getElementById(ROOT_ID);
    if (!root) return;
    var dx = cx - drag.startX;
    var dy = cy - drag.startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) drag.moved = true;
    if (!drag.moved) return;
    var nextTop = Math.min(Math.max(8, drag.startTop + dy), Math.max(8, window.innerHeight - 48));
    var nextRight = Math.min(Math.max(8, drag.startRight - dx), Math.max(8, window.innerWidth - 120));
    root.style.top = nextTop + 'px';
    root.style.right = nextRight + 'px';
  }

  function endDrag() {
    if (!drag.active) return;
    drag.active = false;
    var wasMoved = drag.moved;
    var needRender = drag.deferredRender;
    drag.deferredRender = false;
    var root = document.getElementById(ROOT_ID);
    if (wasMoved && root) {
      var rect = root.getBoundingClientRect();
      savePos(rect.top, window.innerWidth - rect.right);
      drag.justDraggedAt = Date.now();
    }
    if (needRender) setTimeout(function () { if (lastData && !drag.active) render(lastData); }, 0);
  }

  // Register global listeners ONCE
  window.addEventListener('mousemove', function (e) { moveDrag(e.clientX, e.clientY); });
  window.addEventListener('mouseup', endDrag);
  window.addEventListener('touchmove', function (e) {
    if (drag.active && e.touches[0]) moveDrag(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  window.addEventListener('touchend', endDrag);
  window.addEventListener('resize', function () {
    applyPos(document.getElementById(ROOT_ID));
  });
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
      restoreTitle();
      scheduleNext(300);
    }
  });
  window.addEventListener('focus', restoreTitle);

  function showCompletionToast(data) {
    var run = data.latest_run || {};
    var ok = run.status === 'completed';
    var gpuFree = Number(data.active_gpu_count || 0) === 0;
    var title = ok
      ? (gpuFree ? '🎨 生图完成，显卡已释放' : '🎨 生图完成（显卡正在自动释放）')
      : '⚠️ 生图任务异常结束';

    var parts = [];
    if (typeof run.saved === 'number' && typeof run.jobs === 'number') {
      parts.push('入库 ' + run.saved + '/' + run.jobs + ' 张');
    } else if (typeof run.jobs === 'number') {
      parts.push('共 ' + run.jobs + ' 张');
    }
    if (typeof run.actual_units === 'number') {
      parts.push('花费 ' + run.actual_units.toFixed(2) + ' CU');
    }
    if (typeof data.ccu_balance === 'number') {
      parts.push('剩 ' + data.ccu_balance.toFixed(2) + ' CU');
    }
    if (!ok && run.error) {
      parts.push(String(run.error).slice(0, 60));
    }
    var body = parts.join(' · ') || '成品已自动质检并保存至画廊';

    if (document.hidden) {
      flashTitle(ok ? '✅ 画完了！' : '⚠️ 生图结束');
    }

    var old = document.getElementById('art-factory-toast');
    if (old) old.remove();
    var toast = document.createElement('div');
    toast.id = 'art-factory-toast';
    toast.className = 'pab-toast ' + (isDark() ? 'pab-dark' : 'pab-light');

    var h = document.createElement('div');
    h.style.cssText = 'font-weight:700;font-size:13.5px;margin-bottom:5px;';
    h.textContent = title;
    toast.appendChild(h);

    var p = document.createElement('div');
    p.style.cssText = 'font-size:12.5px;opacity:.88;line-height:1.45;';
    p.textContent = body;
    toast.appendChild(p);

    var act = document.createElement('div');
    act.className = 'pab-actions';

    var go = document.createElement('a');
    go.className = 'pab-btn pab-btn-primary';
    go.href = GALLERY_URL;
    go.target = '_blank';
    go.rel = 'noopener';
    go.textContent = '去看成品图';
    go.onclick = function () { toast.remove(); };
    act.appendChild(go);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'pab-btn';
    closeBtn.textContent = '知道了';
    closeBtn.onclick = function () { toast.remove(); };
    act.appendChild(closeBtn);

    toast.appendChild(act);
    document.body.appendChild(toast);
  }

  function pillInfo(data) {
    var run = data.latest_run;
    var gpuCnt = Number(data.active_gpu_count || 0);
    var nowSec = data.server_time || Math.floor(Date.now() / 1000);
    var finishAge = (run && run.finished_at) ? (nowSec - Number(run.finished_at)) : null;

    if (data.active) {
      var pct = 0;
      if (data.total > 0) pct = Math.min(100, Math.round((data.completed / data.total) * 100));
      var label = '🎨 生图中';
      if (data.phase === 'submitting') label = '🎨 正在提交生图…';
      else if (data.phase === 'retrying_gpu') label = '🎨 排队抢 L4 显卡…';
      else if (data.phase === 'postprocessing') label = '🎨 质检上传中 ' + (data.progress || '');
      else if (data.phase === 'drawing') label = '🎨 画图中 ' + (data.progress || '');
      else if (data.phase === 'queued') label = data.progress ? ('🎨 排队画图中 ' + data.progress) : '🎨 等待分配显卡…';
      return { show: true, dot: 'pab-dot-active', label: label.trim(), pct: pct, dismissible: false };
    }

    if (gpuCnt > 0) {
      // Allow 90s grace window after run completion for normal Colab runtime teardown
      if (finishAge !== null && finishAge >= -60 && finishAge <= 90) {
        return { show: true, dot: 'pab-dot-active', label: '🎨 已画完 · 正在释放显卡…', pct: 100, dismissible: false };
      }
      return { show: true, dot: 'pab-dot-warn', label: '⚠️ 显卡未释放 (' + gpuCnt + '台)', pct: 0, dismissible: false };
    }

    var dismissedRun = '';
    try { dismissedRun = localStorage.getItem(KEY_DISMISSED_RUN) || ''; } catch (e) {}
    if (run && run.run_id && run.run_id !== dismissedRun && finishAge !== null && finishAge >= -60 && finishAge <= 300) {
      var lbl = run.status === 'completed'
        ? ('✅ ' + (run.saved != null ? run.saved : run.jobs) + '张已画完 · 显卡已释放')
        : '⚠️ 生图结束（点击查看）';
      return { show: true, dot: run.status === 'completed' ? 'pab-dot-done' : 'pab-dot-warn', label: lbl, pct: 100, dismissible: true, runId: run.run_id };
    }

    return { show: false };
  }

  function render(data) {
    if (drag.active) {
      drag.deferredRender = true;
      return;
    }
    injectStyle();
    var info = pillInfo(data);
    var root = document.getElementById(ROOT_ID);
    if (!info.show) {
      if (root) root.remove();
      popoverOpen = false;
      return;
    }

    if (!root) {
      root = document.createElement('div');
      root.id = ROOT_ID;
      document.body.appendChild(root);
      applyPos(root);
    }
    root.className = isDark() ? 'pab-dark' : 'pab-light';
    root.innerHTML = '';

    var pill = document.createElement('div');
    pill.className = 'pab-pill';
    pill.title = '点击查看生图详情（可拖动挪位置）';

    var dot = document.createElement('span');
    dot.className = 'pab-dot ' + info.dot;
    pill.appendChild(dot);

    var txt = document.createElement('span');
    txt.textContent = info.label;
    pill.appendChild(txt);

    if (info.dismissible) {
      var x = document.createElement('button');
      x.type = 'button';
      x.className = 'pab-x';
      x.title = '收起提示';
      x.textContent = '×';
      x.onclick = function (e) {
        e.stopPropagation();
        try { if (info.runId) localStorage.setItem(KEY_DISMISSED_RUN, info.runId); } catch (err) {}
        popoverOpen = false;
        render(data);
      };
      pill.appendChild(x);
    }

    if (data.active && info.pct > 0) {
      var bar = document.createElement('div');
      bar.className = 'pab-bar';
      bar.style.width = info.pct + '%';
      pill.appendChild(bar);
    }

    pill.addEventListener('mousedown', function (e) {
      if (e.button !== 0 || e.target.closest('.pab-x')) return;
      startDrag(root, e.clientX, e.clientY);
    });
    pill.addEventListener('touchstart', function (e) {
      if (e.target.closest('.pab-x') || !e.touches[0]) return;
      startDrag(root, e.touches[0].clientX, e.touches[0].clientY);
    }, { passive: true });
    pill.addEventListener('click', function (e) {
      e.stopPropagation();
      if (e.target.closest('.pab-x')) return;
      if (Date.now() - drag.justDraggedAt < 250) return;
      popoverOpen = !popoverOpen;
      render(data);
    });

    root.appendChild(pill);

    if (popoverOpen) {
      var pop = document.createElement('div');
      pop.className = 'pab-pop';
      pop.addEventListener('click', function (e) { e.stopPropagation(); });
      var rRect = root.getBoundingClientRect();
      if (rRect.right < 312) {
        pop.style.left = '0';
        pop.style.right = 'auto';
      }
      if (window.innerHeight - rRect.bottom < 260 && rRect.top > 220) {
        pop.style.bottom = 'calc(100% + 8px)';
        pop.style.top = 'auto';
      }

      var head = document.createElement('div');
      head.className = 'pab-pop-head';
      var titleEl = document.createElement('span');
      titleEl.textContent = '🎨 画图工坊实时状态';
      head.appendChild(titleEl);
      var closePop = document.createElement('button');
      closePop.type = 'button';
      closePop.className = 'pab-x';
      closePop.textContent = '×';
      closePop.onclick = function () { popoverOpen = false; render(data); };
      head.appendChild(closePop);
      pop.appendChild(head);

      var stage = document.createElement('div');
      stage.className = 'pab-pop-stage';
      stage.textContent = data.stage_text || (data.active ? '正在生图中…' : '空闲待命中');
      pop.appendChild(stage);

      if (data.active && data.total > 0) {
        var bg = document.createElement('div');
        bg.className = 'pab-pbar-bg';
        var fg = document.createElement('div');
        fg.className = 'pab-pbar-fg';
        fg.style.width = Math.min(100, Math.round((data.completed / data.total) * 100)) + '%';
        bg.appendChild(fg);
        pop.appendChild(bg);
      }

      function addRow(k, v) {
        var row = document.createElement('div');
        row.className = 'pab-pop-row';
        var kEl = document.createElement('span');
        kEl.style.opacity = '0.72';
        kEl.textContent = k;
        var vEl = document.createElement('span');
        vEl.style.fontWeight = '600';
        vEl.textContent = v;
        row.appendChild(kEl);
        row.appendChild(vEl);
        pop.appendChild(row);
      }

      var gpuCnt = Number(data.active_gpu_count || 0);
      addRow('Colab 显卡', gpuCnt > 0 ? (gpuCnt + ' 台运行中') : '已释放（0 消耗）');
      if (typeof data.ccu_balance === 'number') {
        addRow('剩余额度', data.ccu_balance.toFixed(2) + ' CU');
      }
      if (data.latest_run) {
        var lr = data.latest_run;
        var stMap = { completed: '已完成', running: '进行中', submitting: '提交中', postprocessing: '质检上传中', failed: '异常结束' };
        var stZh = stMap[lr.status] || lr.status;
        var countStr = lr.saved != null
          ? (lr.saved + '/' + lr.jobs + ' 张')
          : (data.active && data.total > 0 ? (data.completed + '/' + data.total + ' 张') : (lr.jobs + ' 张'));
        var runSummary = stZh + ' ' + countStr;
        if (typeof lr.actual_units === 'number') {
          runSummary += ' · 花费 ' + lr.actual_units.toFixed(2) + ' CU';
        }
        addRow('最近一批', runSummary);
      }
      if (data.workflow_label) {
        addRow('当前画师', data.workflow_label.split('（')[0]);
      }

      var acts = document.createElement('div');
      acts.className = 'pab-actions';

      var aImg = document.createElement('a');
      aImg.className = 'pab-btn pab-btn-primary';
      aImg.href = GALLERY_URL;
      aImg.target = '_blank';
      aImg.rel = 'noopener';
      aImg.textContent = '打开成品画廊';
      aImg.onclick = function () {
        if (info.dismissible && info.runId) {
          try { localStorage.setItem(KEY_DISMISSED_RUN, info.runId); } catch (err) {}
          popoverOpen = false;
          render(data);
        }
      };
      acts.appendChild(aImg);

      var aStu = document.createElement('a');
      aStu.className = 'pab-btn';
      aStu.href = STUDIO_URL;
      aStu.target = '_blank';
      aStu.rel = 'noopener';
      aStu.textContent = '看显卡日志';
      acts.appendChild(aStu);

      pop.appendChild(acts);

      var note = document.createElement('div');
      note.className = 'pab-note';
      note.textContent = '进度由服务器独立同步，随时可直接和 AI 对话不卡输入框。';
      pop.appendChild(note);

      root.appendChild(pop);
    }
  }

  function scheduleNext(ms) {
    if (timerId) clearTimeout(timerId);
    timerId = setTimeout(poll, ms);
  }

  async function poll() {
    if (pollInFlight) return;
    pollInFlight = true;
    var nextMs = document.hidden ? 25000 : 20000;
    try {
      var res = await fetch(API_URL, { credentials: 'same-origin', cache: 'no-store' });
      if (res.ok) {
        var data = await res.json();
        if (data && data.ok) {
          var isActive = Boolean(data.active);
          var lr = data.latest_run;
          var lrDone = lr && (lr.status === 'completed' || lr.status === 'failed');

          if (!initialized) {
            initialized = true;
            wasActive = isActive;
          } else {
            if (wasActive && !isActive && lrDone) {
              if (lr.run_id && lr.run_id !== lastNotifiedRun) {
                lastNotifiedRun = lr.run_id;
                showCompletionToast(data);
              }
            }
            wasActive = isActive;
          }

          lastData = data;
          render(data);
          if (isActive || Number(data.active_gpu_count || 0) > 0) {
            nextMs = document.hidden ? 15000 : 7000;
          } else {
            nextMs = document.hidden ? 40000 : 25000;
          }
        }
      } else {
        nextMs = 45000;
      }
    } catch (e) {
      nextMs = 45000;
    } finally {
      pollInFlight = false;
    }
    scheduleNext(nextMs);
  }

  document.addEventListener('click', function (e) {
    if (!popoverOpen) return;
    var root = document.getElementById(ROOT_ID);
    if (root && !root.contains(e.target)) {
      popoverOpen = false;
      if (lastData) render(lastData);
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { scheduleNext(1200); });
  } else {
    scheduleNext(1200);
  }
})();
