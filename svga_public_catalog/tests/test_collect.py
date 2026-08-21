from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from svga_public_catalog.collect import CollectionResult, collect_catalog


class CollectCatalogTests(TestCase):
    def test_honors_page_limit_and_writes_normalized_output(self):
        def fetch_categories():
            return [{"gc_id": 9, "gc_name": "Fixture"}]

        def fetch_page(category_id: str, page: int, page_size: int):
            self.assertEqual(category_id, "9")
            self.assertEqual(page_size, 20)
            return {
                "result": {
                    "recommend_page_count": 2,
                    "recommend_list": [
                        {
                            "goods_id": page,
                            "goods_name": f"Item {page}",
                            "goods_category": "Fixture",
                        }
                    ],
                }
            }

        with TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            result = collect_catalog(
                max_pages=2,
                page_size=20,
                detail_limit=0,
                output_path=output,
                fetch_categories=fetch_categories,
                fetch_page=fetch_page,
                fetch_detail=lambda _goods_id: {},
                sleep=lambda _seconds: None,
                jitter=lambda: 0,
                captured_at="2026-08-20T00:00:00Z",
            )

            self.assertTrue(output.exists())

        self.assertIsInstance(result, CollectionResult)
        self.assertEqual(result.pages_requested, 2)
        self.assertEqual(result.products_accepted, 2)
        self.assertEqual(result.terminal_errors, {})

    def test_records_403_as_terminal_without_alternate_access(self):
        result = collect_catalog(
            max_pages=1,
            page_size=20,
            detail_limit=0,
            output_path=Path("/tmp/no-output.json"),
            fetch_categories=lambda: [{"gc_id": 9, "gc_name": "Blocked"}],
            fetch_page=lambda _category_id, _page, _page_size: (_ for _ in ()).throw(
                PermissionError("HTTP 403")
            ),
            fetch_detail=lambda _goods_id: {},
            sleep=lambda _seconds: None,
            jitter=lambda: 0,
            captured_at="2026-08-20T00:00:00Z",
        )

        self.assertEqual(result.products_accepted, 0)
        self.assertEqual(result.terminal_errors, {"9": "HTTP 403"})
        self.assertIsNone(result.output_path)

    def test_retries_transient_page_error_before_accepting_public_data(self):
        calls = 0

        def fetch_page(_category_id: str, _page: int, _page_size: int):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("temporary timeout")
            return {
                "result": {
                    "recommend_page_count": 1,
                    "recommend_list": [
                        {
                            "goods_id": 1,
                            "goods_name": "Recovered",
                            "goods_category": "Fixture",
                        }
                    ],
                }
            }

        with TemporaryDirectory() as directory:
            result = collect_catalog(
                max_pages=1,
                page_size=20,
                detail_limit=0,
                output_path=Path(directory) / "catalog.json",
                fetch_categories=lambda: [{"gc_id": 9, "gc_name": "Fixture"}],
                fetch_page=fetch_page,
                fetch_detail=lambda _goods_id: {},
                sleep=lambda _seconds: None,
                jitter=lambda: 0,
                captured_at="2026-08-20T00:00:00Z",
            )

        self.assertEqual(calls, 2)
        self.assertEqual(result.products_accepted, 1)

    def test_unbounded_detail_enrichment_keeps_item_when_one_detail_fails(self):
        detail_calls: list[str] = []

        def fetch_detail(goods_id: str):
            detail_calls.append(goods_id)
            if goods_id == "2":
                raise PermissionError("HTTP 403")
            return {
                "result": {
                    "goods_id": 1,
                    "goods_advword": "File 281KB Memory 3.3MB",
                    "tagname_list": ["Featured"],
                }
            }

        with TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            result = collect_catalog(
                max_pages=1,
                page_size=20,
                detail_limit=-1,
                output_path=output,
                fetch_categories=lambda: [{"gc_id": 9, "gc_name": "Fixture"}],
                fetch_page=lambda _category_id, _page, _page_size: {
                    "result": {
                        "recommend_page_count": 1,
                        "recommend_list": [
                            {"goods_id": 1, "goods_name": "One", "goods_category": "Fixture"},
                            {"goods_id": 2, "goods_name": "Two", "goods_category": "Fixture"},
                        ],
                    }
                },
                fetch_detail=fetch_detail,
                sleep=lambda _seconds: None,
                jitter=lambda: 0,
                captured_at="2026-08-20T00:00:00Z",
            )

        self.assertEqual(detail_calls, ["1", "2"])
        self.assertEqual(result.details_enriched, 1)
        self.assertEqual(result.products_accepted, 2)
