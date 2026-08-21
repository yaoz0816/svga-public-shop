# SVGA.WANG Public Catalog Design

## Goal

Add an isolated catalog collection flow for publicly accessible product
metadata and publicly playable previews from `svga.wang`. The result feeds a
standalone static catalog gallery in this directory, including batch-normalized
detail metadata for every accepted public list item.

The collector is for catalog inspection only. It must not authenticate, add to
cart, create orders, reveal masked prices, obtain original packages, or
circumvent access controls.

## Scope And Boundaries

### In Scope

- Anonymous collection of product identifiers, titles, category labels, item
  numbers, visible type and usage labels, thumbnail URLs, and publicly
  accessible preview URLs.
- Iteration through the public category and product-list APIs observed while
  browsing the storefront.
- Anonymous product-detail enrichment for every accepted product ID found in
  the public list response. The per-record `sourceApiUrl` identifies the
  corresponding public detail endpoint used during collection.
- A normalized local catalog file embedded into this project's
  `output/index.html`.
- A standalone, category-filtered gallery view for the normalized SVGA.WANG
  data.

### Explicitly Out Of Scope

- Any source, output, script, test, deployment configuration, or browser
  profile under `/Users/mac345/Desktop/discord-shop`.
- Login, QR-code login, cookies, local storage, headers containing credentials,
  member-only prices, cart, checkout, payment, orders, or downloads.
- Signed, tokenized, expiring, anti-hotlink, or otherwise access-controlled
  media URLs.
- Downloading SVGA, VAP, PAG, AE, ZIP, or other source/original asset files.
- Any attempt to bypass CAPTCHA, anti-bot controls, rate limits, or access
  restrictions.
- Claims that catalog access grants commercial reuse rights.

## Directory And File Structure

Create a dedicated top-level `svga_public_catalog/` directory. It is the sole
owner of SVGA.WANG collection logic.

```text
svga_public_catalog/
  __init__.py
  collect.py                 # Anonymous Playwright collection CLI
  normalize.py               # API payload validation, filtering, normalization
  media.py                   # Public preview URL classification and rejection
  schema.py                  # TypedDict definitions and field constants
  fixtures/
    public-list.json         # Sanitized captured public-list fixture
    public-detail.json       # Sanitized captured public-detail fixture
  tests/
    test_normalize.py        # stdlib unittest coverage for normalization
    test_media.py            # stdlib unittest coverage for media policy
scripts/
  generate-catalog-gallery.mjs # Standalone HTML generator
tests/
  catalog-gallery.test.mjs   # Node static artifact validation
vercel.json                  # Optional standalone static deployment config
.vercelignore                # Excludes collector source and JSON inputs
```

Generated artifacts remain under this project's `output/` directory:

```text
output/
  svga-public-catalog.json
  index.html
```

`svga_public_catalog/` and the JSON artifact are local build inputs. When this
directory is deployed independently, its Vercel configuration publishes only
generated HTML from `output/`; raw API payloads are never written as build
artifacts and no JSON source dataset is deployed.

## Collection Architecture

### Browser Context

`collect.py` starts a fresh, non-persistent Playwright Chromium context:

- no `user_data_dir`;
- no cookies imported or saved;
- no request interception that changes site behavior;
- no authentication or login navigation;
- context closed on every success or failure path.

The storefront page is used only to observe and invoke anonymous catalog
requests. The collector has no dependency on another local project or browser
profile.

### Endpoint Allowlist

The initial allowlist is limited to public catalog discovery endpoints observed
from an anonymous storefront session:

```text
GET  /mobile/index/getStoreList
GET  /mobile/index/getCateList
POST /mobile/index/getMoreList
POST /mobile/index/getGoodsDetail?goods_id=<public-list-id>
```

`getGoodsDetail` is required batch enrichment for IDs already obtained from
`getMoreList`, respects the same throttling policy, and has the same data
filter. A response that requires login, returns a non-success API status, or
exposes no approved public fields is skipped rather than retried through a
different access path.

The following endpoint classes are denylisted even if their responses happen
to appear in the browser network log:

```text
login, user, member, cart, order, payment, download, test-download,
coupon, address, token, authorization
```

Only URL, HTTP status, response body, and a fixed collector version are used
for validation in memory. Request headers, response headers, cookies, and
storage values are neither persisted nor included in output.

### Pagination, Retry, And Stop Rules

The list collector enumerates the public categories, then pages each category
through `getMoreList`.

- CLI defaults: `--max-pages 10`, `--page-size 20`, full detail enrichment,
  and `--headless`.
- `--max-pages` is a hard per-category upper bound; callers must increase it
  deliberately for a larger run.
- Every request waits 1.2 seconds plus a random 0.25 to 0.75 second jitter.
- A transient timeout, connection error, or HTTP 429/5xx receives at most two
  retries with 2-second then 4-second backoff.
- HTTP 401/403, CAPTCHA/challenge text, schema failures, and API business
  failures are terminal for that request. The run records a non-sensitive
  error summary and continues with unrelated categories.
- A category stops when the response has no items, the API reports no next
  page, or all items on a page were previously seen.
- Global deduplication is keyed by stable `goodsId`; records without one are
  rejected.

## Data Policy And Normalized Schema

`normalize.py` accepts only known public response shapes. Unknown fields are
dropped by default. It produces a JSON array sorted by `category`, `number`,
then `goodsId`.

```json
{
  "source": "svga.wang",
  "goodsId": "12345",
  "name": "Product name",
  "number": "NO.123",
  "category": "Gift category",
  "tag": "SVGA",
  "usage": "Live gift",
  "dimension": "2D",
  "thumbnailUrl": "https://public-cdn.example/thumbnail.webp",
  "publicPreviewUrl": "https://public-cdn.example/preview.mp4",
  "previewFormat": "mp4",
  "previewSupport": "video",
  "detailUrl": "https://svga.wang/shop?goods_id=12345",
  "sourceApiUrl": "https://gapi.qianmusoft.com/mobile/index/getGoodsDetail?goods_id=12345",
  "priceVisibility": "login-gated-or-masked",
  "capturedAt": "2026-08-20T00:00:00Z"
}
```

`priceVisibility` is a state label only. The collector stores no price amount,
membership entitlement, download entitlement, or order-related value.

For the reference-style detail view, the normalized record additionally
contains these approved display fields:

```json
{
  "fileInfo": "文件281kb内存3.3m",
  "tagList": ["斋月开斋", "自营"],
  "relatedItems": [
    {
      "goodsId": "12232",
      "name": "翠金圣宴主页装扮",
      "thumbnailUrl": "https://public-cdn.example/related.png"
    }
  ]
}
```

`fileInfo` comes from `goods_advword`; `tagList` comes from
`tagname_list`; `relatedItems` is a one-level projection of `relatedGoods`.
Only each related product's identifier, display name, and approved image URL
are retained. The collector does not fetch related-product details recursively
and does not persist `goods_promotion_price`, `goods_marketprice`,
`goods_price`, VAT, store, delivery, or ownership fields.

`media.py` accepts a preview candidate only when all of the following hold:

1. It is an HTTPS URL found in an approved public metadata field.
2. It has no query parameter or pathname marker associated with authorization,
   signature, token, expiry, or temporary download access.
3. Its extension or anonymous response `Content-Type` maps to an approved
   preview format.
4. It is not identified as a source-package or download URL.

Rejected candidates leave `publicPreviewUrl` empty and set
`previewSupport` to `unavailable`; the product record is still retained.

## Standalone Gallery And Detail View

`scripts/generate-catalog-gallery.mjs` reads
`output/svga-public-catalog.json`, validates the normalized schema, and embeds
records into `output/index.html` as `SVGA_CATALOG_ITEMS`.

The single-page gallery has:

- keyword search over name, number, category, tag, usage, and dimension;
- category chips based on normalized `category`;
- deterministic pagination, initially 50 records per page;
- card fields: thumbnail, number, product name, category, tag, and public
  preview support state;
- a reference-style detail dialog: a dark-blue, tall device-style preview area
  on the left; a square cover, title, number/type/tag chips, category,
  description, file-information strip, capture date, and related-item grid on
  the right;
- the directly supplied public preview URL only when the media policy approved
  it;
- a media-unavailable state that retains the product metadata and source
  product link when the browser cannot load a cover or preview.

The page does not make browser requests to `sourceApiUrl`. Detail data is
batch-normalized before the HTML is generated, avoiding CORS and runtime
dependency on the upstream API.

The tab never tries to work around a media format that the browser cannot
render:

| Preview support | Rendering rule |
| --- | --- |
| `image` (`gif`, `webp`, `png`, `jpeg`) | `<img>` with existing broken-media fallback |
| `video` (`mp4`, browser-supported `webm`) | muted looping `<video>` with replay control |
| `svga`, `vap`, `pag`, `lottie`, `mov`, or unknown | show format/status and source product link; do not install a player or convert the asset |
| `unavailable` | show unavailable state and source product link |

No third-party player runtime is added in the first implementation. This keeps
the gallery static, avoids format conversion, and ensures that a non-playable
format cannot become a reason to fetch a protected original asset. The page
must not add `no-referrer`, a proxy, header spoofing, or any other workaround
for media-host access controls.

## Error Handling And Observability

The collector prints an execution summary:

```text
categories visited
pages requested
products accepted
products deduplicated
details enriched
preview URLs accepted
preview URLs rejected
terminal errors by category
output path
```

It exits non-zero when the output could not be produced, no public list
response passed schema validation, or an access-control challenge/HTTP 401/403
prevented all collection. It may exit zero with partial data when at least one
category completed; the terminal summary must clearly list skipped categories.

The generated HTML treats a missing or empty preview as normal content state,
not as a client-side error.

## Test Strategy

Use saved, sanitized fixtures only. No automated test calls `svga.wang`.

1. Add `unittest` tests for category/list parsing, full detail merge, stable
   `goodsId` deduplication, approved related-item projection, field dropping,
   and output sort order.
2. Add media-policy tests that accept plain public image/video URLs and reject
   `token`, `signature`, `expires`, download, ZIP, and unknown candidates.
3. Add a Node static-gallery test requiring a
   `const SVGA_CATALOG_ITEMS = [...]` payload, search/category controls,
   pagination, the reference-style detail structure, related-item rendering,
   and the unsupported-format fallback.
4. Run the collector once manually with a small `--max-pages` cap. Inspect the
   normalized JSON for no credentials, no prices, no signed URLs, and no
   download links.
5. Run batch collection with public list IDs and inspect the normalized JSON
   for detail coverage, no prices, no signed URLs, and no recursive raw
   `relatedGoods` payloads. Regenerate `output/index.html`, run all Node tests,
   then open the page locally to verify search, category filtering, pagination,
   detail metadata, related items, media-unavailable handling, and the
   unsupported fallback state.
6. Before deployment, add this project's `.vercelignore` rules for
   `svga_public_catalog/` and `output/*.json` to ensure collection source,
   fixtures, tests, and normalized input are never published.

## Acceptance Criteria

- The SVGA.WANG collector has no import or runtime dependency on any
  `/Users/mac345/Desktop/discord-shop` file or browser session state.
- All persisted records come from the allowlisted anonymous catalog flow and
  conform to the normalized schema.
- No persisted artifact contains cookies, authorization values, prices, order
  data, download links, signed URLs, or original source packages.
- Re-running collection with the same public data creates one row per
  `goodsId`.
- The batch output has one normalized detail projection for every successfully
  enriched public list item; failed detail requests leave that item's approved
  list metadata intact and are reported without retrying through any alternate
  access path.
- `output/index.html` is a self-contained, directly openable SVGA.WANG public
  catalog gallery.
- Each detail dialog presents the approved file information, tags, and related
  items in the reference-style two-column layout, without showing a price.
- Browser-incompatible formats degrade to metadata and a source link, with no
  player workaround.
- Vercel deployment serves only generated static HTML and does not publish
  collection source or raw/normalized JSON inputs.

## Risks And Explicit Assumptions

- Storefront endpoints and payloads are not a stable public contract. The
  normalizer must reject unknown schema changes rather than guessing fields.
- A URL that is technically public may still require rights-holder permission
  for commercial use. Catalog collection does not grant reuse rights.
- Public media hosts may block cross-origin rendering after collection. The
  generated page must preserve its metadata fallback and source product link.
- The current endpoint names are discovery observations, not permission to
  access login-gated or protected material.
