#!/usr/bin/env python3
"""递归抓取目录外关联商品的公开详情，投影为预览/详情查找表。

根因：relatedGoods 只投影 goods_id/name/image，不含动画 URL。静态画廊里点击
目录外关联商品时左侧只能显示静态缩略图、详情弹框数据也不全。本脚本为这些
goods_id 匿名抓取公开 getGoodsDetail（同一 allowlist 端点），复用
normalize._record 投影成与目录一致的完整记录，供画廊内嵌。

输出：output/svga-related-details.json  { goodsId: 完整 normalized 记录 }
缓存：output/.related_detail_cache/<goods_id>.json（断点续跑不重复请求）

用法：
    .venv/bin/python scripts/enrich_related_details.py            # 全部（默认4并发）
    .venv/bin/python scripts/enrich_related_details.py --workers 6
    .venv/bin/python scripts/enrich_related_details.py --limit 10 # 调试前10个
    .venv/bin/python scripts/enrich_related_details.py --offline  # 只用缓存重建
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from svga_public_catalog.normalize import _record  # noqa: E402

CATALOG = ROOT / "output" / "svga-public-catalog.json"
OUT = ROOT / "output" / "svga-related-details.json"
CACHE = ROOT / "output" / ".related_detail_cache"
DETAIL_API = "https://gapi.qianmusoft.com/mobile/index/getGoodsDetail?goods_id={gid}"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppVersion/2.0"
TIMEOUT = 12
MAX_RETRIES = 3
BACKOFF = 1.0
socket.setdefaulttimeout(TIMEOUT)  # 兜底：urllib 的 timeout 参数可能不覆盖挂起的读操作


def fetch_detail(gid: str) -> dict:
    """拉取单个商品详情，带重试。返回原始响应 dict（失败抛异常）。"""
    url = DETAIL_API.format(gid=gid)
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("err_code") == 0 and isinstance(data.get("result"), dict):
                return data
            last_exc = ValueError(f"业务错误 err_code={data.get('err_code')}")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF * attempt)
    raise last_exc if last_exc else RuntimeError(f"goods {gid} 拉取失败")


def process_one(gid: str) -> tuple[str, dict | None, str | None]:
    """拉取 + 落缓存。返回 (gid, result_dict_or_None, error_str_or_None)。"""
    cache_file = CACHE / f"{gid}.json"
    if cache_file.exists():
        try:
            return gid, json.loads(cache_file.read_text(encoding="utf-8")), None
        except Exception:  # noqa: BLE001
            cache_file.unlink(missing_ok=True)
    try:
        data = fetch_detail(gid)
        CACHE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return gid, data, None
    except Exception as exc:  # noqa: BLE001
        return gid, None, str(exc)


def main() -> int:
    ap = argparse.ArgumentParser(description="递归抓取目录外关联商品详情并投影查找表")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个（调试）")
    ap.add_argument("--offline", action="store_true", help="只用缓存重建，不联网")
    args = ap.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_ids = {str(item.get("goodsId")) for item in catalog}
    related_ids: set[str] = set()
    for item in catalog:
        for rel in item.get("relatedItems", []):
            gid = str(rel.get("goodsId"))
            if gid and gid not in catalog_ids:
                related_ids.add(gid)
    ordered = sorted(related_ids)
    if args.limit:
        ordered = ordered[: args.limit]
    print(f"目录外关联商品: {len(ordered)} 个（workers={args.workers}, offline={args.offline}）")

    details: dict[str, dict] = {}
    failed: dict[str, str] = {}

    if not args.offline:
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(process_one, gid): gid for gid in ordered}
            for fut in as_completed(futures):
                gid, data, err = fut.result()
                done += 1
                if data is not None:
                    details[gid] = data
                else:
                    failed[gid] = err
                if done % 50 == 0 or done == len(ordered):
                    print(f"  进度 {done}/{len(ordered)}，成功 {len(details)}，失败 {len(failed)}")
    else:
        for gid in ordered:
            cf = CACHE / f"{gid}.json"
            if cf.exists():
                details[gid] = json.loads(cf.read_text(encoding="utf-8"))
            else:
                failed[gid] = "无缓存"
        print(f"  offline 重建：缓存命中 {len(details)}，缺 {len(failed)}")

    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lookup: dict[str, dict] = {}
    for gid, payload in details.items():
        result = payload.get("result")
        if not isinstance(result, dict):
            failed[gid] = "无 result"
            continue
        record = _record({"goods_id": gid}, result, captured_at)
        if record is not None:
            lookup[gid] = record

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(lookup, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成 → {OUT}，成功投影 {len(lookup)} / {len(ordered)}")
    if failed:
        print("  失败明细（前 10）:")
        for gid, err in list(failed.items())[:10]:
            print(f"    {gid}: {err}")
    return 0 if lookup else 1


if __name__ == "__main__":
    raise SystemExit(main())
