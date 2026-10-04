"""The SPA's cache headers. On Modal the files' mtime is 0, so without them caches keep an old index.html (Last-Modified
1970, and the same ETag whenever the page keeps its size) that points at assets the new deploy no longer has."""
import pytest

from ssi.api.app import WEB_DIST

pytestmark = pytest.mark.skipif(not (WEB_DIST / "index.html").exists(), reason="needs the built SPA (cd web && npm run build)")


@pytest.mark.parametrize("path", ["/", "/projects/abc", "/favicon.svg"])
def test_page_and_unhashed_files_are_never_stored(client, path):
    r = client().get(path)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"


def test_hashed_assets_are_kept_for_good(client):
    asset = next((WEB_DIST / "assets").glob("index-*.js"))
    r = client().get(f"/assets/{asset.name}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_missing_asset_is_not_cached(client):
    r = client().get("/assets/index-doesnotexist.js")
    assert r.status_code == 404
    assert "immutable" not in r.headers.get("cache-control", "")
