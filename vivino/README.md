# Vivino personal client

Derived from recorded authenticated browser sessions (2026-09-20) using the
derive-client workflow: HAR capture → endpoint identification → client generation →
live verification of every capability.

## Files

- `vivino_client.py` — the client (stdlib-only). All endpoints verified live.
- Session captures (HARs, cookie exports) are secret-bearing and stay out of the repo (0600 locally).
- Your taste profile / rating caches are personal data — keep them out of the repo.

## Capabilities (all verified)

| Method | What | Transport |
|---|---|---|
| `search_wines(q)` | Wine search | Algolia `WINES_prod` index (public key, no auth) |
| `get_wine(id, slug)` | Rating, region, country, grapes, style, taste structure | wine page HTML + `GET /api/wines/{id}/tastes` |
| `get_reviews(wine_id, vintage_year, per_page, page, min_rating)` | Community reviews | `GET /api/wines/{id}/reviews` |
| `get_my_review(wine_id, vintage_id)` | My review for a vintage | `GET /api/users/{uid}/vintages/{vid}/reviews` |
| `rate_wine(vintage_id, rating, note)` | Rate a wine | `POST /api/vintages/{vid}/reviews` {rating, note} |
| `update_rating(review_id, rating, note)` | Change rating | `PATCH /api/reviews/{rid}` |
| `delete_rating(review_id)` | Remove rating | `DELETE /api/reviews/{rid}` |
| `add_to_wishlist(vintage_id)` | Wishlist add | `POST /api/vintages/{vid}/wishlist` |
| `get_my_ratings()` | Full rating history (paginated) | `GET /users/{seo}/activities?limit=10&start_from_id=` (XHR, HTML) |
| `get_my_wishlist()` | Wishlist contents | wishlist page HTML |
| `my_taste_profile(ratings)` | Build affinity profile | derived |
| `taste_fit(wine_id, slug, profile)` | Fit score 0–100 + breakdown | derived |

## Taste-fit scoring

Weighted blend of:
- **Grape affinity** (50%): rank-percentile of the wine's grapes in my rating-weighted grape affinities
- **Region affinity** (30%), **style affinity** (20%)
- Structure distance: `|my_structure − wine_structure|` for acidity/intensity/sweetness/tannin,
  folded in at 45% weight (55% affinity). If nothing in common at all, capped at 35/100.

Sanity-checked: wines the profile owner rated 5.0 score high (79–94); unrelated wines score low (~35).

## Auth / refresh

Cookies + `csrf_token` load from a JSON cookie export (0600). To refresh:
log in via `agent-browser` with the real-Chrome UA (default Chromium UA is
CloudFront-blocked), then `agent-browser cookies get --json > vivino_cookies.json`.

## Not available (confirmed)

- **Cellar add / cellar contents** — Premium-gated on the web app ("Add to cellar" exists
  but the write flow requires a subscription).

## Caveats

- Vivino's internal API is unversioned; keep the HARs for re-derivation.
- HARs and cookie files contain live session material — keep out of git, 0600, delete when done.
- Write endpoints are Vivino's own web-app calls; rate honestly, respect rate limits (client throttles 0.8s).
