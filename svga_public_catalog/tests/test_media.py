from unittest import TestCase

from svga_public_catalog.media import classify_public_preview


class PublicPreviewTests(TestCase):
    def test_allows_plain_public_image_and_video_urls(self):
        self.assertEqual(
            classify_public_preview("https://media.example.test/x.webp"),
            ("https://media.example.test/x.webp", "webp", "image"),
        )
        self.assertEqual(
            classify_public_preview("https://media.example.test/x.mp4"),
            ("https://media.example.test/x.mp4", "mp4", "video"),
        )

    def test_labels_non_browser_preview_without_loading_it(self):
        self.assertEqual(
            classify_public_preview("https://media.example.test/x.svga"),
            ("https://media.example.test/x.svga", "svga", "unsupported"),
        )

    def test_rejects_access_control_and_download_urls(self):
        for url in (
            "http://media.example.test/x.mp4",
            "https://media.example.test/x.mp4?token=abc",
            "https://media.example.test/x.mp4?Expires=1",
            "https://media.example.test/download/x.mp4",
            "https://media.example.test/original.zip",
        ):
            self.assertEqual(
                classify_public_preview(url),
                ("", "", "unavailable"),
            )
