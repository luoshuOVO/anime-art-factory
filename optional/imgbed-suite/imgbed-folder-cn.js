(function () {
  if (window.__imgbedFolderCnInstalled) return;
  window.__imgbedFolderCnInstalled = true;

  // =========================================================================
  // 图床文件夹中文显示映射表（仅改网页显示，不改底层目录名/URL/脚本）
  // 后续在图床新开英文文件夹时，在此字典新增一行即可自动全界面显示中文。
  // =========================================================================
  var FOLDER_MAP = {
    'wallpapers':       { cn: '正式壁纸',       desc: '全站与登录页轮播背景' },
    'wallpapers-inbox': { cn: '自动搜图待选',   desc: '每日自动广域搜图待选箱（上限 200 张，可当壁纸或复制去生图）' },
    'ai-draw-inbox':    { cn: '生图参考池',     desc: '放入参考图供每晚 22:00 自动魔改出图' },
    'ai-art-inbox':     { cn: 'AI出图待审',     desc: '画图工坊初筛后的待审新图' },
    'ai-art-archive':   { cn: 'AI出图留存',     desc: '不算惊艳但不想废弃的留存图' },
    'ai-art':           { cn: 'Studio收藏原画', desc: 'Colab Studio 点收藏自动同步的无损原画' },
    'comics':           { cn: '科普条漫',       desc: '文章转科普条漫成品' },
    'lora-pool':        { cn: '画风精选池',     desc: '精选归集，供后续训练专属画风' },
    'charts':           { cn: '图表杂项',       desc: '手动保存的架构与拓扑图表' }
  };

  var STYLE_ID = 'imgbed-folder-cn-style';
  var CLASS_INLINE = 'imgbed-cn-inline';
  var CLASS_LIST = 'imgbed-cn-list';
  var ATTR_LABEL = 'data-cn-label';
  var ATTR_ORIG_TITLE = 'data-cn-orig-title';

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = [
      '.' + CLASS_INLINE + ' {',
      '  font-size: 0 !important;',
      '}',
      '.' + CLASS_INLINE + '::before {',
      '  content: attr(' + ATTR_LABEL + ');',
      '  font-size: var(--imgbed-cn-fs, 14px);',
      '  line-height: var(--imgbed-cn-lh, inherit);',
      '  display: inline;',
      '  vertical-align: baseline;',
      '}',
      '.' + CLASS_LIST + ' > * {',
      '  display: none !important;',
      '}',
      '.' + CLASS_LIST + '::before {',
      '  content: attr(' + ATTR_LABEL + ');',
      '  display: inline;',
      '}'
    ].join('\n');
    (document.head || document.documentElement).appendChild(style);
  }

  function lookupFolder(rawText, includeRawInLabel) {
    if (!rawText) return null;
    var trimmed = String(rawText).trim();
    if (!trimmed) return null;

    var cleaned = trimmed.replace(/^\/+|\/+$/g, '');
    if (!cleaned) return null;

    var segments = cleaned.split('/');
    var matchedAny = false;
    var mappedSegments = [];
    var descs = [];

    for (var i = 0; i < segments.length; i++) {
      var seg = segments[i];
      var key = seg.toLowerCase();
      if (Object.prototype.hasOwnProperty.call(FOLDER_MAP, key)) {
        matchedAny = true;
        mappedSegments.push(FOLDER_MAP[key].cn);
        descs.push(FOLDER_MAP[key].desc);
      } else {
        mappedSegments.push(seg);
      }
    }

    if (!matchedAny) return null;

    var cnPath = mappedSegments.join('/');
    var label = includeRawInLabel ? (cnPath + ' (' + cleaned + ')') : cnPath;
    var title = cnPath + '（原目录：' + cleaned + (descs.length === 1 && descs[0] ? ' · ' + descs[0] : '') + '）';
    return { label: label, title: title };
  }

  function clearElement(el) {
    if (!el) return;
    if (el.classList.contains(CLASS_INLINE)) el.classList.remove(CLASS_INLINE);
    if (el.classList.contains(CLASS_LIST)) el.classList.remove(CLASS_LIST);
    if (el.hasAttribute(ATTR_LABEL)) el.removeAttribute(ATTR_LABEL);
    if (el.hasAttribute(ATTR_ORIG_TITLE)) {
      var origTitle = el.getAttribute(ATTR_ORIG_TITLE);
      if (origTitle) {
        el.setAttribute('title', origTitle);
      } else {
        el.removeAttribute('title');
      }
      el.removeAttribute(ATTR_ORIG_TITLE);
    }
  }

  function applyInline(el, includeRawInLabel) {
    if (!el || el.querySelector('svg, img, input, textarea')) {
      clearElement(el);
      return;
    }
    var raw = el.textContent;
    var hit = lookupFolder(raw, includeRawInLabel);
    if (!hit) {
      clearElement(el);
      return;
    }
    if (!el.classList.contains(CLASS_INLINE)) {
      try {
        var cs = window.getComputedStyle(el);
        if (cs && cs.fontSize && cs.fontSize !== '0px') {
          el.style.setProperty('--imgbed-cn-fs', cs.fontSize);
        }
        if (cs && cs.lineHeight && cs.lineHeight !== '0px') {
          el.style.setProperty('--imgbed-cn-lh', cs.lineHeight);
        }
      } catch (_) {}
    }
    if (!el.hasAttribute(ATTR_ORIG_TITLE)) {
      el.setAttribute(ATTR_ORIG_TITLE, el.getAttribute('title') || '');
    }
    if (el.getAttribute(ATTR_LABEL) !== hit.label) {
      el.setAttribute(ATTR_LABEL, hit.label);
    }
    if (el.getAttribute('title') !== hit.title) {
      el.setAttribute('title', hit.title);
    }
    if (!el.classList.contains(CLASS_INLINE)) {
      el.classList.add(CLASS_INLINE);
    }
  }

  function applyListFolder(el) {
    if (!el) return;
    var raw = el.textContent;
    var hit = lookupFolder(raw, false);
    if (!hit) {
      clearElement(el);
      return;
    }
    if (!el.hasAttribute(ATTR_ORIG_TITLE)) {
      el.setAttribute(ATTR_ORIG_TITLE, el.getAttribute('title') || '');
    }
    if (el.getAttribute(ATTR_LABEL) !== hit.label) {
      el.setAttribute(ATTR_LABEL, hit.label);
    }
    if (el.getAttribute('title') !== hit.title) {
      el.setAttribute('title', hit.title);
    }
    if (!el.classList.contains(CLASS_LIST)) {
      el.classList.add(CLASS_LIST);
    }
  }

  function translateAll() {
    injectStyle();

    // 1. 文件夹卡片视图
    var cardNames = document.querySelectorAll('.folder-card .file-name');
    for (var i = 0; i < cardNames.length; i++) {
      applyInline(cardNames[i], false);
    }

    // 2. 列表视图（仅限含文件夹图标的行）
    var listItems = document.querySelectorAll('.list-item');
    for (var j = 0; j < listItems.length; j++) {
      var item = listItems[j];
      var nameEl = item.querySelector('.list-col-name .filename-ellipsis');
      if (!nameEl) continue;
      if (item.querySelector('.list-folder-icon')) {
        applyListFolder(nameEl);
      } else if (nameEl.classList.contains(CLASS_LIST)) {
        clearElement(nameEl);
      }
    }

    // 3. 顶部面包屑导航（桌面端 + 移动端）
    var crumbs = document.querySelectorAll('.breadcrumb .el-breadcrumb__inner, .mobile-directory-path');
    for (var k = 0; k < crumbs.length; k++) {
      applyInline(crumbs[k], false);
    }

    // 4. 目录树选择器（移动文件弹窗 / 移动端抽屉 / 目录树 Popover）
    var treeLabels = document.querySelectorAll('.directory-tree .node-label');
    for (var m = 0; m < treeLabels.length; m++) {
      applyInline(treeLabels[m], true);
    }

    // 5. 上传页目录建议下拉项
    var suggestions = document.querySelectorAll('.directory-suggestion-input .suggestion-list li');
    for (var n = 0; n < suggestions.length; n++) {
      applyInline(suggestions[n], true);
    }
  }

  var scheduled = false;
  function scheduleTranslate() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      translateAll();
    });
  }

  function init() {
    translateAll();
    if (document.body) {
      var observer = new MutationObserver(scheduleTranslate);
      observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
    setTimeout(translateAll, 300);
    setTimeout(translateAll, 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
