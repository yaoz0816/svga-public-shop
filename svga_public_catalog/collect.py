"""Anonymous collection of public SVGA.WANG catalog metadata."""

from __future__ import annotations

import argparse
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from .normalize import extract_list_items, normalize_catalog, write_catalog
from .schema import (
    PUBLIC_CATEGORY_ENDPOINT,
    PUBLIC_DETAIL_ENDPOINT,
    PUBLIC_LIST_ENDPOINT,
)

CATALOG_PAGE_URL = "https://svga.wang/shop"
REQUEST_TIMEOUT_MS = 45_000
MAX_RETRIES = 2

FetchCategories = Callable[[], list[dict[str, Any]]]
FetchPage = Callable[[str, int, int], dict[str, Any]]
FetchDetail = Callable[[str], dict[str, Any]]


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


class HttpStatusError(RuntimeError):
    """HTTP error carrying retry eligibility without retaining response data."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.status == 429 or self.status >= 500


class PublicCatalogClient:
    """Fresh, non-persistent browser context for observed public requests."""

    def __init__(self) -> None:
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._categories_payload: dict[str, Any] | None = None
        self._initial_list_payload: dict[str, Any] | None = None
        self._list_form: dict[str, str] | None = None

    def __enter__(self) -> PublicCatalogClient:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for live collection. Install it in this project first."
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(locale="zh-CN")
        page = self._context.new_page()
        page.on("response", self._capture_initial_response)
        page.goto(
            CATALOG_PAGE_URL,
            wait_until="domcontentloaded",
            timeout=REQUEST_TIMEOUT_MS,
        )

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self._categories_payload is not None and self._initial_list_payload is not None:
                break
            page.wait_for_timeout(250)

        if self._categories_payload is None or self._initial_list_payload is None:
            raise RuntimeError("anonymous storefront did not return public catalog responses")
        if not self._list_form:
            raise RuntimeError("anonymous storefront did not provide public list form data")
        return self

    def __exit__(self, *_exception: object) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _capture_initial_response(self, response: Any) -> None:
        try:
            if response.url == PUBLIC_CATEGORY_ENDPOINT:
                body = response.json()
                if isinstance(body, dict):
                    self._categories_payload = body
                return
            if response.url != PUBLIC_LIST_ENDPOINT or self._initial_list_payload is not None:
                return
            body = response.json()
            form = dict(parse_qsl(response.request.post_data or "", keep_blank_values=True))
            if isinstance(body, dict) and form:
                self._initial_list_payload = body
                self._list_form = form
        except Exception:
            return

    def _request_json(self, response: Any) -> dict[str, Any]:
        if response.status >= 400:
            raise HttpStatusError(response.status)
        try:
            body = response.json()
        except Exception as exc:
            raise ValueError("public endpoint returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise ValueError("public endpoint returned a non-object JSON body")
        return body

    def fetch_categories(self) -> list[dict[str, Any]]:
        result = (self._categories_payload or {}).get("result")
        categories = result.get("gc_list") if isinstance(result, dict) else None
        if not isinstance(categories, list):
            raise ValueError("missing result.gc_list")
        return [category for category in categories if isinstance(category, dict)]

    def fetch_public_page(
        self,
        category_id: str,
        page: int,
        _page_size: int,
    ) -> dict[str, Any]:
        if self._context is None or self._list_form is None:
            raise RuntimeError("public catalog client is not open")
        form = self._list_form.copy()
        form["gc_id"] = category_id
        form["page"] = str(page)
        response = self._context.request.post(
            PUBLIC_LIST_ENDPOINT,
            form=form,
            timeout=REQUEST_TIMEOUT_MS,
        )
        return self._request_json(response)

    def fetch_public_detail(self, goods_id: str) -> dict[str, Any]:
        if self._context is None:
            raise RuntimeError("public catalog client is not open")
        response = self._context.request.post(
            f"{PUBLIC_DETAIL_ENDPOINT}?goods_id={goods_id}",
            timeout=REQUEST_TIMEOUT_MS,
        )
        return self._request_json(response)


def _retry(
    callback: Callable[[], Any],
    sleep: Callable[[float], None],
) -> Any:
    for attempt in range(MAX_RETRIES + 1):
        try:
            return callback()
        except HttpStatusError as exc:
            retryable = exc.retryable
        except (TimeoutError, ConnectionError):
            retryable = True
        if not retryable or attempt == MAX_RETRIES:
            raise
        sleep(2**(attempt + 1))
    raise AssertionError("unreachable")


def _category_id(category: dict[str, Any]) -> str:
    value = category.get("gc_id")
    if value is None:
        raise ValueError("category is missing gc_id")
    return str(value)


def _page_count(payload: dict[str, Any]) -> int | None:
    result = payload.get("result")
    value = result.get("recommend_page_count") if isinstance(result, dict) else None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return None


def _limited_payload(payload: dict[str, Any], page_size: int) -> dict[str, Any]:
    """Apply the user-visible per-page cap without sending an unobserved form key."""
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    items = result.get("recommend_list")
    if not isinstance(items, list):
        return payload
    copy = payload.copy()
    copy["result"] = result.copy()
    copy["result"]["recommend_list"] = items[:page_size]
    return copy


def collect_catalog(
    max_pages: int,
    page_size: int,
    detail_limit: int,
    output_path: Path,
    fetch_categories: FetchCategories,
    fetch_page: FetchPage,
    fetch_detail: FetchDetail,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = lambda: random.uniform(0.25, 0.75),
    captured_at: str | None = None,
) -> CollectionResult:
    """Collect approved public fields via injected public-only transport."""
    if max_pages < 1 or page_size < 1 or detail_limit < -1:
        raise ValueError(
            "max_pages/page_size must be positive and detail_limit must be -1 or non-negative"
        )

    terminal_errors: dict[str, str] = {}
    list_payloads: list[dict[str, Any]] = []
    raw_item_count = 0
    pages_requested = 0
    categories_visited = 0

    try:
        categories = fetch_categories()
    except Exception as exc:
        return CollectionResult(0, 0, 0, 0, 0, 0, 0, {"categories": str(exc)}, None)

    seen_categories: set[str] = set()
    for category in categories:
        try:
            category_id = _category_id(category)
        except ValueError:
            continue
        if category_id in seen_categories:
            continue
        seen_categories.add(category_id)
        categories_visited += 1

        for page in range(1, max_pages + 1):
            try:
                sleep(1.2 + jitter())
                payload = _retry(
                    lambda: fetch_page(category_id, page, page_size),
                    sleep,
                )
                limited = _limited_payload(payload, page_size)
                items = extract_list_items(limited)
            except (PermissionError, HttpStatusError, ValueError, RuntimeError) as exc:
                terminal_errors[category_id] = str(exc)
                break

            pages_requested += 1
            if not items:
                break
            raw_item_count += len(items)
            list_payloads.append(limited)
            page_count = _page_count(payload)
            if page_count is not None and page >= page_count:
                break

    if not list_payloads:
        return CollectionResult(
            categories_visited,
            pages_requested,
            0,
            0,
            0,
            0,
            0,
            terminal_errors,
            None,
        )

    details: dict[str, dict[str, Any]] = {}
    if detail_limit != 0:
        for payload in list_payloads:
            for item in extract_list_items(payload):
                goods_id = str(item.get("goods_id", ""))
                if (
                    not goods_id
                    or goods_id in details
                    or (detail_limit > 0 and len(details) >= detail_limit)
                ):
                    continue
                try:
                    sleep(1.2 + jitter())
                    details[goods_id] = _retry(lambda: fetch_detail(goods_id), sleep)
                except (PermissionError, HttpStatusError, ValueError, RuntimeError):
                    continue

    timestamp = captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = normalize_catalog(list_payloads, details, timestamp)
    write_catalog(rows, output_path)
    accepted_previews = sum(
        row["previewSupport"] in {"image", "video"} for row in rows
    )
    return CollectionResult(
        categories_visited=categories_visited,
        pages_requested=pages_requested,
        products_accepted=len(rows),
        products_deduplicated=max(0, raw_item_count - len(rows)),
        details_enriched=len(details),
        preview_urls_accepted=accepted_previews,
        preview_urls_rejected=len(rows) - accepted_previews,
        terminal_errors=terminal_errors,
        output_path=output_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public SVGA.WANG catalog metadata")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=-1,
        help="-1 enriches every public list item, 0 disables enrichment",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[1] / "output" / "svga-public-catalog.json",
    )
    args = parser.parse_args()

    try:
        with PublicCatalogClient() as client:
            result = collect_catalog(
                max_pages=args.max_pages,
                page_size=args.page_size,
                detail_limit=args.detail_limit,
                output_path=args.output,
                fetch_categories=client.fetch_categories,
                fetch_page=client.fetch_public_page,
                fetch_detail=client.fetch_public_detail,
            )
    except Exception as exc:
        print(f"collection failed: {exc}")
        return 1

    print(f"categories visited: {result.categories_visited}")
    print(f"pages requested: {result.pages_requested}")
    print(f"products accepted: {result.products_accepted}")
    print(f"products deduplicated: {result.products_deduplicated}")
    print(f"details enriched: {result.details_enriched}")
    print(f"preview URLs accepted: {result.preview_urls_accepted}")
    print(f"preview URLs rejected: {result.preview_urls_rejected}")
    print(f"terminal errors: {result.terminal_errors}")
    print(f"output path: {result.output_path}")
    return 0 if result.output_path is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
