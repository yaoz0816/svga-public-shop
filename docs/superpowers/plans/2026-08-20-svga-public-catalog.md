# SVGA.WANG Public Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build an independent desktop project that anonymously collects
public SVGA.WANG product metadata and renders it as a standalone static catalog
gallery.

**Architecture:** `svga_public_catalog/` owns the strict public-response
normalizer and a fresh, non-persistent Playwright collection context. It writes
only a filtered `output/svga-public-catalog.json`. A separate Node generator
embeds that data into this project's own `output/index.html`; no file beneath
`/Users/mac345/Desktop/discord-shop` is imported, modified, or deployed.

**Tech Stack:** Python 3.12 standard library, existing Playwright Python
package, Node.js built-ins, `node:test`, static HTML/CSS/browser JavaScript.

---

## File Structure

```text
svga-public-catalog/
  svga_public_catalog/
    __init__.py
    schema.py
    media.py
    normalize.py
    collect.py
    fixtures/
    tests/
  scripts/
    generate-catalog-gallery.mjs
  tests/
    catalog-gallery.test.mjs
    vercel-config.test.mjs
  output/
    svga-public-catalog.json
    index.html
  .vercelignore
  vercel.json
```

### Task 1: Test The Media Policy

**Files:**
- Create: `svga_public_catalog/schema.py`
- Create: `svga_public_catalog/media.py`
- Create: `svga_public_catalog/tests/__init__.py`
- Create: `svga_public_catalog/tests/test_media.py`

- [ ] **Step 1: Write the failing test.**

```python
from unittest import TestCase

from svga_public_catalog.media import classify_public_preview


class PublicPreviewTests(TestCase):
    def test_allows_plain_public_image_and_video_urls(self):
        self.assertEqual(
            classify_public_preview("https://media.example.test/x.webp"),
            ("https://media.example.test/x.webp", "webp", "image"),
        )
        self.assertEqual(
            classify_public_preview("https://media.example.test/x.mp4"),
            ("https://media.example.test/x.mp4", "mp4", "video"),
        )

    def test_labels_non_browser_preview_without_loading_it(self):
        self.assertEqual(
            classify_public_preview("https://media.example.test/x.svga"),
            ("https://media.example.test/x.svga", "svga", "unsupported"),
        )

    def test_rejects_access_control_and_download_urls(self):
        for url in (
            "http://media.example.test/x.mp4",
            "https://media.example.test/x.mp4?token=abc",
            "https://media.example.test/x.mp4?Expires=1",
            "https://media.example.test/download/x.mp4",
            "https://media.example.test/original.zip",
        ):
            self.assertEqual(classify_public_preview(url), ("", "", "unavailable"))
```

- [ ] **Step 2: Run the test and observe an import failure.**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_media -v
```

Expected: FAIL because `svga_public_catalog.media` does not exist.

- [ ] **Step 3: Implement the minimal pure classifier.**

```python
# schema.py
DENIED_QUERY_KEYS = frozenset(
    {"token", "signature", "expires", "expiry", "auth", "auth_key", "key"}
)
DENIED_PATH_MARKERS = frozenset(
    {"login", "member", "cart", "order", "payment", "download", "token"}
)
IMAGE_FORMATS = frozenset({"gif", "webp", "png", "jpg", "jpeg"})
VIDEO_FORMATS = frozenset({"mp4", "webm"})
UNSUPPORTED_FORMATS = frozenset({"svga", "vap", "pag", "json", "lottie", "mov"})
```

```python
# media.py
from urllib.parse import parse_qsl, urlparse

from .schema import (
    DENIED_PATH_MARKERS,
    DENIED_QUERY_KEYS,
    IMAGE_FORMATS,
    UNSUPPORTED_FORMATS,
    VIDEO_FORMATS,
)


def classify_public_preview(value: object) -> tuple[str, str, str]:
    if not isinstance(value, str) or not value:
        return "", "", "unavailable"
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return "", "", "unavailable"
    if any(marker in parsed.path.lower() for marker in DENIED_PATH_MARKERS):
        return "", "", "unavailable"
    if any(key.lower() in DENIED_QUERY_KEYS for key, _ in parse_qsl(parsed.query)):
        return "", "", "unavailable"
    extension = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""
    if extension in IMAGE_FORMATS:
        return value, extension, "image"
    if extension in VIDEO_FORMATS:
        return value, extension, "video"
    if extension in UNSUPPORTED_FORMATS:
        return value, extension, "unsupported"
    return "", "", "unavailable"
```

- [ ] **Step 4: Re-run the test.**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_media -v
```

Expected: PASS with three tests. The test must make no network request.

### Task 2: Test And Implement Normalization

**Files:**
- Create: `svga_public_catalog/normalize.py`
- Create: `svga_public_catalog/tests/test_normalize.py`
- Read: `svga_public_catalog/fixtures/public-list.json`
- Read: `svga_public_catalog/fixtures/public-detail.json`

- [ ] **Step 1: Write failing fixture-driven tests.**

```python
import json
from pathlib import Path
from unittest import TestCase

from svga_public_catalog.normalize import normalize_catalog

FIXTURES = Path(__file__).parents[1] / "fixtures"


class NormalizeCatalogTests(TestCase):
    def test_keeps_only_the_approved_16_fields(self):
        listing = json.loads((FIXTURES / "public-list.json").read_text("utf-8"))
        details = json.loads((FIXTURES / "public-detail.json").read_text("utf-8"))
        rows = normalize_catalog([listing], {"10001": details}, "2026-08-20T00:00:00Z")

        self.assertEqual([row["goodsId"] for row in rows], ["10001", "10002"])
        self.assertEqual(rows[0]["publicPreviewUrl"], "https://media.example.test/preview.mp4")
        self.assertEqual(rows[1]["publicPreviewUrl"], "")
        self.assertEqual(rows[1]["previewSupport"], "unavailable")
        self.assertEqual(
            set(rows[0]),
            {
                "source", "goodsId", "name", "number", "category", "tag",
                "usage", "dimension", "thumbnailUrl", "publicPreviewUrl",
                "previewFormat", "previewSupport", "detailUrl", "sourceApiUrl",
                "priceVisibility", "capturedAt",
            },
        )

    def test_deduplicates_goods_id_and_sorts_stably(self):
        payload = {
            "result": {
                "recommend_list": [
                    {"goods_id": 2, "goods_name": "B", "goods_category": "B"},
                    {"goods_id": 1, "goods_name": "A", "goods_category": "A"},
                    {"goods_id": 2, "goods_name": "Duplicate", "goods_category": "B"},
                ]
            }
        }
        rows = normalize_catalog([payload], {}, "2026-08-20T00:00:00Z")
        self.assertEqual([row["goodsId"] for row in rows], ["1", "2"])
```

- [ ] **Step 2: Run the test and observe an import failure.**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_normalize -v
```

Expected: FAIL because `svga_public_catalog.normalize` does not exist.

- [ ] **Step 3: Implement a whitelisted mapping.**

```python
def extract_list_items(payload: dict) -> list[dict]:
    result = payload.get("result")
    items = result.get("recommend_list") if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise ValueError("missing result.recommend_list")
    return [item for item in items if isinstance(item, dict)]


def normalize_catalog(
    list_payloads: list[dict],
    detail_payloads: dict[str, dict],
    captured_at: str,
) -> list[dict]:
    ...


def write_catalog(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", "utf-8")
```

Map only the observed public fields: `goods_id`, `goods_name`,
`goods_category`, `goods_image`, `goods_video_url`, `g_sub_title`, `g_2d`,
`duration`, and `tagname_list`. Use `classify_public_preview()` and construct
the approved 16-key schema. Drop price fields even when the live response
contains them. For duplicate IDs retain the first valid record, then sort by
`category`, `number`, and `goodsId`.

- [ ] **Step 4: Re-run both Python test modules.**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_media svga_public_catalog.tests.test_normalize -v
```

Expected: PASS. No test contacts the public storefront.

### Task 3: Test And Implement Anonymous Collection

**Files:**
- Create: `svga_public_catalog/collect.py`
- Create: `svga_public_catalog/tests/test_collect.py`

- [ ] **Step 1: Write failing orchestration tests with mocked transport.**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from svga_public_catalog.collect import CollectionResult, collect_catalog


class CollectCatalogTests(TestCase):
    @patch("svga_public_catalog.collect.fetch_public_detail")
    @patch("svga_public_catalog.collect.fetch_public_page")
    @patch("svga_public_catalog.collect.fetch_categories")
    def test_honors_page_limit_and_writes_output(self, categories, page, detail):
        categories.return_value = [{"gc_id": 9, "gc_name": "Fixture"}]
        page.side_effect = [
            {"result": {"recommend_list": [{"goods_id": 1, "goods_name": "A"}], "recommend_page_count": 2}},
            {"result": {"recommend_list": [{"goods_id": 2, "goods_name": "B"}], "recommend_page_count": 2}},
        ]
        detail.return_value = {}
        with TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            result = collect_catalog(2, 20, 0, output, sleep=lambda _: None)
            self.assertTrue(output.exists())
        self.assertEqual(result.pages_requested, 2)
        self.assertEqual(result.products_accepted, 2)

    @patch("svga_public_catalog.collect.fetch_public_page")
    @patch("svga_public_catalog.collect.fetch_categories")
    def test_records_403_as_terminal_without_an_alternate_path(self, categories, page):
        categories.return_value = [{"gc_id": 9, "gc_name": "Blocked"}]
        page.side_effect = PermissionError("HTTP 403")
        result = collect_catalog(1, 20, 0, Path("/tmp/no-output.json"), sleep=lambda _: None)
        self.assertEqual(result.products_accepted, 0)
        self.assertEqual(result.terminal_errors, {"9": "HTTP 403"})
```

- [ ] **Step 2: Run the collector test and observe an import failure.**

Run:

```bash
.venv/bin/python -m unittest svga_public_catalog.tests.test_collect -v
```

Expected: FAIL because `svga_public_catalog.collect` does not exist.

- [ ] **Step 3: Implement the fresh-context public transport.**

Expose:

```python
@dataclass(frozen=True)
class CollectionResult:
    categories_visited: int
    pages_requested: int
    products_accepted: int
    products_deduplicated: int
    details_enriched: int
    preview_urls_accepted: int
    preview_urls_rejected: int
    terminal_errors: dict[str, str]
    output_path: Path | None


def fetch_categories() -> list[dict]: ...
def fetch_public_page(category_id: str, page: int, page_size: int) -> dict: ...
def fetch_public_detail(goods_id: str) -> dict: ...
def collect_catalog(
    max_pages: int,
    page_size: int,
    detail_limit: int,
    output_path: Path,
    sleep: Callable[[float], None] = time.sleep,
) -> CollectionResult: ...
```

On initial page load, capture the anonymous `getCateList` body, one
`getMoreList` body, and that list request's form data in memory. Reuse that
observed form only by replacing `gc_id` and `page`; do not write form values to
disk. Use a fresh `chromium.launch()` and `browser.new_context()`, never a
profile or `launch_persistent_context`. Public detail requests use only
previously observed product IDs and only when `detail_limit > 0`.

Wait 1.2 seconds plus 0.25–0.75 second jitter before calls. Retry timeouts,
connection errors, HTTP 429, and HTTP 5xx twice after 2 then 4 seconds. Treat
HTTP 401/403, challenge text, malformed JSON, and missing
`result.recommend_list` as terminal per-category errors. Do not use login,
cart, order, payment, download, or alternative protected endpoints.

- [ ] **Step 4: Add the bounded CLI and summary.**

```python
parser.add_argument("--max-pages", type=int, default=10)
parser.add_argument("--page-size", type=int, default=20)
parser.add_argument("--detail-limit", type=int, default=0)
parser.add_argument(
    "--output",
    type=Path,
    default=Path(__file__).parents[1] / "output" / "svga-public-catalog.json",
)
```

Print only aggregate counters and terminal category identifiers. Return 1 when
there is no valid public list payload; otherwise return 0.

- [ ] **Step 5: Run the full Python suite and isolation scan.**

Run:

```bash
.venv/bin/python -m unittest discover -s svga_public_catalog/tests -v
rg -n 'discord-shop|discord_shop|launch_persistent_context|storage_state' \
  svga_public_catalog --glob '!fixtures/**' --glob '!tests/**'
```

Expected: all tests pass and the scan has no output.

### Task 4: Test And Generate The Standalone Catalog Page

**Files:**
- Create: `output/svga-public-catalog.json`
- Create: `scripts/generate-catalog-gallery.mjs`
- Create: `tests/catalog-gallery.test.mjs`
- Generate: `output/index.html`

- [ ] **Step 1: Add a normalized development dataset and failing static test.**

```js
const embedded = html.match(
  /const SVGA_CATALOG_ITEMS = (\[[\s\S]*?\]);\n\nconst PAGE_SIZE/,
);

assert.ok(embedded, 'the page embeds normalized records');
assert.deepEqual(JSON.parse(embedded[1]), source);
assert.match(html, /id="catalog-search"/);
assert.match(html, /id="category-list"/);
assert.match(html, /function renderCatalogPage\(/);
assert.match(html, /function renderCatalogModalMedia\(/);
assert.match(html, /不支持在浏览器中预览/);
```

- [ ] **Step 2: Run the Node test and observe failure.**

Run:

```bash
node --test tests/catalog-gallery.test.mjs
```

Expected: FAIL because the generator and `output/index.html` do not exist.

- [ ] **Step 3: Implement the independent generator.**

`generate-catalog-gallery.mjs` reads
`output/svga-public-catalog.json`, validates every required field, and embeds
`SVGA_CATALOG_ITEMS` into a self-contained `output/index.html`. The page owns:

- keyword search over name, number, category, tag, usage, and dimension;
- category chips, 50-item pagination, empty state, and responsive cards;
- a modal with metadata, product source link, copy URL, replay, and previous/
  next controls scoped to the current filtered page;
- `<img>` previews for `image`, `<video>` previews for `video`, and an explicit
  unsupported/unavailable message for all other formats.

The only external modal link is `detailUrl`. Never expose `sourceApiUrl` in
the UI or create a player/converter for SVGA, VAP, PAG, Lottie, MOV, or source
package formats.

- [ ] **Step 4: Generate the page and run its test.**

Run:

```bash
node scripts/generate-catalog-gallery.mjs
node --test tests/catalog-gallery.test.mjs
```

Expected: PASS.

### Task 5: Isolate Deployment And Run A Bounded Public Collection

**Files:**
- Create: `vercel.json`
- Create: `.vercelignore`
- Create: `tests/vercel-config.test.mjs`
- Generate: `output/svga-public-catalog.json`
- Generate: `output/index.html`

- [ ] **Step 1: Add failing deployment configuration tests.**

```js
assert.equal(config.outputDirectory, 'output');
assert.equal(config.cleanUrls, true);
assert.deepEqual(ignoredPaths, [
  '.venv',
  'docs',
  'scripts',
  'tests',
  'svga_public_catalog/',
  'output/*.json',
]);
```

- [ ] **Step 2: Run the test and observe failure.**

Run:

```bash
node --test tests/vercel-config.test.mjs
```

Expected: FAIL because deployment files do not exist.

- [ ] **Step 3: Add standalone Vercel configuration.**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "outputDirectory": "output",
  "cleanUrls": true
}
```

```text
.venv
docs
scripts
tests
svga_public_catalog/
output/*.json
```

- [ ] **Step 4: Verify deployment configuration.**

Run:

```bash
node --test tests/vercel-config.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Run one anonymous, bounded collection.**

Run:

```bash
.venv/bin/python -m svga_public_catalog.collect --max-pages 1 --page-size 20 --detail-limit 0
```

Expected: a non-empty normalized output or a clear non-zero access/schema
error. Never retry through login, cookies, or protected endpoints.

- [ ] **Step 6: Validate output safety, regenerate, and run all tests.**

Run:

```bash
node - <<'NODE'
const fs = require('node:fs');
const rows = JSON.parse(fs.readFileSync('output/svga-public-catalog.json', 'utf8'));
const forbidden = /cookie|authorization|bearer|password|order|payment|download|token=|signature|expires=/i;
if (!Array.isArray(rows) || rows.length === 0) throw new Error('catalog is empty');
for (const row of rows) {
  const inspection = { ...row };
  delete inspection.priceVisibility;
  if (row.priceVisibility !== 'login-gated-or-masked') throw new Error('unexpected price visibility');
  if (forbidden.test(JSON.stringify(inspection))) throw new Error(`forbidden row ${row.goodsId}`);
}
console.log(`validated ${rows.length} rows`);
NODE
node scripts/generate-catalog-gallery.mjs
node --test tests/*.test.mjs
.venv/bin/python -m unittest discover -s svga_public_catalog/tests -v
```

Expected: the dataset passes the policy scan, the standalone page is generated,
and all tests pass.

- [ ] **Step 7: Manual browser acceptance.**

Run:

```bash
python3 -m http.server 4173 --directory output
```

Verify search, category filter, pagination, modal source link, image/video
preview, replay, and unsupported format fallback. Confirm no request targets
login, cart, order, payment, or download endpoints.

## Plan Self-Review

- The project is independent: all paths are under
  `/Users/mac345/Desktop/svga-public-catalog/`.
- Automated tests use only redacted fixtures and mocks.
- The collector persists only a normalized 16-key public schema and excludes
  price, member, order, download, signed URL, and credential data.
- Browser support degrades safely for formats that cannot be rendered.
