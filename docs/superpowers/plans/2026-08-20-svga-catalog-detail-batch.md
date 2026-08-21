# SVGA Catalog Detail Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Batch-normalize approved public detail metadata for every collected catalog item and render it in a reference-style static product detail dialog.

**Architecture:** `collect.py` continues to discover anonymous list items, then calls each record's allowlisted detail endpoint and passes only public response objects to `normalize.py`. The normalizer projects an explicit detail whitelist into the embedded catalog JSON. The HTML generator consumes that static data and renders a two-column dialog without issuing browser requests to `sourceApiUrl`.

**Tech Stack:** Python 3.12 standard-library tests, Playwright for manual anonymous collection, Node.js ESM static HTML generator, browser-native HTML/CSS/JS.

---

### Task 1: Expand The Normalized Detail Schema

**Files:**
- Modify: `svga_public_catalog/normalize.py`
- Modify: `svga_public_catalog/tests/test_normalize.py`
- Modify: `svga_public_catalog/fixtures/public-detail.json`

- [x] **Step 1: Write failing normalization assertions**

Add a test that supplies a detail response with:

```python
"goods_advword": "文件281kb内存3.3m",
"tagname_list": ["斋月开斋", "自营"],
"relatedGoods": [
    {
        "goods_id": 12232,
        "goods_name": "翠金圣宴主页装扮",
        "goods_image": "https://media.example.test/related.png",
    }
],
"goods_promotion_price": "200.00",
"goods_marketprice": "200.00",
"goods_price": "**",
```

Require output fields:

```python
assert row["fileInfo"] == "文件281kb内存3.3m"
assert row["tagList"] == ["斋月开斋", "自营"]
assert row["relatedItems"] == [{
    "goodsId": "12232",
    "name": "翠金圣宴主页装扮",
    "thumbnailUrl": "https://media.example.test/related.png",
}]
assert "goods_price" not in row
assert "goods_promotion_price" not in row
assert "goods_marketprice" not in row
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_normalize
```

Expected: FAIL because `fileInfo`, `tagList`, and `relatedItems` are not yet normalized.

- [x] **Step 3: Implement explicit detail projections**

In `svga_public_catalog/normalize.py`, add:

```python
def _tag_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _related_items(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        goods_id = _as_text(item.get("goods_id"))
        if not goods_id or goods_id in seen:
            continue
        seen.add(goods_id)
        rows.append({
            "goodsId": goods_id,
            "name": _as_text(item.get("goods_name")),
            "thumbnailUrl": _thumbnail(item.get("goods_image")),
        })
    return rows
```

Extend `_record()` with only:

```python
"fileInfo": _as_text(_first_value(list_item, detail_item, "goods_advword")),
"tagList": _tag_list(_first_value(list_item, detail_item, "tagname_list")),
"relatedItems": _related_items(detail_item.get("relatedGoods")),
```

Do not add price, store, VAT, delivery, ownership, or raw detail-response fields.

- [x] **Step 4: Run the focused normalization tests**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_normalize
```

Expected: PASS.

- [x] **Step 5: Record source-control status**

Run:

```bash
git status --short --branch
```

Expected: `fatal: not a git repository`; do not create a Git repository or attempt a commit.

### Task 2: Make Full Detail Enrichment The Collector Default

**Files:**
- Modify: `svga_public_catalog/collect.py`
- Modify: `svga_public_catalog/tests/test_collect.py`

- [x] **Step 1: Write failing collection tests**

Add a test with two list items and `detail_limit=-1`. Its injected
`fetch_detail()` must record both IDs, and assert:

```python
self.assertEqual(detail_calls, ["1", "2"])
self.assertEqual(result.details_enriched, 2)
```

Add an assertion that a failed detail request does not remove the list item:

```python
self.assertEqual(result.products_accepted, 2)
self.assertEqual(result.details_enriched, 1)
```

- [x] **Step 2: Run the focused collector test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_collect
```

Expected: FAIL because negative detail limits are rejected or do not represent unbounded enrichment.

- [x] **Step 3: Implement unbounded detail-limit semantics**

In `collect_catalog()`, accept `detail_limit=-1` as unbounded:

```python
if max_pages < 1 or page_size < 1 or detail_limit < -1:
    raise ValueError("max_pages/page_size must be positive and detail_limit must be -1 or non-negative")
```

Use:

```python
should_enrich = detail_limit != 0
has_reached_limit = detail_limit > 0 and len(details) >= detail_limit
```

Then keep detail requests restricted to de-duplicated IDs present in public list
payloads. Set the CLI default:

```python
parser.add_argument("--detail-limit", type=int, default=-1)
```

For an individual failed detail response, continue collection and retain the
list record. Do not try a second endpoint, alternate domain, credentials,
headers, proxy, or media URL.

- [x] **Step 4: Run the focused collector tests**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_collect
```

Expected: PASS.

- [x] **Step 5: Run all Python tests**

Run:

```bash
.venv/bin/python -m unittest discover -s svga_public_catalog/tests -t .
```

Expected: PASS with all normalizer, collector, and media-policy tests.

### Task 3: Validate The Embedded Detail Contract

**Files:**
- Modify: `scripts/generate-catalog-gallery.mjs`
- Modify: `tests/catalog-gallery.test.mjs`

- [x] **Step 1: Write failing static-generator tests**

Require each record to have:

```javascript
['fileInfo', 'tagList', 'relatedItems']
```

Require the emitted page source to include:

```javascript
function renderDetailTags(
function renderRelatedItems(
class="detail-dialog"
```

Reject accidental price-field source strings:

```javascript
assert.doesNotMatch(html, /goods_promotion_price|goods_marketprice|goods_price/);
```

- [x] **Step 2: Run Node tests to verify they fail**

Run:

```bash
node --test tests/catalog-gallery.test.mjs tests/vercel-config.test.mjs
```

Expected: FAIL because the current generator has no detail tags, related-item renderer, or detail-dialog markup.

- [x] **Step 3: Validate the detail fields in the generator**

Extend `requiredFields`:

```javascript
'fileInfo',
'tagList',
'relatedItems',
```

Validate:

```javascript
if (!Array.isArray(item.tagList) || !Array.isArray(item.relatedItems)) {
  throw new Error(`invalid detail arrays at index ${index}`);
}
```

Ensure every related item is a plain object containing string `goodsId`,
`name`, and `thumbnailUrl`. Do not accept or render raw API objects.

- [x] **Step 4: Run the generator and Node tests**

Run:

```bash
node scripts/generate-catalog-gallery.mjs
node --test tests/catalog-gallery.test.mjs tests/vercel-config.test.mjs
```

Expected: The generator succeeds and all Node tests PASS.

### Task 4: Replace The Modal With The Reference-Style Detail Layout

**Files:**
- Modify: `scripts/generate-catalog-gallery.mjs`
- Modify: `tests/catalog-gallery.test.mjs`

- [x] **Step 1: Add failing behavior checks**

Add source assertions for:

```javascript
function renderDetailTags(
function renderRelatedItems(
function renderDetailCover(
```

Require media fallback copy and confirm no referrer override is emitted:

```javascript
assert.match(html, /该媒体无法在浏览器中预览。/);
assert.doesNotMatch(html, /referrerpolicy|no-referrer|fetch\(/i);
```

- [x] **Step 2: Run the Node test to verify it fails**

Run:

```bash
node --test tests/catalog-gallery.test.mjs
```

Expected: FAIL because the old modal has only title, metadata text, and actions.

- [x] **Step 3: Implement the detail layout**

Replace the modal panel markup with a dialog containing:

```html
<section class="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <div id="preview" class="detail-preview"></div>
  <aside class="detail-panel">
    <div class="detail-heading">
      <img id="detail-cover" class="detail-cover" alt="">
      <div>
        <h2 id="modal-title"></h2>
        <p id="modal-number"></p>
        <div id="detail-tags"></div>
      </div>
    </div>
    <dl id="detail-metadata"></dl>
    <p id="detail-file-info"></p>
    <section><h3>关联商品</h3><div id="related-items"></div></section>
  </aside>
</section>
```

Use CSS grid for desktop:

```css
.detail-dialog { grid-template-columns: minmax(360px, 1.1fr) minmax(340px, 0.9fr); }
.detail-preview { background: #0b1c34; min-height: 600px; }
.detail-panel { background: #112745; color: #f5f8fc; overflow: auto; }
```

For widths at or below 820px, use one column, keep a bounded preview height,
and allow the right panel to scroll. Create tag chips from `tagList`, a
metadata list from number/category/dimension/usage/capture time, a file-info
strip from `fileInfo`, and up to eight related cards from `relatedItems`.

When cover or preview emits an error, replace only its media container with
the existing unavailable state. Do not append a `referrerpolicy` attribute,
proxy media, use a fetch request, or modify request headers.

- [x] **Step 4: Run Node tests**

Run:

```bash
node scripts/generate-catalog-gallery.mjs
node --test tests/catalog-gallery.test.mjs tests/vercel-config.test.mjs
```

Expected: PASS.

### Task 5: Batch Generate And Verify Public Artifacts

**Files:**
- Modify: `output/svga-public-catalog.json`
- Modify: `output/index.html`

- [x] **Step 1: Run full anonymous collection**

Run:

```bash
.venv/bin/python -m svga_public_catalog.collect --max-pages 10 --page-size 20 --detail-limit -1
```

Expected: a summary with the accepted product count, `details enriched`, and
an `output/svga-public-catalog.json` file. If upstream network access fails,
preserve the existing output and report the exact failure; do not use an
alternate access method.

- [x] **Step 2: Inspect the normalized output without exposing raw detail data**

Run:

```bash
jq '[.[] | {goodsId, fileInfo, tagList, relatedCount: (.relatedItems | length)}] | .[0:3]' output/svga-public-catalog.json
jq '.. | objects | keys[]?' output/svga-public-catalog.json | rg 'goods_price|goods_promotion_price|goods_marketprice|relatedGoods' && exit 1 || true
```

Expected: sampled records contain only normalized display fields; the forbidden
raw price and related-payload keys produce no matches.

- [x] **Step 3: Regenerate page and run full checks**

Run:

```bash
node scripts/generate-catalog-gallery.mjs
.venv/bin/python -m unittest discover -s svga_public_catalog/tests -t .
node --test tests/catalog-gallery.test.mjs tests/vercel-config.test.mjs
```

Expected: generator succeeds; all Python and Node tests PASS.

- [x] **Step 4: Perform local browser verification**

Run:

```bash
python3 -m http.server 4173 --directory output
```

Open `http://127.0.0.1:4173`, select a card, and verify:

```text
detail layout includes cover, title, number, tags, file info, metadata, and related items
cover and MP4 failures show a local unavailable state
no price is visible
search, category filtering, pagination, Escape-to-close, and previous/next detail navigation still work
```

- [x] **Step 5: Record source-control status**

Run:

```bash
git status --short --branch
```

Expected: `fatal: not a git repository`; do not create a repository or claim a commit.
