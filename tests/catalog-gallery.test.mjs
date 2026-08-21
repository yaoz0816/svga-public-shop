import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

const outputDir = new URL('../output/', import.meta.url);
const catalogFile = new URL('svga-public-catalog.json', outputDir);
const pageFile = new URL('index.html', outputDir);

test('standalone catalog page embeds normalized data and preview controls', () => {
  const source = JSON.parse(readFileSync(catalogFile, 'utf8'));

  assert.ok(existsSync(pageFile), 'output/index.html should be generated');
  assert.ok(
    source.every(
      (item) =>
        typeof item.fileInfo === 'string' &&
        Array.isArray(item.tagList) &&
        Array.isArray(item.relatedItems),
    ),
    'normalized records include the approved detail fields',
  );

  const html = readFileSync(pageFile, 'utf8');
  const embedded = html.match(
    /const SVGA_CATALOG_ITEMS = (\[[\s\S]*?\]);\nconst SVGA_RELATED_DETAILS = ([\s\S]*?);\n\nconst PAGE_SIZE/,
  );

  assert.ok(embedded, 'the page embeds normalized catalog items');
  assert.deepEqual(JSON.parse(embedded[1]), source);
  assert.ok(
    embedded[2] && JSON.parse(embedded[2]),
    'the page embeds the related-detail lookup',
  );
  assert.match(html, /id="catalog-search"/);
  assert.match(html, /id="category-list"/);
  assert.match(html, /function renderCatalogPage\(/);
  assert.match(html, /function renderCatalogModalMedia\(/);
  assert.match(html, /function renderDetailTags\(/);
  assert.match(html, /function renderRelatedItems\(/);
  assert.match(html, /function renderDetailCover\(/);
  assert.match(html, /class="detail-dialog"/);
  assert.match(html, /不支持在浏览器中预览/);
  assert.match(html, /该媒体无法在浏览器中预览。/);
  assert.match(
    html,
    /<meta name="referrer" content="no-referrer">/,
    'the page suppresses Referer so the CDN hotlink check allows media',
  );
  assert.doesNotMatch(html, /referrerpolicy|fetch\(/i);
  assert.doesNotMatch(
    html,
    /goods_promotion_price|goods_marketprice|goods_price/,
  );
});
