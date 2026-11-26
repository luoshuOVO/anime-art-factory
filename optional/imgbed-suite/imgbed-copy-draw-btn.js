(function () {
  if (window.__imgbedCopyDrawInstalled) return;
  window.__imgbedCopyDrawInstalled = true;

  var TARGET_FOLDER = 'ai-draw-inbox';
  var STYLE_ID = 'imgbed-copy-draw-style';
  var TOAST_ID = 'imgbed-copy-draw-toast';
  var BTN_CLASS = 'imgbed-copy-draw-btn';

  var ICON_WAND =
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/>' +
      '<path d="M17.8 11.8 19 13"/><path d="M15 9h0"/>' +
      '<path d="M17.8 6.2 19 5"/><path d="M3 21l9-9"/><path d="M12.2 6.2 11 5"/>' +
    '</svg>';

  var ICON_SPIN =
    '<svg class="pcd-spin" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">' +
      '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>' +
    '</svg>';

  var ICON_CHECK =
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M20 6 9 17l-5-5"/>' +
    '</svg>';

  // Real-time cache of filenames already inside ai-draw-inbox (cross-refresh dedup)
  var targetNames = new Set();
  var lastFetchedAt = 0;
  var fetchInFlight = null;

  function normalizeName(name) {
    if (!name) return '';
    var s = String(name).trim();
    var idx = s.lastIndexOf('/');
    if (idx !== -1) s = s.slice(idx + 1);
    return s.toLowerCase();
  }

  async function refreshTargetNames(force) {
    var now = Date.now();
    if (!force && lastFetchedAt > 0 && now - lastFetchedAt < 15000) {
      return targetNames;
    }
    if (fetchInFlight) return fetchInFlight;

    function fetchWithTimeout(url, opts, timeoutMs) {
      var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeoutMs) : null;
      var merged = Object.assign({}, opts || {});
      if (ctrl) merged.signal = ctrl.signal;
      return fetch(url, merged).finally(function () {
        if (timer) clearTimeout(timer);
      });
    }

    fetchInFlight = (async function () {
      try {
        var resp = await fetchWithTimeout(
          '/api/manage/list?dir=' + encodeURIComponent(TARGET_FOLDER) + '&count=-1',
          { credentials: 'include' },
          10000
        );
        if (resp.ok) {
          var data = await resp.json();
          var files = Array.isArray(data && data.files) ? data.files : [];
          var next = new Set();
          for (var i = 0; i < files.length; i++) {
            var n = files[i] && files[i].name;
            if (n) next.add(normalizeName(n));
          }
          targetNames = next;
          lastFetchedAt = Date.now();
          scheduleScan();
        }
      } catch (_) {
        // Keep existing cache on transient network error
      } finally {
        fetchInFlight = null;
      }
      return targetNames;
    })();

    return fetchInFlight;
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = [
      '.' + BTN_CLASS + ' {',
      '  order: -1;',
      '  width: clamp(24px, 2.5vw, 28px);',
      '  height: clamp(24px, 2.5vw, 28px);',
      '  padding: 0;',
      '  margin: 0;',
      '  border: 1px solid rgba(196, 181, 253, 0.38);',
      '  border-radius: clamp(5px, 0.6vw, 8px);',
      '  background: rgba(139, 92, 246, 0.28);',
      '  color: #f5f3ff;',
      '  cursor: pointer;',
      '  display: inline-flex;',
      '  align-items: center;',
      '  justify-content: center;',
      '  flex-shrink: 0;',
      '  transition: all 0.2s ease;',
      '  outline: none;',
      '}',
      '.' + BTN_CLASS + ':hover {',
      '  background: rgba(139, 92, 246, 0.55);',
      '  border-color: rgba(221, 214, 254, 0.72);',
      '  transform: scale(1.08);',
      '}',
      '.' + BTN_CLASS + ':active {',
      '  transform: scale(0.94);',
      '}',
      '.' + BTN_CLASS + '.is-loading {',
      '  cursor: wait;',
      '  opacity: 0.85;',
      '  background: rgba(139, 92, 246, 0.45);',
      '}',
      '.' + BTN_CLASS + '.is-done {',
      '  background: rgba(16, 185, 129, 0.55);',
      '  border-color: rgba(167, 243, 208, 0.75);',
      '  color: #ecfdf5;',
      '}',
      '.' + BTN_CLASS + '.is-list {',
      '  width: 28px;',
      '  height: 28px;',
      '  border-radius: 7px;',
      '  background: rgba(139, 92, 246, 0.14);',
      '  border-color: rgba(139, 92, 246, 0.35);',
      '  color: #7c3aed;',
      '}',
      '.' + BTN_CLASS + '.is-list:hover {',
      '  background: rgba(139, 92, 246, 0.28);',
      '  color: #5b21b6;',
      '}',
      '.' + BTN_CLASS + '.is-list.is-done {',
      '  background: rgba(16, 185, 129, 0.2);',
      '  border-color: rgba(16, 185, 129, 0.55);',
      '  color: #059669;',
      '}',
      'html.dark .' + BTN_CLASS + '.is-list {',
      '  background: rgba(139, 92, 246, 0.25);',
      '  color: #ddd6fe;',
      '}',
      'html.dark .' + BTN_CLASS + '.is-list.is-done {',
      '  background: rgba(16, 185, 129, 0.3);',
      '  color: #a7f3d0;',
      '}',
      '@keyframes pcdSpin {',
      '  from { transform: rotate(0deg); }',
      '  to { transform: rotate(360deg); }',
      '}',
      '.' + BTN_CLASS + ' .pcd-spin {',
      '  animation: pcdSpin 0.85s linear infinite;',
      '}',
      '#' + TOAST_ID + ' {',
      '  position: fixed;',
      '  top: 22px;',
      '  left: 50%;',
      '  transform: translate(-50%, -14px);',
      '  z-index: 99999;',
      '  padding: 10px 18px;',
      '  border-radius: 12px;',
      '  background: rgba(17, 24, 39, 0.86);',
      '  backdrop-filter: blur(16px) saturate(1.4);',
      '  -webkit-backdrop-filter: blur(16px) saturate(1.4);',
      '  border: 1px solid rgba(255, 255, 255, 0.16);',
      '  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);',
      '  color: #f9fafb;',
      '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;',
      '  font-size: 13.5px;',
      '  font-weight: 500;',
      '  line-height: 1.4;',
      '  white-space: nowrap;',
      '  max-width: 90vw;',
      '  overflow: hidden;',
      '  text-overflow: ellipsis;',
      '  pointer-events: none;',
      '  opacity: 0;',
      '  transition: opacity 0.24s ease, transform 0.24s ease;',
      '}',
      '#' + TOAST_ID + '.is-show {',
      '  opacity: 1;',
      '  transform: translate(-50%, 0);',
      '}',
      '#' + TOAST_ID + '.is-error {',
      '  background: rgba(153, 27, 27, 0.9);',
      '  border-color: rgba(252, 165, 165, 0.35);',
      '}'
    ].join('\n');
    (document.head || document.documentElement).appendChild(style);
  }

  var toastTimer = null;
  function showToast(msg, isError) {
    injectStyle();
    var el = document.getElementById(TOAST_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = TOAST_ID;
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.toggle('is-error', Boolean(isError));
    el.classList.add('is-show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.classList.remove('is-show');
    }, isError ? 4200 : 3200);
  }

  function getImageSrc(container, isList) {
    var img = container.querySelector(
      isList ? 'img.list-preview-img, .list-preview-img img' : '.image-preview img, img.image-preview'
    );
    if (!img) return '';
    var src = img.getAttribute('src') || img.getAttribute('data-src') || '';
    if (!src || src.indexOf('data:') === 0) return '';
    return src;
  }

  function isAlreadyInTarget(src) {
    try {
      var u = new URL(src, window.location.origin);
      var decoded = decodeURIComponent(u.pathname || '');
      return decoded.indexOf('/file/' + TARGET_FOLDER + '/') === 0;
    } catch (_) {
      return src.indexOf('/file/' + TARGET_FOLDER + '/') !== -1;
    }
  }

  function extractFilename(src) {
    try {
      var u = new URL(src, window.location.origin);
      var parts = (u.pathname || '').split('/').filter(Boolean);
      var last = parts.length ? decodeURIComponent(parts[parts.length - 1]) : '';
      if (last && /\.[a-z0-9]{2,5}$/i.test(last)) return last;
    } catch (_) {}
    return 'ref_' + Date.now() + '.webp';
  }

  function setBtnDone(btn) {
    btn.classList.remove('is-loading');
    btn.classList.add('is-done');
    btn.innerHTML = ICON_CHECK;
    btn.title = '已在生图参考池中（不会重复复制）';
    btn.setAttribute('aria-label', '已在生图参考池中');
  }

  function resetBtn(btn) {
    btn.classList.remove('is-loading', 'is-done');
    btn.innerHTML = ICON_WAND;
    btn.title = '复制去生图（送到生图参考池，原图不动）';
    btn.setAttribute('aria-label', '复制去生图');
  }

  function syncBtnVisual(btn, src) {
    if (btn.classList.contains('is-loading')) return;
    var norm = normalizeName(extractFilename(src));
    if (norm && targetNames.has(norm)) {
      if (!btn.classList.contains('is-done')) setBtnDone(btn);
    } else if (btn.dataset.src !== src) {
      resetBtn(btn);
    }
  }

  async function handleCopyClick(btn, container, isList) {
    if (btn.classList.contains('is-loading')) return;

    var src = getImageSrc(container, isList);
    if (!src) {
      showToast('图片还没加载完，稍等一下再点', true);
      return;
    }
    if (isAlreadyInTarget(src)) {
      showToast('这张图已经在「生图参考池」里了，无需重复复制', false);
      return;
    }

    var fileName = extractFilename(src);
    var normName = normalizeName(fileName);

    btn.classList.add('is-loading');
    btn.innerHTML = ICON_SPIN;
    btn.title = '正在检查并复制到生图参考池...';

    try {
      // Live server-side check before uploading so refreshes / multi-tabs never create duplicates
      await refreshTargetNames(true);
      if (normName && targetNames.has(normName)) {
        setBtnDone(btn);
        showToast('这张图已经在「生图参考池」里了，不会重复复制', false);
        return;
      }

      var imgCtrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var imgTimer = imgCtrl ? setTimeout(function () { imgCtrl.abort(); }, 25000) : null;
      var imgResp;
      try { imgResp = await fetch(src, { credentials: 'include', signal: imgCtrl ? imgCtrl.signal : undefined }); }
      finally { if (imgTimer) clearTimeout(imgTimer); }
      if (!imgResp.ok) {
        throw new Error('读取原图失败 (' + imgResp.status + ')');
      }
      var blob = await imgResp.blob();
      if (!blob || !blob.size) {
        throw new Error('原图内容为空');
      }

      var file = new File([blob], fileName, { type: blob.type || 'image/webp' });
      var formData = new FormData();
      formData.append('file', file);

      var uploadUrl =
        '/upload?uploadChannel=cfr2&uploadFolder=' +
        encodeURIComponent(TARGET_FOLDER) +
        '&uploadNameType=origin&returnFormat=default';

      var upCtrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var upTimer = upCtrl ? setTimeout(function () { upCtrl.abort(); }, 25000) : null;
      var upResp;
      try {
        upResp = await fetch(uploadUrl, {
          method: 'POST',
          body: formData,
          credentials: 'include',
          signal: upCtrl ? upCtrl.signal : undefined
        });
      } finally { if (upTimer) clearTimeout(upTimer); }

      if (!upResp.ok) {
        var errText = '';
        try { errText = (await upResp.text()).slice(0, 80); } catch (_) {}
        throw new Error('上传失败 (' + upResp.status + ')' + (errText ? ' ' + errText : ''));
      }

      var data = await upResp.json();
      var uploadedSrc = Array.isArray(data)
        ? (data[0] && data[0].src)
        : (data && data.src);
      if (!uploadedSrc) {
        throw new Error('图床返回异常');
      }

      targetNames.add(normName);
      targetNames.add(normalizeName(uploadedSrc));
      lastFetchedAt = Date.now();

      setBtnDone(btn);
      showToast('已复制到「生图参考池」，原图不动，现在可以放心移入「正式壁纸」', false);
    } catch (err) {
      resetBtn(btn);
      showToast('复制去生图失败：' + (err && err.message ? err.message : '网络异常'), true);
    }
  }

  function createButton(container, isList) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = BTN_CLASS + (isList ? ' is-list' : '');
    resetBtn(btn);
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      handleCopyClick(btn, container, isList);
    });
    return btn;
  }

  function syncItem(container, actionBar, isList) {
    if (!container || !actionBar) return;
    var existing = actionBar.querySelector('.' + BTN_CLASS);
    var src = getImageSrc(container, isList);

    if (!src || isAlreadyInTarget(src)) {
      if (existing) existing.remove();
      return;
    }

    if (!existing) {
      var btn = createButton(container, isList);
      btn.dataset.src = src;
      syncBtnVisual(btn, src);
      actionBar.appendChild(btn);
      return;
    }

    syncBtnVisual(existing, src);
    existing.dataset.src = src;
  }

  function scan() {
    var path = window.location.pathname || '';
    if (path.indexOf('/dashboard') !== 0) return;

    injectStyle();
    if (lastFetchedAt === 0) refreshTargetNames(false);

    var cards = document.querySelectorAll('.img-card:not(.folder-card)');
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var bar = card.querySelector('.action-bar-right');
      if (bar) syncItem(card, bar, false);
    }

    var rows = document.querySelectorAll('.list-item');
    for (var j = 0; j < rows.length; j++) {
      var row = rows[j];
      if (row.querySelector('.list-folder-icon')) continue;
      var actions = row.querySelector('.list-col-actions');
      if (actions) syncItem(row, actions, true);
    }
  }

  var scheduled = false;
  function scheduleScan() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      scan();
    });
  }

  function init() {
    scan();
    if (document.body) {
      var observer = new MutationObserver(scheduleScan);
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['src']
      });
    }
    setTimeout(scan, 400);
    setTimeout(scan, 1200);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
