import json
from pathlib import Path
from unittest import TestCase

from svga_public_catalog.normalize import normalize_catalog

FIXTURES = Path(__file__).parents[1] / "fixtures"


class NormalizeCatalogTests(TestCase):
    def test_keeps_only_approved_fields_and_filters_restricted_preview(self):
        listing = json.loads((FIXTURES / "public-list.json").read_text("utf-8"))
        details = json.loads((FIXTURES / "public-detail.json").read_text("utf-8"))

        rows = normalize_catalog(
            [listing],
            {"10001": details},
            "2026-08-20T00:00:00Z",
        )

        self.assertEqual([row["goodsId"] for row in rows], ["10001", "10002"])
        self.assertEqual(rows[0]["number"], "NO.10001")
        self.assertEqual(
            rows[0]["publicPreviewUrl"],
            "https://media.example.test/preview.mp4",
        )
        self.assertEqual(rows[0]["previewSupport"], "video")
        self.assertEqual(rows[1]["publicPreviewUrl"], "")
        self.assertEqual(rows[1]["previewSupport"], "unavailable")
        self.assertEqual(rows[0]["fileInfo"], "File 281KB Memory 3.3MB")
        self.assertEqual(rows[0]["tagList"], ["MP4", "Featured"])
        self.assertEqual(
            rows[0]["relatedItems"],
            [
                {
                    "goodsId": "10003",
                    "name": "Fixture Related Gift",
                    "thumbnailUrl": "https://media.example.test/related.png",
                }
            ],
        )
        self.assertNotIn("goods_price", rows[0])
        self.assertNotIn("goods_promotion_price", rows[0])
        self.assertNotIn("goods_marketprice", rows[0])
        self.assertEqual(
            set(rows[0]),
            {
                "source",
                "goodsId",
                "name",
                "number",
                "category",
                "tag",
                "usage",
                "dimension",
                "thumbnailUrl",
                "publicPreviewUrl",
                "previewFormat",
                "previewSupport",
                "detailUrl",
                "sourceApiUrl",
                "priceVisibility",
                "capturedAt",
                "fileInfo",
                "tagList",
                "relatedItems",
            },
        )

    def test_deduplicates_goods_id_and_sorts_stably(self):
        payload = {
            "result": {
                "recommend_list": [
                    {"goods_id": 2, "goods_name": "B", "goods_category": "B"},
                    {"goods_id": 1, "goods_name": "A", "goods_category": "A"},
                    {
                        "goods_id": 2,
                        "goods_name": "Duplicate",
                        "goods_category": "B",
                    },
                ]
            }
        }

        rows = normalize_catalog([payload], {}, "2026-08-20T00:00:00Z")

        self.assertEqual([row["goodsId"] for row in rows], ["1", "2"])
