# SVGA Public Shop

SVGA.WANG 公开商品目录的**自包含静态画廊**。匿名采集公开商品列表与详情，规范化后生成零运行时依赖的 `output/index.html`，可直接部署到任意静态托管（Vercel / GitHub Pages 等）。

> 仅采集**匿名可见**的商品元数据与可公开预览的媒体；价格一律以 `**` 展示（登录态或打码字段，不采集）。

> ⚠️ **免责声明：本仓库仅供个人学习与技术演示使用，无任何商业用途。**

## 功能特性

- **两级筛选**：顶部横向分类 Tab（全部 + 13 类）+「用途」chips（国内 / 海外 / 其他，数据驱动自动归类）
- **详情弹框**：左侧预览（图片 / mp4 动图 / 不可预览兜底）+ 右侧标签 / 元数据 / 关联商品
- **关联预览**：点击目录外关联商品可播放对应动图并同步详情（递归抓取的关联查找表，覆盖 100%）
- **搜索 + 分页** + 键盘 / 按钮翻页，移动端适配
- **深浅主题**：右上角一键切换，localStorage 持久化
- **完全自包含**：数据内嵌于 HTML，无任何运行时 API 调用

## 目录结构

```
svga-public-shop/
├── svga_public_catalog/        # 采集与规范化 Python 包
│   ├── collect.py              # 匿名 Playwright 爬取目录
│   ├── normalize.py            # 列表/详情 → fileInfo/tagList/relatedItems
│   ├── media.py / schema.py    # 预览 URL 判定 / 目录项校验
│   ├── fixtures/               # 测试夹具
│   └── tests/                  # 9 个单元测试
├── scripts/
│   ├── enrich_goods_detail.py  # 批量拉取 210 条商品详情
│   ├── enrich_related_details.py # 递归抓取 767 个目录外关联商品
│   ├── rebuild_catalog_from_cache.py # 用缓存重建（免重爬）
│   └── generate-catalog-gallery.mjs # 生成自包含画廊
├── tests/                      # 画廊输出 / Vercel 配置测试
├── output/                     # 生成产物（数据 + index.html）
├── CLAUDE.md                   # 项目开发指引
├── vercel.json                 # outputDirectory: output
└── .vercelignore               # 仅发布 index.html
```

## 更新链路（三步）

```bash
# 1. 采集目录（约 5-8 分钟，210 条）
.venv/bin/python -m svga_public_catalog.collect --max-pages 10

# 2. 补关联详情（缓存命中自动跳过；新增关联商品自动纳入）
.venv/bin/python scripts/enrich_related_details.py --workers 3

# 3. 生成画廊
node scripts/generate-catalog-gallery.mjs
```

生成的 `output/index.html` 即为可部署产物；`output/svga-public-catalog.json`（目录）与 `output/svga-related-details.json`（关联查找表）为中间数据。

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # playwright
.venv/bin/playwright install chromium
```

> `collect.py` 使用相对导入，必须以 `python -m svga_public_catalog.collect` 运行；直接 `python collect.py` 会 ImportError。

## 测试

```bash
node --test                                   # 画廊输出 + 部署配置
.venv/bin/python -m unittest discover -s svga_public_catalog/tests -q
```

> 改画廊脚本 / HTML 后必须跑 `node --test`，保证 `output/index.html` 内的 id / 函数名不被破坏。

## 部署（Vercel）

```bash
npx vercel --prod --yes
```

- `vercel.json`：`outputDirectory: output` + `cleanUrls`，`framework: null` 避免 Python 运行时误检测
- `.vercelignore`：仅上传 `index.html`，排除源码 / 脚本 / 测试 / 抓取缓存 / `output/*.json`

## 已知注意事项

- **CDN 防盗链**：媒体 CDN `pic.qianmukeji.cn` 按 Referer 校验，仅放行无 Referer 与 `svga.wang`。页面必须内嵌 `<meta name="referrer" content="no-referrer">`，否则线上 https 域名下所有媒体 403。
- **gapi 限流**：`getGoodsDetail` 按 IP 约 115-120 次请求 / 窗口即全站超时。批量抓取按批次：每 IP 抓 ~115 个 → 切 IP → 断点续跑（脚本带缓存）。

## 免责声明

> **本仓库内容仅供个人学习与技术演示使用，无任何商业用途。**

- 本项目仅用于个人学习与数据展示，所有数据均来自 SVGA.WANG 的公开接口，仅供匿名公开信息检索。
- 请尊重原站权益，**禁止用于任何商业用途**，包括但不限于商品转售、商业推广、广告投放等。
- 若原站或权利人要求，将随时下架相关数据与页面。
