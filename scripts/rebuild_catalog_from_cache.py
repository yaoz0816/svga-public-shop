#!/usr/bin/env python3
"""用已缓存的详情响应把公开目录重建为新 schema（fileInfo/tagList/relatedItems）。

背景：normalize.py 升级产出 fileInfo/tagList/relatedItems 后，output 里旧的
svga-public-catalog.json 仍是旧 schema。不重跑 Playwright 采集，改为：

    - 详情：读 output/.detail_cache/<goods_id>.json（getGoodsDetail 原始响应，210 条）
    - 列表：由现有目录的 goodsId 合成 list_payloads（normalize 的 _first_value 会从
      detail 兜底取全部字段，因此等价于真实采集产物）

用法：
    .venv/bin/python scripts/rebuild_catalog_from_cache.py \
        [--input output/svga-public-catalog.json] [--output output/svga-public-catalog.json]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from svga_public_catalog.normalize import (  # noqa: E402
    extract_list_items,
    normalize_catalog,
    write_catalog,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="从详情缓存重建新 schema 公开目录")
    ap.add_argument("--input", type=Path, default=ROOT / "output" / "svga-public-catalog.json")
    ap.add_argument("--output", type=Path, default=ROOT / "output" / "svga-public-catalog.json")
    ap.add_argument("--cache", type=Path, default=ROOT / "output" / ".detail_cache")
    args = ap.parse_args()

    catalog = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise SystemExit("input 不是数组")

    cache = args.cache
    if not cache.is_dir():
        raise SystemExit(f"详情缓存目录不存在: {cache}")

    # detail_payloads: 原始 getGoodsDetail 响应，按 goods_id 键控
    detail_payloads: dict[str, dict] = {}
    for file in cache.glob("*.json"):
        goods_id = file.stem
        detail_payloads[goods_id] = json.loads(file.read_text(encoding="utf-8"))
    print(f"详情缓存: {len(detail_payloads)} 条")

    # list_payloads: 由现有目录 goodsId 合成（字段从 detail 兜底）
    goods_ids = [str(item.get("goodsId")) for item in catalog if item.get("goodsId")]
    list_payload = {
        "result": {
            "recommend_list": [{"goods_id": gid} for gid in goods_ids],
        }
    }
    list_payloads = [list_payload]
    list_count = len(extract_list_items(list_payload))
    print(f"列表条目: {list_count}")

    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = normalize_catalog(list_payloads, detail_payloads, captured_at)
    write_catalog(rows, args.output)

    from collections import Counter

    print(f"\n完成 → {args.output}，共 {len(rows)} 条")
    print("  分类分布:", dict(Counter(r["category"] for r in rows)))
    has_rel = sum(1 for r in rows if r["relatedItems"])
    has_tag = sum(1 for r in rows if r["tagList"])
    has_file = sum(1 for r in rows if r["fileInfo"])
    print(f"  带 relatedItems: {has_rel} | 带 tagList: {has_tag} | 带 fileInfo: {has_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
