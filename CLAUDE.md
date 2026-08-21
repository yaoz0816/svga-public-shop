# CLAUDE.md

SVGA.WANG 公开商品目录 → 自包含静态画廊（Vercel 部署）。采集公开商品列表与详情，规范化后生成一个零运行时依赖的 `output/index.html`。

## 更新链路（三步）

1. **采集目录**：`.venv/bin/python -m svga_public_catalog.collect --max-pages 10`
   → 匿名 Playwright 爬取，写 `output/svga-public-catalog.json`（约 5-8 分钟，当前约 210 条）。
2. **补关联详情**：`.venv/bin/python scripts/enrich_related_details.py --workers 3`
   → 递归抓取目录外关联商品的 getGoodsDetail，投影成 `output/svga-related-details.json` 查找表（goodsId → 完整 normalized 记录）。原始响应缓存于 `output/.related_detail_cache/<gid>.json`，断点续跑不重复请求。
3. **生成画廊**：`node scripts/generate-catalog-gallery.mjs`
   → 内嵌 `SVGA_CATALOG_ITEMS` + `SVGA_RELATED_DETAILS`，写自包含 `output/index.html`。

## 关键坑

- **相对导入**：`collect.py` 用相对导入，必须 `-m svga_public_catalog.collect` 运行；直接 `python collect.py` 会 ImportError。
- **gapi 限流**：`gapi.qianmusoft.com/mobile/index/getGoodsDetail` 按 IP 约 115-120 次请求/窗口即全站超时（连已知好 id 也超时），并发触发更早。批量抓取必须按批次：每 IP 抓 ~115 个 → 用户切 IP → 断点续跑。探测 IP 用已知好 id（如 `getGoodsDetail?goods_id=12241`）。
- **价格字段**：一律 `**`（登录态或打码，不采集）。
- **预览判定**：部分媒体无法在浏览器中预览，画廊需兜底文案。

## 数据 Schema

`normalize.py` 产出 `fileInfo` / `tagList[]` / `relatedItems[]`（`{goodsId,name,thumbnailUrl}`），源为 `goods_advword` / `tagname_list` / `relatedGoods`。`relatedGoods` API 投影不含动画 URL——所以点击目录外关联商品要靠步骤 2 的查找表播放动图。

## 页面功能（generate-catalog-gallery.mjs）

- **两级筛选**：顶部横向分类 Tab（全部 + 13 类）+「用途」chips 按 国内/海外/其他 分组（数据驱动：按 tag 与 国内/海外 的共现计数推断归属）。
- **详情弹框**：左侧预览（图片 / mp4 动图 / 不可预览兜底）+ 右侧标签/元数据/关联卡；点击关联卡经三级查找（当前筛选 → 全目录 → 关联详情查找表）同步播放并刷新弹框。
- 搜索 + 分页 + 键盘/按钮翻页，移动端适配。

## 测试

- node：`node --test`（校验 output/index.html 内嵌数据、渲染函数、禁项：无 referrerpolicy/fetch、无价格字段）。
- python：`.venv/bin/python -m unittest discover -s svga_public_catalog/tests -q`
- **改画廊脚本/HTML 后必须跑 node 测试**，保证 `output/index.html` 里的 id/函数名不被破坏。

## 部署

- `vercel.json`：`outputDirectory: output` + `cleanUrls`。
- `.vercelignore`：仅发布 `output/index.html`，排除 `.venv` / `docs` / `scripts` / `tests` / `svga_public_catalog/` 源码与 `output/*.json`。
- `.gitignore`：排除 `.venv`、`__pycache__`、抓取缓存（`.detail_cache`、`.related_detail_cache`）、过期备份 JSON。
