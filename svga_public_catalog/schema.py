"""Schema constants for public catalog filtering."""

from __future__ import annotations

DENIED_QUERY_KEYS = frozenset(
    {"token", "signature", "expires", "expiry", "auth", "auth_key", "key"}
)
DENIED_PATH_MARKERS = frozenset(
    {"login", "member", "cart", "order", "payment", "download", "token"}
)
IMAGE_FORMATS = frozenset({"gif", "webp", "png", "jpg", "jpeg"})
VIDEO_FORMATS = frozenset({"mp4", "webm"})
UNSUPPORTED_FORMATS = frozenset({"svga", "vap", "pag", "json", "lottie", "mov"})

PUBLIC_LIST_ENDPOINT = "https://gapi.qianmusoft.com/mobile/index/getMoreList"
PUBLIC_CATEGORY_ENDPOINT = "https://gapi.qianmusoft.com/mobile/index/getCateList"
PUBLIC_DETAIL_ENDPOINT = "https://gapi.qianmusoft.com/mobile/index/getGoodsDetail"
