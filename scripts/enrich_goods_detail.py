#!/usr/bin/env python3
"""为 svga-public-catalog 批量拉取详情页数据（gapi getGoodsDetail）并合并为全量 JSON。

读取  output/svga-public-catalog.json  的 210 条公开目录，
对每条调用  https://gapi.qianmusoft.com/mobile/index/getGoodsDetail?goods_id=<id>
把详情结果挂在每条记录的 detail 字段下，输出：

    output/svga-public-catalog-full.json

用法：
    .venv/bin/python scripts/enrich_goods_detail.py              # 拉全部
    .venv/bin/python scripts/enrich_goods_detail.py --ids 12241,12244   # 只拉指定
    .venv/bin/python scripts/enrich_goods_detail.py --limit 10   # 只拉前 N 条（调试）
    .venv/bin/python scripts/enrich_goods_detail.py --offline    # 用已缓存结果重建（不联网）

已拉取的结果缓存到 output/.detail_cache/<goods_id>.json，断点续跑不重复请求。
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "output" / "svga-public-catalog.json"
OUT = ROOT / "output" / "svga-public-catalog-full.json"
CACHE = ROOT / "output" / ".detail_cache"
DETAIL_API = "https://gapi.qianmusoft.com/mobile/index/getGoodsDetail?goods_id={gid}"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppVersion/2.0"
TIMEOUT = 15
MAX_WORKERS = 6
MAX_RETRIES = 3
BACKOFF = 1.0


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
            last_exc = ValueError(f"业务错误 err_code={data.get('err_code')} code={data.get('code')}")
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
    ap = argparse.ArgumentParser(description="批量拉取商品详情并合并为全量 JSON")
    ap.add_argument("--ids", help="逗号分隔的 goods_id 列表（默认用目录全部）")
    ap.add_argument("--limit", type=int, default=0, help="只拉前 N 条（调试用）")
    ap.add_argument("--offline", action="store_true", help="只用缓存重建，不联网")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = ap.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    else:
        ids = [str(it.get("goodsId")) for it in catalog if it.get("goodsId")]
    if args.limit:
        ids = ids[: args.limit]

    print(f"待拉取 {len(ids)} 条详情（workers={args.workers}, offline={args.offline}）")
    details: dict[str, dict] = {}
    failed: dict[str, str] = {}

    if not args.offline:
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(process_one, gid): gid for gid in ids}
            for fut in as_completed(futures):
                gid, data, err = fut.result()
                done += 1
                if data is not None:
                    details[gid] = data
                else:
                    failed[gid] = err
                if done % 30 == 0 or done == len(ids):
                    print(f"  进度 {done}/{len(ids)}，成功 {len(details)}，失败 {len(failed)}")
    else:
        # offline：只读缓存
        for gid in ids:
            cf = CACHE / f"{gid}.json"
            if cf.exists():
                details[gid] = json.loads(cf.read_text(encoding="utf-8"))
            else:
                failed[gid] = "无缓存"
        print(f"  offline 重建：缓存命中 {len(details)}，缺 {len(failed)}")

    # 合并
    merged: list[dict] = []
    for it in catalog:
        gid = str(it.get("goodsId"))
        rec = dict(it)
        detail = details.get(gid)
        if detail:
            rec["detail"] = detail.get("result", {})
            rec["detail_code"] = detail.get("code")
        else:
            rec["detail"] = {}
            rec["detail_error"] = failed.get(gid, "未拉取")
        merged.append(rec)

    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成。合并 {len(merged)} 条 → {OUT}")
    print(f"  详情成功 {len(details)}，失败 {len(failed)}")
    if failed:
        print("  失败明细（前 10）:")
        for gid, err in list(failed.items())[:10]:
            print(f"    {gid}: {err}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
