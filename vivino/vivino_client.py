#!/usr/bin/env python3
"""Vivino personal client — scoped to what Hemanth asked for:
  - search wines
  - rate a wine (with optional note)
  - wine page: rating, reviews, region, style, grapes
  - my ratings history + taste profile
  - taste-fit score: how well a wine matches my rated history

Derived from recorded authenticated sessions (2026-09-20). All endpoints verified live.
Auth: session cookies + csrf_token loaded from a 0600 cookie JSON export. Never hardcode.
Writes used sparingly and deliberately (rating/wishlist are POSTs Vivino's own web app makes).

Cookie refresh: log in via agent-browser, `agent-browser cookies get --json > vivino_cookies.json`.
"""
import json
import re
import time
import html as H
import statistics
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE = "https://www.vivino.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


class VivinoError(RuntimeError):
    pass


class VivinoClient:
    def __init__(self, cookies_json: str | Path, min_interval: float = 0.8):
        cookies = json.loads(Path(cookies_json).read_text())["data"]["cookies"]
        self.cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("value"))
        csrf = next((c["value"] for c in cookies if c["name"] == "csrf_token"), "")
        self.csrf = csrf
        self._min_interval = min_interval
        self._last = 0.0
        self.user_id = self._get_json("/api/users/me")["user"]["id"]
        self.seo_name = self._get_json("/api/users/me")["user"]["seo_name"]

    # ---------- transport ----------

    def _throttle(self):
        wait = self._min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _call(self, path_or_url: str, method: str = "GET", data=None,
              accept: str = "application/json", referer: str | None = None) -> tuple[int, bytes]:
        self._throttle()
        url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
        headers = {
            "User-Agent": UA,
            "Accept": accept,
            "X-Requested-With": "XMLHttpRequest",
            "X-Csrf-Token": self.csrf,
            "Cookie": self.cookie_header,
            "Referer": referer or BASE + "/",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, headers=headers, method=method,
                                     data=json.dumps(data).encode() if isinstance(data, (dict, list)) else data)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as ex:
            if ex.code in (401, 403, 422):
                raise VivinoError(f"{ex.code} on {url} — session expired; re-export cookies") from ex
            raise

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        url = path + (("?") + urllib.parse.urlencode(params) if params else "")
        s, b = self._call(url)
        return json.loads(b.decode())

    # ---------- search ----------

    def search_wines(self, query: str, limit: int = 10) -> list[dict]:
        """Search wines via Vivino's Algolia search index (public key, no auth needed).

        Returns [{wine_id, name, slug, region, vintage_id, year, rating, ratings_count}].
        """
        req = urllib.request.Request(
            "https://9takgwjuxl-dsn.algolia.net/1/indexes/WINES_prod/query?x-algolia-agent=HermesClient",
            method="POST",
            data=json.dumps({"query": query, "hitsPerPage": limit}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Algolia-API-Key": "60c11b2f1068885161d95ca068d3a6ae",
                "X-Algolia-Application-Id": "9TAKGWJUXL",
            })
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
        out = []
        for h in body.get("hits", []):
            vintages = h.get("vintages") or []
            # pick the vintage with the most ratings (most representative)
            vbest = max(vintages, key=lambda v: ((v.get("statistics") or {}).get("ratings_count") or 0)) if vintages else {}
            stats = vbest.get("statistics") or {}
            out.append({
                "wine_id": h.get("id"), "name": h.get("name"), "slug": h.get("seo_name"),
                "region": (h.get("region") or {}).get("name"),
                "type_id": h.get("type_id"),
                "vintage_id": vbest.get("id"), "year": vbest.get("year"),
                "rating": stats.get("ratings_average"), "ratings_count": stats.get("ratings_count"),
            })
        return out

    # ---------- wine page ----------

    def get_wine(self, wine_id: int, slug: str | None = None) -> dict:
        """Full wine metadata: rating, region, country, grapes, style, winery, taste structure."""
        out = {}
        if slug:
            s, b = self._call(f"/en/{slug}/w/{wine_id}", accept="text/html")
            if s == 200:
                html = b.decode(errors="replace")
                m = re.search(r'"region":\s*\{[^{}]*"name":\s*"([^"]+)"[^{}]*"country":\s*\{[^{}]*"name":\s*"([^"]+)"', html)
                if m:
                    out["region"], out["country"] = m.group(1), m.group(2)
                g = re.search(r"Grapes\t([^\n]+)", html)
                if g:
                    out["grapes"] = [x.strip() for x in H.unescape(g.group(1)).split(",")]
                else:
                    gj = re.search(r'"grapes":\s*\[(.{0,800}?)\]', html, re.S)
                    if gj:
                        out["grapes"] = re.findall(r'"name":\s*"([A-Z][^"]+)"', gj.group(1))
                st = re.search(r'"style":\s*\{[^{}]*?"name":\s*"([^"]+)"', html)
                if st:
                    out["style"] = st.group(1)
                av = re.search(r'"average_rating"\s*:\s*([\d.]+)', html)
                if av:
                    out["avg_rating"] = float(av.group(1))
        # taste structure always available from JSON
        s, b = self._call(f"/api/wines/{wine_id}/tastes")
        if s == 200:
            t = json.loads(b.decode()).get("tastes", {})
            out["taste_structure"] = {k: t.get("structure", {}).get(k)
                                      for k in ("acidity", "intensity", "sweetness", "tannin", "fizziness")}
        out.setdefault("wine_id", wine_id)
        return out

    def get_reviews(self, wine_id: int, vintage_year: int | None = None,
                    per_page: int = 10, page: int = 1, min_rating: float | None = None) -> list[dict]:
        """Community reviews for a wine (optionally filtered by vintage year / rating)."""
        params = {k: v for k, v in {
            "vintage_year": vintage_year, "perPage": per_page, "page": page,
            "ratings": min_rating}.items() if v is not None}
        data = self._get_json(f"/api/wines/{wine_id}/reviews", params)
        out = []
        for r in data.get("reviews", []):
            out.append({
                "id": r["id"], "rating": r.get("rating"), "note": (r.get("note") or "").strip(),
                "created_at": r.get("created_at"),
                "user": (r.get("user") or {}).get("alias"),
                "user_ratings_count": ((r.get("user") or {}).get("statistics") or {}).get("ratings_count"),
            })
        return out

    def get_my_review(self, wine_id: int, vintage_id: int) -> dict | None:
        """My own review for a wine's vintage, if any."""
        data = self._get_json(f"/api/users/{self.user_id}/vintages/{vintage_id}/reviews")
        revs = data.get("reviews", [])
        return revs[0] if revs else None

    # ---------- write: rate ----------

    def rate_wine(self, vintage_id: int, rating: float, note: str | None = None) -> dict:
        """Rate a wine (and optionally leave a note).

        rating: 0.0–5.0 in 0.1 steps (Vivino's star scale).
        Returns the created review {id, rating, note, created_at}.
        Re-rating an existing review updates it? No — one review per vintage per user;
        to change a rating, call update_rating() with the returned review id.
        """
        if not (0 <= rating <= 5):
            raise VivinoError("rating must be 0..5")
        body = {"rating": round(rating, 1)}
        if note:
            body["note"] = note
        s, b = self._call(f"/api/vintages/{vintage_id}/reviews", "POST", body)
        return json.loads(b.decode())["review"]

    def update_rating(self, review_id: int, rating: float, note: str | None = None) -> dict:
        """Update an existing review's rating/note (PATCH /api/reviews/{id})."""
        body = {"rating": round(rating, 1)}
        if note is not None:
            body["note"] = note
        s, b = self._call(f"/api/reviews/{review_id}", "PATCH", body)
        return json.loads(b.decode())

    def delete_rating(self, review_id: int) -> bool:
        s, _ = self._call(f"/api/reviews/{review_id}", "DELETE")
        return s in (200, 204)

    def add_to_wishlist(self, vintage_id: int) -> bool:
        s, _ = self._call(f"/api/vintages/{vintage_id}/wishlist", "POST")
        return s in (200, 201)

    # ---------- my history ----------

    def get_my_ratings(self, max_pages: int = 20) -> list[dict]:
        """Full personal rating history, newest first (paginates the activities XHR)."""
        out = []
        cursor = 0
        for _ in range(max_pages):
            s, b = self._call(f"/users/{self.seo_name}/activities?limit=10&start_from_id={cursor}",
                              accept="text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01",
                              referer=f"{BASE}/users/{self.seo_name}")
            if s != 200 or not b:
                break
            html = b.decode(errors="replace")
            ids = []
            for m in re.finditer(r'data-id=\\?"(\d{6,})', html):
                if m.group(1) not in ids:
                    ids.append(m.group(1))
            if not ids:
                break
            for aid in ids:
                i = html.find(f'data-id=\\"{aid}\\"')
                nxts = [html.find(f'data-id=\\"{x}\\"', i + 10) for x in ids]
                nxt = min([c for c in nxts if c > i] + [len(html)])
                seg = html[i:nxt]
                if "rated this wine" not in seg:
                    continue  # skip wishlist/purchase activities
                pcts = [int(x) / 100 for x in re.findall(r'icon-(\d+)-pct', seg)][:5]
                if len(pcts) != 5:
                    continue
                wine = re.search(r'aria-label=\\?"([^"\\\\]+)\\?"', seg)
                href = re.search(r'href=\\?"(/en/[^"\\\\]+/w/\d+)[^"\\\\]*\\?"', seg)
                out.append({
                    "activity_id": aid, "rating": round(sum(pcts), 2),
                    "wine": H.unescape(wine.group(1)) if wine else None,
                    "wine_id": int(href.group(1).rsplit("/w/", 1)[1]) if href else None,
                    "path": href.group(1) if href else None,
                })
            cursor = int(ids[-1])
            if len(ids) < 10:
                break
        # dedupe by wine+rating pairs repeated in feed
        seen = set()
        uniq = []
        for r in out:
            key = (r["wine"], r["rating"])
            if key not in seen:
                seen.add(key)
                uniq.append(r)
        return uniq

    def get_my_wishlist(self) -> list[dict]:
        s, b = self._call(f"/en/users/{self.seo_name}/wishlist", accept="text/html")
        html = b.decode(errors="replace")
        links = list(dict.fromkeys(re.findall(r'href="(/en/[a-z0-9-]+/w/\d+)(?:\?[^"]*)?"', html)))
        out = []
        for href in links:
            i = html.find(href)
            seg = html[i:i + 2500]
            txt = re.sub(r"<[^>]+>", "|", seg)
            txt = re.sub(r"(\s*\|\s*)+", " | ", H.unescape(txt))
            rating = re.search(r"Avg\. rating\s*\|\s*([\d.,]+)", txt)
            out.append({"wine_id": int(href.rsplit("/w/", 1)[1]), "path": href,
                        "name": (re.search(r'aria-label="([^"]+)"', seg) or [None, None])[1],
                        "avg_rating": rating and float(rating.group(1).replace(",", "."))})
        return out

    # ---------- taste profile & fit ----------

    def my_taste_profile(self, ratings: list[dict], enrich: bool = True) -> dict:
        """Aggregate structure/grape/region/style affinities from my rated wines.

        weights: high-rated wines count more (weight = rating).
        """
        from collections import defaultdict
        weights = defaultdict(float)      # "grape:X" / "region:Y" / "style:Z"
        structure = defaultdict(list)     # weighted taste structure values
        for r in ratings:
            w = r["rating"]
            wid, slug = r.get("wine_id"), (r.get("path") or "").split("/w/")[0].replace("/en/", "")
            meta = {}
            if enrich and wid and slug:
                try:
                    meta = self.get_wine(wid, slug)
                    time.sleep(0.3)
                except VivinoError:
                    meta = {}
            r["meta"] = meta
            for grape in meta.get("grapes") or []:
                weights[f"grape:{grape}"] += w
            if meta.get("region"):
                weights[f"region:{meta['region']}"] += w
            if meta.get("style"):
                weights[f"style:{meta['style']}"] += w
            ts = meta.get("taste_structure") or {}
            for k, v in ts.items():
                if v is not None:
                    structure[k].append((v, w))
        profile = {
            "affinities": dict(sorted(weights.items(), key=lambda kv: -kv[1])),
            "structure": {k: round(sum(v * wt for v, wt in xs) / sum(wt for _, wt in xs), 2)
                          for k, xs in structure.items()},
            "n_wines": len(ratings),
        }
        return profile

    def taste_fit(self, wine_id: int, slug: str | None, profile: dict) -> dict:
        """Score how well a wine fits my taste. Returns {score 0-100, breakdown}.

        Components (equal thirds): grape overlap, region overlap, style overlap,
        then a structure-distance term folded into the score.
        """
        wine = self.get_wine(wine_id, slug)
        aff = profile["affinities"]
        max_aff = max(aff.values()) if aff else 1

        def bucket_hit(key_prefix):
            vals = []
            if key_prefix == "grape:":
                vals = [f"grape:{g}" for g in wine.get("grapes") or []]
            elif key_prefix == "region:":
                vals = [f"region:{wine.get('region')}"]
            elif key_prefix == "style:":
                vals = [f"style:{wine.get('style')}"]
            if not vals:
                return None
            return max(aff.get(v, 0) for v in vals) / max_aff

        grape = bucket_hit("grape:")
        region = bucket_hit("region:")
        style = bucket_hit("style:")
        known = [x for x in (grape, region, style) if x is not None]
        affinity_score = (sum(known) / len(known)) if known else 0.0

        # structure distance (0..1, 1 = perfect)
        my = profile.get("structure") or {}
        wt = wine.get("taste_structure") or {}
        dists = []
        for k, mv in my.items():
            wv = wt.get(k)
            if mv is not None and wv is not None:
                dists.append(1 - min(abs(mv - wv) / 5.0, 1))
        structure_score = statistics.mean(dists) if dists else 0.0

        # Blend: structure is the strongest personal signal (I rated these wines),
        # grape next, then region/style. Mean-normalize affinities instead of max
        # so a single 5.0 rating doesn't dominate.
        # Rank-percentile: my affinity vector sorted; how high does this wine's best
        # matching key rank among everything I like? Robust to long-tail fragmenting.
        vals = sorted((x for x in aff.values() if x), reverse=True)
        def percentile(x):
            if x is None or not vals: return 0.0
            better = sum(1 for v in vals if v > x)
            return 1.0 - (better / len(vals))  # 1.0 = my very top affinity
        aff_known = [x for x in (grape, region, style) if x is not None]
        # per-component percentile, then weight grape highest (most transferable signal)
        gp_pct = percentile(aff.get('grape:' + (wine.get('grapes') or [''])[0])) if wine.get('grapes') else None
        rg_pct = percentile(aff.get('region:' + (wine.get('region') or ''))) if wine.get('region') else None
        st_pct = percentile(aff.get('style:' + (wine.get('style') or ''))) if wine.get('style') else None
        comps = [p for p in (gp_pct, rg_pct, st_pct) if p is not None]
        aff_score = (0.5 * gp_pct + 0.3 * rg_pct + 0.2 * st_pct) if (gp_pct is not None and rg_pct is not None and st_pct is not None) else ((sum(comps)/len(comps)) if comps else 0.0)
        if dists and aff_known:
            base = 0.45 * structure_score + 0.55 * aff_score
            if all(x == 0 for x in aff_known):  # nothing in common at all
                base = min(base, 0.35)
            score = round(100 * base)
        elif dists:
            score = round(100 * structure_score)
        elif aff_known:
            score = round(100 * aff_score)
        else:
            score = 0
        return {
            "score": score,
            "grape_fit": None if grape is None else round(grape, 2),
            "region_fit": None if region is None else round(region, 2),
            "style_fit": None if style is None else round(style, 2),
            "structure_fit": round(structure_score, 2) if dists else None,
            "wine": wine,
        }

        # unreachable: legacy equal-thirds code kept below for reference
        parts = [x for x in (grape, region, style, structure_score) if x is not None]
        score = round(100 * (sum(parts) / len(parts)) if parts else 0)
        return {
            "score": score,
            "grape_fit": None if grape is None else round(grape, 2),
            "region_fit": None if region is None else round(region, 2),
            "style_fit": None if style is None else round(style, 2),
            "structure_fit": round(structure_score, 2) if dists else None,
            "wine": wine,
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    c = VivinoClient(cookies_json=sys.argv[1])
    print("user:", c.seo_name, c.user_id)
    res = c.search_wines("catena malbec", limit=3)
    print("search:", json.dumps(res[:2], indent=1)[:400])
