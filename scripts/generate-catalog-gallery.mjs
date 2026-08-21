import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const catalogFile = new URL('../output/svga-public-catalog.json', import.meta.url);
const relatedDetailsFile = new URL('../output/svga-related-details.json', import.meta.url);
const outputFile = new URL('../output/index.html', import.meta.url);

const requiredFields = [
  'source',
  'goodsId',
  'name',
  'number',
  'category',
  'tag',
  'usage',
  'dimension',
  'fileInfo',
  'tagList',
  'relatedItems',
  'thumbnailUrl',
  'publicPreviewUrl',
  'previewFormat',
  'previewSupport',
  'detailUrl',
  'sourceApiUrl',
  'priceVisibility',
  'capturedAt',
];

const catalogSource = JSON.parse(await readFile(catalogFile, 'utf8'));
if (!Array.isArray(catalogSource)) {
  throw new Error('svga-public-catalog.json must contain an array');
}

let relatedDetailsSource = {};
try {
  relatedDetailsSource = JSON.parse(await readFile(relatedDetailsFile, 'utf8'));
} catch {
  relatedDetailsSource = {};
}
if (!relatedDetailsSource || typeof relatedDetailsSource !== 'object' || Array.isArray(relatedDetailsSource)) {
  throw new Error('svga-related-details.json must contain an object');
}

const catalogItems = catalogSource.map((item, index) => {
  if (
    !item ||
    typeof item !== 'object' ||
    item.source !== 'svga.wang' ||
    requiredFields.some((field) => !(field in item)) ||
    !String(item.goodsId)
  ) {
    throw new Error(`invalid public catalog record at index ${index}`);
  }
  if (
    !Array.isArray(item.tagList) ||
    !Array.isArray(item.relatedItems) ||
    item.tagList.some((tag) => typeof tag !== 'string') ||
    item.relatedItems.some(
      (related) =>
        !related ||
        typeof related !== 'object' ||
        typeof related.goodsId !== 'string' ||
        typeof related.name !== 'string' ||
        typeof related.thumbnailUrl !== 'string',
    )
  ) {
    throw new Error(`invalid normalized detail fields at index ${index}`);
  }
  return item;
});

const html = String.raw`<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <title>SVGA.WANG 公开商品目录</title>
  <style>
    :root {
      color-scheme: light;
      --canvas: #f3f4f6;
      --surface: #ffffff;
      --ink: #1f2933;
      --muted: #68727d;
      --line: #d7dde3;
      --accent: #d84f5e;
      --accent-hover: #ba3f4c;
      --teal: #167e77;
      --preview: #171c22;
      --shadow: 0 14px 36px rgba(20, 31, 43, 0.15);
    }

    * { box-sizing: border-box; }
    body {
      min-width: 320px;
      margin: 0;
      color: var(--ink);
      background: var(--canvas);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, a { font: inherit; }
    button, a { -webkit-tap-highlight-color: transparent; }
    .shell { width: min(1440px, calc(100% - 32px)); margin: 0 auto; padding: 30px 0 42px; }
    .topbar {
      display: flex;
      gap: 24px;
      align-items: end;
      justify-content: space-between;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--line);
    }
    .eyebrow {
      margin: 0 0 6px;
      color: var(--teal);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    h1 { margin: 0; font-size: 28px; line-height: 1.15; letter-spacing: 0; }
    .intro { margin: 8px 0 0; color: var(--muted); font-size: 14px; line-height: 1.5; }
    .status { min-width: 180px; margin: 0; color: var(--muted); font-size: 13px; text-align: right; }
    .status strong { display: block; color: var(--ink); font-size: 16px; }
    .filters { padding: 20px 0 4px; }
    .filter-row { display: flex; gap: 14px; align-items: center; justify-content: space-between; }
    .filter-summary { color: var(--teal); font-size: 13px; font-weight: 800; }
    .search {
      width: min(360px, 100%);
      min-height: 38px;
      padding: 8px 11px;
      color: var(--ink);
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 5px;
      outline: none;
    }
    .search:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(216, 79, 94, 0.13); }
    .filter-stack { margin-top: 13px; }
    .category-list {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 2px 2px 8px;
      scrollbar-width: thin;
    }
    .category-list::-webkit-scrollbar { height: 6px; }
    .category-chip {
      flex: 0 0 auto;
      min-height: 34px;
      padding: 7px 15px;
      color: var(--ink);
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 999px;
      cursor: pointer;
      white-space: nowrap;
      font-weight: 600;
    }
    .category-chip:hover, .category-chip:focus-visible { color: var(--accent); border-color: var(--accent); outline: none; }
    .category-chip[aria-pressed="true"], .category-chip.active { color: #ffffff; background: var(--accent); border-color: var(--accent); }
    .category-chip small { opacity: 0.74; font-weight: 700; }
    .usage-filter { display: flex; align-items: flex-start; gap: 10px; margin-top: 10px; }
    .usage-label { flex: 0 0 auto; padding-top: 7px; color: var(--teal); font-size: 13px; font-weight: 800; }
    .usage-chips { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
    .usage-chip {
      min-height: 28px;
      padding: 5px 11px;
      color: var(--muted);
      font-size: 12px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 5px;
      cursor: pointer;
      white-space: nowrap;
    }
    .usage-chip:hover, .usage-chip:focus-visible { color: var(--ink); border-color: var(--teal); outline: none; }
    .usage-chip[aria-pressed="true"], .usage-chip.active { color: #ffffff; background: var(--teal); border-color: var(--teal); }
    .usage-chip small { opacity: 0.82; }
    .usage-group-label { margin: 0 2px 0 8px; color: var(--muted); font-size: 12px; font-weight: 800; white-space: nowrap; }
    .gallery {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .catalog-card {
      display: block;
      width: 100%;
      min-width: 0;
      padding: 0;
      overflow: hidden;
      color: inherit;
      text-align: left;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 7px;
      cursor: pointer;
      transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
    }
    .catalog-card:hover, .catalog-card:focus-visible {
      border-color: var(--accent);
      box-shadow: 0 8px 20px rgba(216, 79, 94, 0.16);
      outline: none;
      transform: translateY(-2px);
    }
    .thumb {
      display: grid;
      width: 100%;
      aspect-ratio: 1 / 1;
      place-items: center;
      overflow: hidden;
      background: #e8edf1;
    }
    .thumb img, .thumb video { width: 100%; height: 100%; object-fit: contain; }
    .missing-media {
      display: grid;
      width: 100%;
      min-height: 96px;
      height: 100%;
      place-items: center;
      padding: 16px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      text-align: center;
      background: repeating-linear-gradient(45deg, #edf0f3 0, #edf0f3 9px, #e4e8ec 9px, #e4e8ec 18px);
    }
    .card-body { padding: 11px 12px 12px; }
    .card-meta { display: flex; gap: 8px; justify-content: space-between; color: var(--teal); font-size: 11px; font-weight: 800; }
    .card-number, .card-format { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .card-format { color: var(--muted); font-weight: 700; }
    .card-title {
      display: -webkit-box;
      min-height: 38px;
      margin: 8px 0 0;
      overflow: hidden;
      font-size: 14px;
      line-height: 1.35;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }
    .card-category {
      display: block;
      overflow: hidden;
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .pager { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; justify-content: center; min-height: 42px; margin-top: 26px; }
    .pager button {
      min-width: 36px;
      height: 34px;
      padding: 0 10px;
      color: var(--ink);
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 5px;
      cursor: pointer;
    }
    .pager button:hover:not(:disabled), .pager button:focus-visible { color: var(--accent); border-color: var(--accent); outline: none; }
    .pager button[aria-current="page"] { color: #ffffff; background: var(--accent); border-color: var(--accent); }
    .pager button:disabled { color: #a2a9b2; cursor: not-allowed; }
    .ellipsis { min-width: 20px; color: var(--muted); text-align: center; }
    .empty { grid-column: 1 / -1; padding: 64px 20px; color: var(--muted); text-align: center; background: var(--surface); border: 1px dashed var(--line); border-radius: 7px; }
    .modal[hidden] { display: none; }
    .modal { position: fixed; z-index: 20; inset: 0; display: grid; place-items: center; padding: 20px; background: rgba(5, 13, 25, 0.82); }
    .detail-dialog {
      display: grid;
      grid-template-columns: minmax(360px, 1.1fr) minmax(340px, 0.9fr);
      width: min(1180px, 100%);
      max-height: min(850px, calc(100vh - 40px));
      overflow: hidden;
      color: #edf5ff;
      background: #112745;
      border: 1px solid rgba(200, 220, 241, 0.18);
      border-radius: 7px;
      box-shadow: 0 22px 60px rgba(0, 0, 0, 0.42);
    }
    .detail-preview { position: relative; display: grid; min-height: 600px; place-items: center; overflow: hidden; background: #0b1c34; }
    .detail-preview img, .detail-preview video { display: block; width: 100%; height: 100%; max-height: min(820px, calc(100vh - 40px)); object-fit: contain; }
    .detail-preview .missing-media { max-width: 380px; height: 190px; color: #d9e7f4; background: rgba(255, 255, 255, 0.09); }
    .close-button {
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 1;
      display: grid;
      width: 34px;
      height: 34px;
      place-items: center;
      padding: 0;
      color: #ffffff;
      background: rgba(0, 0, 0, 0.55);
      border: 0;
      border-radius: 50%;
      cursor: pointer;
    }
    .detail-panel { display: flex; flex-direction: column; min-width: 0; gap: 18px; padding: 24px; overflow: auto; }
    .detail-heading { display: grid; grid-template-columns: 116px minmax(0, 1fr); gap: 15px; align-items: start; }
    .detail-cover-frame {
      display: grid;
      width: 116px;
      aspect-ratio: 1 / 1;
      place-items: center;
      overflow: hidden;
      background: #0a1a31;
      border: 1px solid rgba(206, 225, 244, 0.18);
      border-radius: 5px;
    }
    .detail-cover-frame img { width: 100%; height: 100%; object-fit: contain; }
    .detail-cover-frame .missing-media { min-height: 100%; padding: 10px; color: #bacbe0; background: rgba(255, 255, 255, 0.06); }
    .detail-number { margin: 0 0 7px; color: #7ad0c7; font-size: 12px; font-weight: 800; }
    .detail-panel h2 { margin: 0; color: #ffffff; font-size: 22px; line-height: 1.25; }
    .detail-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
    .detail-tag { padding: 4px 7px; color: #dcecf9; font-size: 11px; line-height: 1.2; background: rgba(84, 162, 190, 0.18); border: 1px solid rgba(151, 208, 226, 0.26); border-radius: 4px; }
    .detail-metadata { display: grid; grid-template-columns: 88px minmax(0, 1fr); gap: 8px 12px; margin: 0; padding: 15px 0; border-top: 1px solid rgba(211, 227, 244, 0.15); border-bottom: 1px solid rgba(211, 227, 244, 0.15); }
    .detail-metadata dt { color: #9eb6ce; font-size: 12px; }
    .detail-metadata dd { min-width: 0; margin: 0; color: #eff7ff; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
    .detail-file-info { margin: 0; padding: 10px 12px; color: #e2f2ff; font-size: 12px; line-height: 1.5; background: rgba(43, 116, 154, 0.22); border-left: 3px solid #49b2c0; border-radius: 3px; }
    .related-section { min-width: 0; }
    .related-section h3 { margin: 0 0 10px; color: #ffffff; font-size: 14px; line-height: 1.3; }
    .related-items { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .related-card { min-width: 0; }
    .related-thumb { display: grid; width: 100%; aspect-ratio: 1 / 1; place-items: center; overflow: hidden; background: #0a1a31; border: 1px solid rgba(206, 225, 244, 0.16); border-radius: 4px; }
    .related-thumb img { width: 100%; height: 100%; object-fit: contain; }
    .related-thumb .missing-media { min-height: 100%; padding: 7px; color: #aebfd2; background: rgba(255, 255, 255, 0.05); font-size: 10px; }
    .related-name { display: block; margin-top: 5px; overflow: hidden; color: #c7d8e8; font-size: 10px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
    .related-empty { margin: 0; color: #9eb6ce; font-size: 12px; line-height: 1.5; }
    .actions { display: grid; gap: 8px; margin-top: auto; padding-top: 2px; }
    .actions button, .actions a {
      display: inline-flex;
      min-height: 38px;
      align-items: center;
      justify-content: center;
      padding: 8px 12px;
      color: #eaf4ff;
      text-decoration: none;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(211, 227, 244, 0.2);
      border-radius: 5px;
      cursor: pointer;
    }
    .actions button:hover:not(:disabled), .actions button:focus-visible, .actions a:hover, .actions a:focus-visible { color: #ffffff; border-color: #62c4d0; outline: none; }
    .actions .primary { color: #ffffff; background: var(--accent); border-color: var(--accent); }
    .actions .primary:hover:not(:disabled), .actions .primary:focus-visible { color: #ffffff; background: var(--accent-hover); border-color: var(--accent-hover); }
    .actions button:disabled { color: #9ca5af; background: #edf0f2; border-color: #edf0f2; cursor: not-allowed; }
    .modal-navigation { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    @media (max-width: 1180px) { .gallery { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
    @media (max-width: 820px) {
      .shell { width: min(100% - 24px, 720px); padding-top: 20px; }
      .topbar { align-items: start; }
      .gallery { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
      .detail-dialog { grid-template-columns: 1fr; overflow-y: auto; }
      .detail-preview { min-height: min(58vh, 440px); }
      .detail-panel { min-height: 390px; }
    }
    @media (max-width: 560px) {
      .topbar, .filter-row { display: block; }
      .status { margin-top: 16px; text-align: left; }
      .search { width: 100%; margin-top: 11px; }
      .gallery { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .pager button { min-width: 33px; padding: 0 7px; }
      .modal { padding: 10px; }
      .detail-dialog { max-height: calc(100vh - 20px); }
      .detail-preview { min-height: min(48vh, 360px); }
      .detail-panel { padding: 18px; }
      .detail-heading { grid-template-columns: 92px minmax(0, 1fr); }
      .detail-cover-frame { width: 92px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Public Catalog</p>
        <h1>SVGA.WANG 公开商品目录</h1>
        <p class="intro">仅包含匿名公开商品元数据与可公开预览媒体。</p>
      </div>
      <p class="status"><strong id="range-status">Loading</strong><span id="total-status"></span></p>
    </header>

    <section class="filters" aria-label="商品筛选">
      <div class="filter-row">
        <strong id="filter-summary" class="filter-summary">全部分类</strong>
        <input id="catalog-search" class="search" type="search" placeholder="搜索商品、编号、分类..." aria-label="搜索商品">
      </div>
      <div class="filter-stack">
        <div id="category-list" class="category-list" role="tablist" aria-label="商品分类"></div>
        <div class="usage-filter">
          <span class="usage-label">用途</span>
          <div id="usage-chips" class="usage-chips"></div>
        </div>
      </div>
    </section>

    <section id="catalog-gallery" class="gallery" aria-live="polite"></section>
    <nav id="catalog-pager" class="pager" aria-label="商品分页"></nav>
  </main>

  <div id="modal" class="modal" hidden role="presentation">
    <section class="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div id="preview" class="detail-preview">
        <button id="close-button" class="close-button" type="button" aria-label="关闭预览">×</button>
      </div>
      <aside class="detail-panel">
        <div class="detail-heading">
          <div id="detail-cover-frame" class="detail-cover-frame"></div>
          <div>
            <p id="detail-number" class="detail-number"></p>
            <h2 id="modal-title">商品预览</h2>
            <div id="detail-tags" class="detail-tags"></div>
          </div>
        </div>
        <dl id="detail-metadata" class="detail-metadata"></dl>
        <p id="detail-file-info" class="detail-file-info" hidden></p>
        <section class="related-section">
          <h3>关联商品</h3>
          <div id="related-items" class="related-items"></div>
        </section>
        <div class="actions">
          <button id="replay-button" class="primary" type="button">Refresh / Replay</button>
          <button id="copy-button" type="button">复制 URL</button>
          <a id="open-source" target="_blank" rel="noreferrer">打开商品页</a>
          <div class="modal-navigation">
            <button id="previous-button" type="button">上一条</button>
            <button id="next-button" type="button">下一条</button>
          </div>
        </div>
      </aside>
    </section>
  </div>

  <script>
const SVGA_CATALOG_ITEMS = ${JSON.stringify(catalogItems)};
const SVGA_RELATED_DETAILS = ${JSON.stringify(relatedDetailsSource)};

const PAGE_SIZE = 50;
const galleryState = { page: 1, selectedCategory: '', selectedUsage: '', query: '' };
const modalState = { index: null, opener: null, virtual: null };

const catalogSearch = document.querySelector('#catalog-search');
const categoryList = document.querySelector('#category-list');
const usageChips = document.querySelector('#usage-chips');
const filterSummary = document.querySelector('#filter-summary');
const gallery = document.querySelector('#catalog-gallery');
const pager = document.querySelector('#catalog-pager');
const rangeStatus = document.querySelector('#range-status');
const totalStatus = document.querySelector('#total-status');
const modal = document.querySelector('#modal');
const preview = document.querySelector('#preview');
const closeButton = document.querySelector('#close-button');
const modalTitle = document.querySelector('#modal-title');
const detailNumber = document.querySelector('#detail-number');
const detailCoverFrame = document.querySelector('#detail-cover-frame');
const detailTags = document.querySelector('#detail-tags');
const detailMetadata = document.querySelector('#detail-metadata');
const detailFileInfo = document.querySelector('#detail-file-info');
const relatedItems = document.querySelector('#related-items');
const replayButton = document.querySelector('#replay-button');
const copyButton = document.querySelector('#copy-button');
const openSource = document.querySelector('#open-source');
const previousButton = document.querySelector('#previous-button');
const nextButton = document.querySelector('#next-button');

function missingMedia(container, message) {
  const placeholder = document.createElement('div');
  placeholder.className = 'missing-media';
  placeholder.textContent = message;
  container.replaceChildren(placeholder);
  if (container === preview) container.append(closeButton);
}

function renderImage(container, url, label) {
  const image = document.createElement('img');
  image.src = url;
  image.alt = label;
  image.loading = container === preview ? 'eager' : 'lazy';
  image.decoding = 'async';
  image.addEventListener('error', () => {
    missingMedia(container, '该媒体无法在浏览器中预览。');
  }, { once: true });
  container.replaceChildren(image);
  if (container === preview) container.append(closeButton);
}

function renderVideo(container, url, label) {
  const video = document.createElement('video');
  video.src = url;
  video.muted = true;
  video.autoplay = true;
  video.loop = true;
  video.playsInline = true;
  video.controls = container === preview;
  video.setAttribute('aria-label', label);
  video.addEventListener('error', () => {
    missingMedia(container, '该视频无法在浏览器中预览。');
  }, { once: true });
  container.replaceChildren(video);
  if (container === preview) container.append(closeButton);
}

function renderThumbnail(container, item) {
  if (item.thumbnailUrl) {
    renderImage(container, item.thumbnailUrl, item.name);
    return;
  }
  missingMedia(container, '未提供公开缩略图。');
}

function categories() {
  const counts = new Map();
  for (const item of SVGA_CATALOG_ITEMS) {
    const category = item.category || '未分类';
    counts.set(category, (counts.get(category) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function filteredItems() {
  const query = galleryState.query.trim().toLocaleLowerCase();
  return SVGA_CATALOG_ITEMS.filter((item) => {
    const category = item.category || '未分类';
    const categoryMatches = !galleryState.selectedCategory || category === galleryState.selectedCategory;
    const tags = item.tagList || [];
    const usageMatches = !galleryState.selectedUsage
      || tags.includes(galleryState.selectedUsage)
      || item.tag === galleryState.selectedUsage;
    const searchable = [
      item.name,
      item.number,
      item.category,
      item.tag,
      item.usage,
      item.dimension,
      ...tags,
    ].join(' ').toLocaleLowerCase();
    return categoryMatches && usageMatches && (!query || searchable.includes(query));
  });
}

function pageCount(items) {
  return Math.max(1, Math.ceil(items.length / PAGE_SIZE));
}

function pageItems() {
  const items = filteredItems();
  const count = pageCount(items);
  if (galleryState.page > count) galleryState.page = count;
  const start = (galleryState.page - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, items.length);
  return { items, start, end, visible: items.slice(start, end) };
}

function paginationItems(page, count) {
  const candidates = new Set([1, count, page - 1, page, page + 1]);
  const pages = [...candidates].filter((candidate) => candidate >= 1 && candidate <= count).sort((a, b) => a - b);
  const result = [];
  let previous = 0;
  for (const current of pages) {
    if (current - previous > 1) result.push('ellipsis-' + current);
    result.push(current);
    previous = current;
  }
  return result;
}

function renderPager(count) {
  pager.replaceChildren();
  const addButton = (label, target, disabled, current) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.disabled = disabled;
    if (current) button.setAttribute('aria-current', 'page');
    button.addEventListener('click', () => {
      galleryState.page = target;
      renderCatalogPage();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    pager.append(button);
  };

  addButton('上一页', galleryState.page - 1, galleryState.page === 1, false);
  for (const value of paginationItems(galleryState.page, count)) {
    if (typeof value === 'string') {
      const ellipsis = document.createElement('span');
      ellipsis.className = 'ellipsis';
      ellipsis.textContent = '...';
      pager.append(ellipsis);
    } else {
      addButton(String(value), value, false, value === galleryState.page);
    }
  }
  addButton('下一页', galleryState.page + 1, galleryState.page === count, false);
}

function usageGroups() {
  const groups = { 国内: [], 海外: [], 其他: [] };
  const seen = new Set();
  const regionOf = (tag) => {
    let domestic = 0;
    let overseas = 0;
    for (const item of SVGA_CATALOG_ITEMS) {
      const tags = item.tagList || [];
      if (!tags.includes(tag)) continue;
      if (tags.includes('国内')) domestic += 1;
      if (tags.includes('海外')) overseas += 1;
    }
    if (domestic > overseas) return '国内';
    if (overseas > domestic) return '海外';
    return domestic ? '国内' : '其他';
  };
  for (const item of SVGA_CATALOG_ITEMS) {
    for (const tag of item.tagList || []) {
      if (tag === '国内' || tag === '海外' || tag === '自营' || seen.has(tag)) continue;
      seen.add(tag);
      groups[regionOf(tag)].push(tag);
    }
  }
  for (const key of Object.keys(groups)) groups[key].sort((a, b) => a.localeCompare(b, 'zh'));
  return groups;
}

function renderCategories() {
  renderCategoryTabs();
  renderUsageChips();
}

function renderCategoryTabs() {
  categoryList.replaceChildren();
  const addTab = (category, count) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'category-chip' + (galleryState.selectedCategory === category ? ' active' : '');
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', String(galleryState.selectedCategory === category));
    button.setAttribute('aria-pressed', String(galleryState.selectedCategory === category));
    button.append(document.createTextNode(category ? category : '全部'));
    const countElement = document.createElement('small');
    countElement.textContent = String(count);
    button.append(countElement);
    button.addEventListener('click', () => {
      galleryState.selectedCategory = galleryState.selectedCategory === category ? '' : category;
      galleryState.page = 1;
      renderCatalogPage();
    });
    categoryList.append(button);
  };

  addTab('', SVGA_CATALOG_ITEMS.length);
  for (const [category, count] of categories()) addTab(category, count);
}

function renderUsageChips() {
  usageChips.replaceChildren();
  const addChip = (tag, count) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'usage-chip' + (galleryState.selectedUsage === tag ? ' active' : '');
    button.setAttribute('aria-pressed', String(galleryState.selectedUsage === tag));
    button.append(document.createTextNode(tag + ' '));
    const countElement = document.createElement('small');
    countElement.textContent = String(count);
    button.append(countElement);
    button.addEventListener('click', () => {
      galleryState.selectedUsage = galleryState.selectedUsage === tag ? '' : tag;
      galleryState.page = 1;
      renderCatalogPage();
    });
    usageChips.append(button);
  };

  const allButton = document.createElement('button');
  allButton.type = 'button';
  allButton.className = 'usage-chip' + (galleryState.selectedUsage === '' ? ' active' : '');
  allButton.textContent = '全部';
  allButton.setAttribute('aria-pressed', String(galleryState.selectedUsage === ''));
  allButton.addEventListener('click', () => {
    galleryState.selectedUsage = '';
    galleryState.page = 1;
    renderCatalogPage();
  });
  usageChips.append(allButton);

  for (const group of ['国内', '海外', '其他']) {
    const tags = usageGroups()[group];
    if (!tags.length) continue;
    const label = document.createElement('span');
    label.className = 'usage-group-label';
    label.textContent = group;
    usageChips.append(label);
    for (const tag of tags) {
      const count = SVGA_CATALOG_ITEMS.filter((item) => (item.tagList || []).includes(tag)).length;
      addChip(tag, count);
    }
  }
}

function renderCard(item, index) {
  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'catalog-card';
  card.setAttribute('aria-label', '打开 ' + item.name);
  const thumb = document.createElement('span');
  thumb.className = 'thumb';
  renderThumbnail(thumb, item);

  const body = document.createElement('span');
  body.className = 'card-body';
  const meta = document.createElement('span');
  meta.className = 'card-meta';
  const number = document.createElement('span');
  number.className = 'card-number';
  number.textContent = item.number || item.goodsId;
  const format = document.createElement('span');
  format.className = 'card-format';
  format.textContent = item.previewFormat || item.tag || '无预览';
  meta.append(number, format);

  const title = document.createElement('strong');
  title.className = 'card-title';
  title.textContent = item.name || '未命名商品';
  const category = document.createElement('span');
  category.className = 'card-category';
  category.textContent = [item.category, item.dimension].filter(Boolean).join(' · ') || '未分类';
  body.append(meta, title, category);
  card.append(thumb, body);
  card.addEventListener('click', () => openModal(index, card));
  return card;
}

function renderCatalogPage() {
  const { items, start, end, visible } = pageItems();
  gallery.replaceChildren();
  if (visible.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = '没有匹配的公开商品。';
    gallery.append(empty);
  } else {
    visible.forEach((item, index) => gallery.append(renderCard(item, start + index)));
  }
  const filterParts = [];
  if (galleryState.selectedCategory) filterParts.push(galleryState.selectedCategory);
  if (galleryState.selectedUsage) filterParts.push(galleryState.selectedUsage);
  filterSummary.textContent = filterParts.length ? filterParts.join(' · ') : '全部分类';
  rangeStatus.textContent = items.length
    ? String(start + 1).padStart(3, '0') + '-' + String(end).padStart(3, '0')
    : '0';
  totalStatus.textContent = '第 ' + galleryState.page + ' / ' + pageCount(items) + ' 页 · ' + items.length + ' 条';
  renderCategories();
  renderPager(pageCount(items));
}

function activeItem() {
  if (modalState.virtual) return modalState.virtual;
  if (modalState.index === null) return null;
  return filteredItems()[modalState.index] || null;
}

function renderCatalogModalMedia() {
  const item = activeItem();
  if (!item) return;
  if (item.previewSupport === 'image' && item.publicPreviewUrl) {
    renderImage(preview, item.publicPreviewUrl, item.name);
    return;
  }
  if (item.previewSupport === 'video' && item.publicPreviewUrl) {
    renderVideo(preview, item.publicPreviewUrl, item.name);
    return;
  }
  missingMedia(
    preview,
    item.previewFormat
      ? item.previewFormat.toUpperCase() + ' 不支持在浏览器中预览。'
      : '未提供可公开预览媒体。',
  );
}

function renderDetailCover(item) {
  if (!item.thumbnailUrl) {
    missingMedia(detailCoverFrame, '未提供公开封面。');
    return;
  }
  renderImage(detailCoverFrame, item.thumbnailUrl, item.name || '商品封面');
}

function renderDetailTags(item) {
  detailTags.replaceChildren();
  const tags = item.tagList.length ? item.tagList : [item.tag].filter(Boolean);
  for (const tag of tags) {
    const chip = document.createElement('span');
    chip.className = 'detail-tag';
    chip.textContent = tag;
    detailTags.append(chip);
  }
}

function renderDetailMetadata(item) {
  detailMetadata.replaceChildren();
  const entries = [
    ['编号', item.number || item.goodsId],
    ['分类', item.category || '未分类'],
    ['类型', item.dimension || '未标注'],
    ['预览格式', item.previewFormat ? item.previewFormat.toUpperCase() : '未提供'],
    ['用途', item.usage || '未提供'],
    ['采集时间', item.capturedAt || '未提供'],
  ];
  for (const [label, value] of entries) {
    const term = document.createElement('dt');
    term.textContent = label;
    const description = document.createElement('dd');
    description.textContent = value;
    detailMetadata.append(term, description);
  }
}

function renderRelatedItems(item) {
  relatedItems.replaceChildren();
  const related = item.relatedItems.slice(0, 8);
  if (!related.length) {
    const empty = document.createElement('p');
    empty.className = 'related-empty';
    empty.textContent = '未提供关联商品。';
    relatedItems.append(empty);
    return;
  }
  for (const relatedItem of related) {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'related-card';
    card.setAttribute('aria-label', '查看关联商品 ' + (relatedItem.name || relatedItem.goodsId));
    card.setAttribute('title', relatedItem.name || relatedItem.goodsId);
    const thumbnail = document.createElement('div');
    thumbnail.className = 'related-thumb';
    if (relatedItem.thumbnailUrl) {
      renderImage(thumbnail, relatedItem.thumbnailUrl, relatedItem.name || '关联商品');
    } else {
      missingMedia(thumbnail, '无封面');
    }
    const name = document.createElement('span');
    name.className = 'related-name';
    name.textContent = relatedItem.name || relatedItem.goodsId;
    card.append(thumbnail, name);
    card.addEventListener('click', () => openRelatedItem(relatedItem));
    relatedItems.append(card);
  }
}

function openRelatedItem(relatedItem) {
  const id = String(relatedItem.goodsId);
  let items = filteredItems();
  let index = items.findIndex((item) => String(item.goodsId) === id);
  if (index >= 0) {
    openModal(index, modalState.opener);
    return;
  }
  const fullIndex = SVGA_CATALOG_ITEMS.findIndex((item) => String(item.goodsId) === id);
  if (fullIndex >= 0) {
    galleryState.selectedCategory = '';
    galleryState.selectedUsage = '';
    galleryState.query = '';
    catalogSearch.value = '';
    galleryState.page = 1;
    renderCatalogPage();
    index = filteredItems().findIndex((item) => String(item.goodsId) === id);
    if (index >= 0) {
      openModal(index, modalState.opener);
      return;
    }
  }
  // 不在目录内：优先用递归抓取的关联详情（可播放动图 + 详情弹框同步）
  const relatedDetail = SVGA_RELATED_DETAILS[id];
  if (relatedDetail) {
    modalState.index = null;
    modalState.virtual = { ...relatedDetail, goodsId: id };
    updateModal();
    return;
  }
  // 无详情兜底：留在当前弹窗，左侧用缩略图预览，面板切到该关联商品
  modalState.index = null;
  modalState.virtual = {
    goodsId: id,
    name: relatedItem.name || '关联商品 NO.' + id,
    number: 'NO.' + id,
    category: '关联商品',
    tag: '',
    tagList: [],
    usage: '关联商品（未采集详情，点击“打开商品页”查看完整页面）',
    dimension: '',
    fileInfo: '',
    relatedItems: [],
    thumbnailUrl: relatedItem.thumbnailUrl || '',
    publicPreviewUrl: relatedItem.thumbnailUrl || '',
    previewFormat: 'image',
    previewSupport: relatedItem.thumbnailUrl ? 'image' : 'none',
    detailUrl: 'https://svga.wang/shop?goods_id=' + id,
    capturedAt: '',
  };
  updateModal();
}

function updateModal() {
  const item = activeItem();
  if (!item) return;
  const isVirtual = !!modalState.virtual;
  const items = filteredItems();
  const start = (galleryState.page - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, items.length);
  modalTitle.textContent = item.name || '未命名商品';
  detailNumber.textContent = item.number || item.goodsId;
  detailFileInfo.hidden = !item.fileInfo;
  detailFileInfo.textContent = item.fileInfo;
  openSource.href = item.detailUrl;
  replayButton.disabled = isVirtual || !['image', 'video'].includes(item.previewSupport);
  previousButton.disabled = isVirtual || modalState.index <= start;
  nextButton.disabled = isVirtual || modalState.index >= end - 1;
  renderDetailCover(item);
  renderDetailTags(item);
  renderDetailMetadata(item);
  renderRelatedItems(item);
  renderCatalogModalMedia();
}

function openModal(index, trigger) {
  modalState.index = index;
  modalState.opener = trigger;
  modalState.virtual = null;
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
  updateModal();
  closeButton.focus();
}

function closeModal() {
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.style.overflow = '';
  preview.replaceChildren(closeButton);
  const opener = modalState.opener;
  modalState.index = null;
  modalState.opener = null;
  modalState.virtual = null;
  opener?.focus();
}

function moveModal(offset) {
  if (modalState.virtual || modalState.index === null) return;
  const items = filteredItems();
  const start = (galleryState.page - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, items.length);
  const nextIndex = modalState.index + offset;
  if (nextIndex < start || nextIndex >= end) return;
  modalState.index = nextIndex;
  updateModal();
}

catalogSearch.addEventListener('input', () => {
  galleryState.query = catalogSearch.value;
  galleryState.page = 1;
  renderCatalogPage();
});
replayButton.addEventListener('click', renderCatalogModalMedia);
copyButton.addEventListener('click', async () => {
  const item = activeItem();
  if (!item) return;
  const source = item.publicPreviewUrl || item.detailUrl;
  const original = copyButton.textContent;
  try {
    await navigator.clipboard.writeText(source);
    copyButton.textContent = '已复制';
  } catch {
    copyButton.textContent = '复制失败';
  }
  window.setTimeout(() => { copyButton.textContent = original; }, 1400);
});
previousButton.addEventListener('click', () => moveModal(-1));
nextButton.addEventListener('click', () => moveModal(1));
closeButton.addEventListener('click', closeModal);
modal.addEventListener('click', (event) => {
  if (event.target === modal) closeModal();
});
document.addEventListener('keydown', (event) => {
  if (modal.hidden) return;
  if (event.key === 'Escape') closeModal();
  if (event.key === 'ArrowLeft') moveModal(-1);
  if (event.key === 'ArrowRight') moveModal(1);
});

renderCatalogPage();
  </script>
</body>
</html>
`;

await writeFile(outputFile, html);
console.log(
  `Generated ${fileURLToPath(outputFile)} with ${catalogItems.length} public catalog items.`,
);
