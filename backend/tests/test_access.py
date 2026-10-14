from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import client_at

VIEWER = "100.64.0.7"  # a Tailscale address


def test_loopback_is_admin_and_can_write(db):
    c = client_at("127.0.0.1")
    assert c.get("/api/system/whoami").json() == {"role": "admin"}
    assert c.post("/api/system/autoscan", json={"enabled": False}).status_code == 200
    c.post("/api/system/autoscan", json={"enabled": True})
    assert c.get("/api/system/connect").status_code == 200
    assert client_at("::1").get("/api/system/whoami").json() == {"role": "admin"}


def test_viewer_reads_but_cannot_write_or_connect(db):
    c = client_at(VIEWER)
    assert c.get("/api/system/whoami").json() == {"role": "viewer"}
    assert c.get("/api/system/health").status_code == 200
    assert c.get("/api/config").status_code == 200
    for method, path in [("POST", "/api/scans/run"), ("PUT", "/api/config"), ("POST", "/api/config/reset"),
                         ("POST", "/api/system/autoscan"), ("GET", "/api/system/connect"),
                         ("GET", "/auth/callback?request_token=x"), ("GET", "/api/system/callback?request_token=x")]:
        r = c.request(method, path, json={})
        assert r.status_code == 403 and r.json() == {"detail": "read-only viewer"}, (method, path)


def test_admin_ips_grants_admin(db, monkeypatch):
    from app.core.settings import get_settings
    monkeypatch.setattr(get_settings(), "admin_ips", f"10.0.0.1, {VIEWER}")
    assert client_at(VIEWER).get("/api/system/whoami").json() == {"role": "admin"}


def test_spa_fallback_serves_index(tmp_path):
    from app.main import mount_frontend
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    app = FastAPI()
    mount_frontend(app, tmp_path)
    c = TestClient(app)
    assert c.get("/").text == "<div id=root></div>"
    assert c.get("/signals/live").text == "<div id=root></div>"
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/favicon.svg").text == "<svg/>"
    assert c.get("/api/nope").status_code == 404
    assert c.get("/../../etc/passwd").text == "<div id=root></div>"
