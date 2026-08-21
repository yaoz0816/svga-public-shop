"""Normalize anonymous public catalog responses into a minimal schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .media import classify_public_preview

SOURCE = "svga.wang"
PRICE_VISIBILITY = "login-gated-or-masked"
DETAIL_URL = "https://svga.wang/shop?goods_id={goods_id}"
DETAIL_API_URL = (
    "https://gapi.qianmusoft.com/mobile/index/getGoodsDetail?goods_id={goods_id}"
)


def extract_list_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the fixture-confirmed public list or reject an unknown shape."""
    result = payload.get("result")
    items = result.get("recommend_list") if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise ValueError("missing result.recommend_list")
    return [item for item in items if isinstance(item, dict)]


def _detail_item(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _first_value(
    list_item: dict[str, Any],
    detail_item: dict[str, Any],
    field: str,
) -> Any:
    value = list_item.get(field)
    if value not in (None, "", []):
        return value
    return detail_item.get(field)


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else str(value) if value is not None else ""


def _tags(value: Any) -> str:
    return " · ".join(_tag_list(value))


def _tag_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _thumbnail(value: Any) -> str:
    url, _format, support = classify_public_preview(value)
    return url if support == "image" else ""


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
        rows.append(
            {
                "goodsId": goods_id,
                "name": _as_text(item.get("goods_name")),
                "thumbnailUrl": _thumbnail(item.get("goods_image")),
            }
        )
    return rows


def _record(
    list_item: dict[str, Any],
    detail_item: dict[str, Any],
    captured_at: str,
) -> dict[str, Any] | None:
    goods_id = _as_text(_first_value(list_item, detail_item, "goods_id"))
    if not goods_id:
        return None

    preview_url, preview_format, preview_support = classify_public_preview(
        _first_value(list_item, detail_item, "goods_video_url")
    )
    is_2d = _first_value(list_item, detail_item, "g_2d")
    if is_2d in (1, "1"):
        dimension = "2D"
    elif is_2d in (0, "0"):
        dimension = "3D"
    else:
        dimension = ""

    return {
        "source": SOURCE,
        "goodsId": goods_id,
        "name": _as_text(_first_value(list_item, detail_item, "goods_name")),
        "number": f"NO.{goods_id}",
        "category": _as_text(_first_value(list_item, detail_item, "goods_category")),
        "tag": _tags(_first_value(list_item, detail_item, "tagname_list")),
        "usage": _as_text(_first_value(list_item, detail_item, "g_sub_title")),
        "dimension": dimension,
        "fileInfo": _as_text(_first_value(list_item, detail_item, "goods_advword")),
        "tagList": _tag_list(_first_value(list_item, detail_item, "tagname_list")),
        "relatedItems": _related_items(detail_item.get("relatedGoods")),
        "thumbnailUrl": _thumbnail(
            _first_value(list_item, detail_item, "goods_image")
        ),
        "publicPreviewUrl": preview_url,
        "previewFormat": preview_format,
        "previewSupport": preview_support,
        "detailUrl": DETAIL_URL.format(goods_id=goods_id),
        "sourceApiUrl": DETAIL_API_URL.format(goods_id=goods_id),
        "priceVisibility": PRICE_VISIBILITY,
        "capturedAt": captured_at,
    }


def normalize_catalog(
    list_payloads: list[dict[str, Any]],
    detail_payloads: dict[str, dict[str, Any]],
    captured_at: str,
) -> list[dict[str, Any]]:
    """Produce deduplicated records using only the approved public fields."""
    records: dict[str, dict[str, Any]] = {}
    for payload in list_payloads:
        for list_item in extract_list_items(payload):
            goods_id = _as_text(list_item.get("goods_id"))
            if not goods_id or goods_id in records:
                continue
            record = _record(list_item, _detail_item(detail_payloads.get(goods_id)), captured_at)
            if record is not None:
                records[goods_id] = record
    return sorted(
        records.values(),
        key=lambda record: (
            record["category"].casefold(),
            record["number"].casefold(),
            record["goodsId"],
        ),
    )


def write_catalog(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write deterministic UTF-8 JSON with no raw API payloads."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
