import os, tempfile
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
from main import app

c = TestClient(app)
H = {"Authorization": "Bearer " + c.post("/api/auth/register", json={"username": "alice", "password": "secret1"}).json()["token"]}
mk = lambda **kw: c.post("/api/links", json=kw, headers=H)

def test_invalid_and_unsafe_urls():
    assert mk(url="javascript:alert(1)").status_code == 422
    assert mk(url="ftp://example.com/x").status_code == 422
    assert mk(url="http://127.0.0.1/admin").status_code == 422

def test_redirect_records_click():
    assert mk(url="https://example.com/a", alias="demo1").status_code == 200
    r = c.get("/demo1", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://example.com/a"
    assert c.get("/api/links/demo1/analytics", headers=H).json()["total"] == 1

def test_duplicate_alias():
    mk(url="https://example.com", alias="dupe")
    assert mk(url="https://example.org", alias="dupe").status_code == 409

def test_click_limit():
    mk(url="https://example.com", alias="once", max_clicks=1)
    assert c.get("/once", follow_redirects=False).status_code == 302
    assert c.get("/once", follow_redirects=False).status_code == 410

def test_password_link():
    mk(url="https://example.com/secret", alias="locked", password="pw1234")
    assert c.get("/locked").status_code == 200
    assert c.post("/locked", data={"password": "bad"}).status_code == 401
    assert c.post("/locked", data={"password": "pw1234"}, follow_redirects=False).status_code == 303

def test_past_expiry_rejected():
    assert mk(url="https://example.com", expires_at="2020-01-01T00:00:00Z").status_code == 422

def test_disable_and_takedown():
    mk(url="https://example.com", alias="offme")
    c.post("/api/links/offme/toggle", headers=H)
    assert c.get("/offme", follow_redirects=False).status_code == 410
