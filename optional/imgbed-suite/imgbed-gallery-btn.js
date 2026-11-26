(function () {
  if (window.__imgbedGalleryBtnInstalled) return;
  window.__imgbedGalleryBtnInstalled = true;

  var BTN_ID = 'imgbed-gallery-btn';
  var STYLE_ID = 'imgbed-gallery-style';

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = [
      '#' + BTN_ID + ' {',
      '  position: fixed;',
      '  top: 30px;',
      '  left: 104px;',
      '  z-index: 100;',
      '  height: 2.5rem;',
      '  padding: 0 14px 0 12px;',
      '  box-sizing: border-box;',
      '  display: inline-flex;',
      '  align-items: center;',
      '  gap: 7px;',
      '  border-radius: 12px;',
      '  border: 1px solid var(--glass-border, #c9cdd4);',
      '  background-color: var(--glass-bg, hsla(0, 0%, 100%, 0.45));',
      '  backdrop-filter: blur(20px) saturate(1.4);',
      '  -webkit-backdrop-filter: blur(20px) saturate(1.4);',
      '  box-shadow: var(--glass-shadow, none);',
      '  color: var(--theme-toggle-color, #1d2129);',
      '  text-decoration: none;',
      '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;',
      '  font-size: 13.5px;',
      '  font-weight: 500;',
      '  letter-spacing: 0.02em;',
      '  line-height: 1;',
      '  white-space: nowrap;',
      '  cursor: pointer;',
      '  outline: none;',
      '  user-select: none;',
      '  -webkit-user-select: none;',
      '  opacity: 0;',
      '  transform: translateX(-14px) scale(0.97);',
      '  pointer-events: none;',
      '  transition: opacity 0.34s ease, transform 0.34s cubic-bezier(0.22, 1, 0.36, 1), background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, color 0.25s ease;',
      '}',
      '#' + BTN_ID + '.is-visible {',
      '  opacity: 1;',
      '  transform: translateX(0) scale(1);',
      '  pointer-events: auto;',
      '}',
      '#' + BTN_ID + '.is-visible:hover {',
      '  transform: scale(1.04);',
      '  border-color: var(--glass-border-hover, #aeb4be);',
      '  box-shadow: 0 6px 20px rgba(31, 35, 41, 0.12);',
      '}',
      'html.dark #' + BTN_ID + '.is-visible:hover {',
      '  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.38);',
      '}',
      '#' + BTN_ID + '.is-visible:active {',
      '  transform: scale(0.98);',
      '}',
      '#' + BTN_ID + ':focus-visible {',
      '  border-color: var(--primary-color, #2563eb);',
      '  box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary-color, #2563eb) 28%, transparent);',
      '}',
      '#' + BTN_ID + ' .pgb-icon {',
      '  width: 17px;',
      '  height: 17px;',
      '  flex-shrink: 0;',
      '  color: var(--primary-color, #2563eb);',
      '  transition: transform 0.25s ease;',
      '}',
      'html.dark #' + BTN_ID + ' .pgb-icon {',
      '  color: var(--upload-list-file-icon-color, #60a5fa);',
      '}',
      '#' + BTN_ID + ':hover .pgb-icon {',
      '  transform: scale(1.08);',
      '}',
      '#' + BTN_ID + ' .pgb-text-short {',
      '  display: none;',
      '}',
      '#' + BTN_ID + ' .pgb-arrow {',
      '  width: 13px;',
      '  height: 13px;',
      '  flex-shrink: 0;',
      '  opacity: 0.55;',
      '  margin-left: -2px;',
      '  transition: transform 0.25s ease, opacity 0.25s ease;',
      '}',
      '#' + BTN_ID + ':hover .pgb-arrow {',
      '  opacity: 0.95;',
      '  transform: translateX(2px);',
      '}',
      '@media (max-width: 768px) {',
      '  #' + BTN_ID + ' {',
      '    top: 30px;',
      '    left: 90px;',
      '    height: 2rem;',
      '    padding: 0 10px 0 9px;',
      '    gap: 5px;',
      '    border-radius: 10px;',
      '    font-size: 12.5px;',
      '  }',
      '  #' + BTN_ID + ' .pgb-icon {',
      '    width: 15px;',
      '    height: 15px;',
      '  }',
      '  #' + BTN_ID + ' .pgb-arrow {',
      '    display: none;',
      '  }',
      '}',
      '@media (max-width: 480px) {',
      '  #' + BTN_ID + ' {',
      '    padding: 0 9px 0 8px;',
      '    gap: 4px;',
      '    font-size: 12px;',
      '  }',
      '  #' + BTN_ID + ' .pgb-text-full {',
      '    display: none;',
      '  }',
      '  #' + BTN_ID + ' .pgb-text-short {',
      '    display: inline;',
      '  }',
      '}',
      '.imgbed-dashboard-back-btn {',
      '  order: -1;',
      '  height: 32px;',
      '  padding: 0 11px 0 9px;',
      '  box-sizing: border-box;',
      '  display: inline-flex;',
      '  align-items: center;',
      '  justify-content: center;',
      '  gap: 4px;',
      '  border: 1px solid var(--glass-border, #c9cdd4);',
      '  border-radius: 10px;',
      '  background: var(--glass-bg, hsla(0, 0%, 100%, 0.45));',
      '  backdrop-filter: blur(12px);',
      '  -webkit-backdrop-filter: blur(12px);',
      '  color: var(--el-text-color-secondary, #4e5969);',
      '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;',
      '  font-size: 13px;',
      '  font-weight: 500;',
      '  line-height: 1;',
      '  white-space: nowrap;',
      '  cursor: pointer;',
      '  flex-shrink: 0;',
      '  outline: none;',
      '  transition: color 0.16s ease, background-color 0.2s ease, border-color 0.2s ease, transform 0.16s ease;',
      '}',
      '.imgbed-dashboard-back-btn:hover {',
      '  border-color: var(--glass-border-hover, var(--primary-color-accent, #409eff));',
      '  color: var(--primary-color-accent, #409eff);',
      '}',
      '.imgbed-dashboard-back-btn:active {',
      '  transform: scale(0.96);',
      '}',
      '@media (max-width: 768px) {',
      '  .imgbed-dashboard-back-btn {',
      '    height: 28px;',
      '    padding: 0 9px 0 7px;',
      '    border-radius: 8px;',
      '    font-size: 12px;',
      '  }',
      '}'
    ].join('\n');
    (document.head || document.documentElement).appendChild(style);
  }

  function isUploadHome() {
    var path = window.location.pathname || '/';
    return path === '/' || path === '/index.html';
  }

  function ensureButton() {
    var btn = document.getElementById(BTN_ID);
    if (btn) return btn;
    if (!document.body) return null;

    injectStyle();

    btn = document.createElement('a');
    btn.id = BTN_ID;
    btn.href = '/dashboard';
    btn.title = '进入图库查看所有文件夹与图片';
    btn.setAttribute('aria-label', '进入图库');
    btn.innerHTML =
      '<svg class="pgb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.38a2 2 0 0 1 1.48.66l1.02 1.13a2 2 0 0 0 1.48.66H18.5A2.5 2.5 0 0 1 21 9.95v7.55a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/>' +
        '<circle cx="9.2" cy="12.2" r="1.2" fill="currentColor" stroke="none"/>' +
        '<path d="M5.5 17.5l3.6-3.4a1.1 1.1 0 0 1 1.52.04l2.08 2.08 1.65-1.58a1.1 1.1 0 0 1 1.52.03l2.63 2.83"/>' +
      '</svg>' +
      '<span class="pgb-text-full">进入图库</span>' +
      '<span class="pgb-text-short">图库</span>' +
      '<svg class="pgb-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M9 6l6 6-6 6"/>' +
      '</svg>';

    btn.addEventListener('click', function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      try {
        var appEl = document.getElementById('app');
        var router = appEl && appEl.__vue_app__ && appEl.__vue_app__.config && appEl.__vue_app__.config.globalProperties && appEl.__vue_app__.config.globalProperties.$router;
        if (router && typeof router.push === 'function') {
          e.preventDefault();
          router.push('/dashboard');
        }
      } catch (_) {}
    });

    document.body.appendChild(btn);
    return btn;
  }

  function syncPosition(btn) {
    try {
      var logo = document.querySelector('.upload-home .logo--fixed, .logo--fixed');
      if (logo) {
        // Use layout coordinates (offsetLeft + offsetWidth) so CSS entry translate / hover scale never skews placement.
        var rightEdge = (logo.offsetLeft || 0) + (logo.offsetWidth || 0);
        if (rightEdge > 40 && rightEdge < 220) {
          var gap = window.innerWidth <= 768 ? 10 : 14;
          btn.style.left = Math.round(rightEdge + gap) + 'px';
          return;
        }
      }
      btn.style.left = '';
    } catch (_) {}
  }

  var syncScheduled = false;
  function scheduleSync() {
    if (syncScheduled) return;
    syncScheduled = true;
    requestAnimationFrame(function () {
      syncScheduled = false;
      syncVisibility();
    syncDashboardBackButton();
    });
  }

  function syncVisibility() {
    syncDashboardBackButton();
    var loading = document.documentElement.classList.contains('entry-loading');
    var show = !loading && isUploadHome() && Boolean(document.querySelector('.upload-home'));
    if (!show) {
      var existing = document.getElementById(BTN_ID);
      if (existing) existing.classList.remove('is-visible');
      return;
    }
    var btn = ensureButton();
    if (!btn) return;
    if (!btn.classList.contains('is-visible')) {
      syncPosition(btn);
      btn.classList.add('is-visible');
    }
  }

  var origPush = history.pushState;
  history.pushState = function () {
    var ret = origPush.apply(this, arguments);
    scheduleSync();
    return ret;
  };
  var origReplace = history.replaceState;
  history.replaceState = function () {
    var ret = origReplace.apply(this, arguments);
    scheduleSync();
    return ret;
  };
  window.addEventListener('popstate', scheduleSync);
  window.addEventListener('resize', function () {
    var btn = document.getElementById(BTN_ID);
    if (btn && btn.classList.contains('is-visible')) syncPosition(btn);
  });

  var classObserver = new MutationObserver(scheduleSync);
  classObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

  function attachAppObserver() {
    var appEl = document.getElementById('app');
    if (!appEl) return;
    var appObserver = new MutationObserver(function () {
      if (isUploadHome() || (window.location.pathname || '').indexOf('/dashboard') === 0) scheduleSync();
    });
    appObserver.observe(appEl, { childList: true, subtree: true });
  }

  // Click outside the preview image (on dark backdrop/canvas) to close el-image-viewer
  function setupViewerBackdropClose() {
    if (window.__viewerBackdropCloseInstalled) return;
    window.__viewerBackdropCloseInstalled = true;

    var downState = null;
    var NON_BACKDROP_SEL = 'img, .el-image-viewer__img, .el-image-viewer__actions, .el-image-viewer__btn, button, a, input, video, audio';

    document.addEventListener('pointerdown', function (e) {
      if (e.button && e.button !== 0) {
        downState = null;
        return;
      }
      var target = e.target;
      var wrapper = target && target.closest ? target.closest('.el-image-viewer__wrapper') : null;
      if (!wrapper || target.closest(NON_BACKDROP_SEL)) {
        downState = null;
        return;
      }
      downState = { x: e.clientX, y: e.clientY, wrapper: wrapper };
    }, true);

    document.addEventListener('click', function (e) {
      if (!downState) return;
      var st = downState;
      downState = null;

      var target = e.target;
      var wrapper = target && target.closest ? target.closest('.el-image-viewer__wrapper') : null;
      if (!wrapper || wrapper !== st.wrapper || target.closest(NON_BACKDROP_SEL)) return;

      var dx = e.clientX - st.x;
      var dy = e.clientY - st.y;
      if (dx * dx + dy * dy > 64) return;

      var closeBtn = wrapper.querySelector('.el-image-viewer__close');
      if (closeBtn) {
        e.preventDefault();
        e.stopPropagation();
        closeBtn.click();
      }
    }, true);
  }

  // Dashboard toolbar "Back" button: parent folder if in subfolder, or Upload Home if at root
  var BACK_BTN_CLASS = 'imgbed-dashboard-back-btn';

  function syncDashboardBackButton() {
    var path = window.location.pathname || '';
    if (path.indexOf('/dashboard') !== 0) return;

    var container = document.querySelector('.breadcrumb-container');
    if (!container) return;

    injectStyle();

    var items = container.querySelectorAll('.breadcrumb .el-breadcrumb__item');
    var inSubfolder = items.length > 1;
    var btn = container.querySelector('.' + BACK_BTN_CLASS);

    if (!btn) {
      btn = document.createElement('button');
      btn.type = 'button';
      btn.className = BACK_BTN_CLASS;
      btn.innerHTML =
        '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M15 18l-6-6 6-6"/>' +
        '</svg>' +
        '<span>返回</span>';

      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var curItems = container.querySelectorAll('.breadcrumb .el-breadcrumb__item');
        if (curItems.length > 1) {
          var parentItem = curItems[curItems.length - 2];
          var inner = parentItem.querySelector('.el-breadcrumb__inner') || parentItem;
          inner.click();
          return;
        }
        try {
          var appEl = document.getElementById('app');
          var router = appEl && appEl.__vue_app__ && appEl.__vue_app__.config && appEl.__vue_app__.config.globalProperties && appEl.__vue_app__.config.globalProperties.$router;
          if (router && typeof router.push === 'function') {
            router.push('/');
            return;
          }
        } catch (_) {}
        window.location.href = '/';
      });

      container.appendChild(btn);
    }

    var tip = inSubfolder ? '返回上一级文件夹' : '返回上传首页';
    if (btn.title !== tip) {
      btn.title = tip;
      btn.setAttribute('aria-label', tip);
    }
  }

  function init() {
    setupViewerBackdropClose();
    attachAppObserver();
    syncVisibility();
    syncDashboardBackButton();
    setTimeout(syncVisibility, 400);
    setTimeout(syncVisibility, 1200);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
