# Fixture Rules

Fixtures are manually redacted public response bodies captured from an anonymous
browser session. They must never contain headers, cookies, request payloads,
price amounts, member fields, cart/order/payment fields, download links, signed
URLs, or user information.

Capture at most one list response and one detail response. Keep only the keys
needed for category, stable product ID, title, visible labels, thumbnail, and
candidate preview URL. Replace any real public CDN host with
`https://media.example.test` after preserving the original extension.

The anonymous storefront response shape observed on August 20, 2026 is:

- categories: `result.gc_list`
- product list: `result.recommend_list`
- product detail: `result`
- public list request: form fields `brand_id`, `gc_id`, `hotsearch`, `order`,
  `page`, `search`, and `tag_id`

The fixtures below retain only fields used by the normalizer. The real endpoint
also returned price-related fields; those were deliberately omitted.
