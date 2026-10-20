"""LinkPulse backend: URL shortener + analytics (FastAPI + SQLAlchemy)."""
import os, io, csv, re, time, secrets, string, hashlib, hmac, ipaddress
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from typing import Optional

import jwt, qrcode
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ---------- config ----------
SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me-please-use-a-long-random-key")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
FRONTEND = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./linkpulse.db")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

def now():  # naive UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ---------- models ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(30), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, index=True, nullable=False)
    target = Column(String(2048), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    campaign = Column(String(60), index=True)
    tags = Column(String(200))
    password_hash = Column(String)
    expires_at = Column(DateTime)
    max_clicks = Column(Integer)
    click_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)   # owner switch
    takedown = Column(Boolean, default=False, nullable=False)   # admin switch
    created_at = Column(DateTime, default=now)
    owner = relationship("User")

class Click(Base):
    """Privacy-conscious: no IP address, no full user-agent, only referrer host."""
    __tablename__ = "clicks"
    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("links.id"), index=True, nullable=False)
    ts = Column(DateTime, default=now, index=True)
    referrer = Column(String(100))
    browser = Column(String(20))
    device = Column(String(20))

Base.metadata.create_all(engine)

# ---------- helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 100_000).hex()

def check_pw(p, h):
    return bool(h) and hmac.compare_digest(hash_pw(p, h.split("$")[0]), h)

_hits = {}
def limit(request: Request, key: str, n: int, per: int = 60):
    ip = request.client.host if request.client else "unknown"
    t = time.time()
    q = [x for x in _hits.get((key, ip), []) if t - x < per]
    if len(q) >= n:
        raise HTTPException(429, "Too many requests. Please slow down.")
    q.append(t)
    _hits[(key, ip)] = q

bearer = HTTPBearer(auto_error=False)
def current_user(creds=Depends(bearer), db=Depends(get_db)):
    if not creds:
        raise HTTPException(401, "Please log in")
    try:
        uid = int(jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Session expired, please log in again")
    u = db.get(User, uid)
    if not u:
        raise HTTPException(401, "User not found")
    return u

def token_for(u):
    return jwt.encode({"sub": str(u.id), "exp": datetime.now(timezone.utc) + timedelta(days=7)}, SECRET, algorithm="HS256")

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED = {"api", "docs", "redoc", "health", "admin", "static"}

def validate_url(u):
    u = (u or "").strip()
    if len(u) > 2048:
        raise HTTPException(422, "URL is too long (max 2048 characters)")
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise HTTPException(422, "Enter a valid URL starting with http:// or https://")
    h = p.hostname.lower()
    if h == "localhost" or h.endswith(".local") or h == urlparse(BASE_URL).hostname:
        raise HTTPException(422, "This destination is not allowed")
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(422, "Private or internal addresses are not allowed")
    except ValueError:
        pass  # hostname, not a literal IP
    return u

def parse_ua(ua):
    s = ua.lower()
    if not s or re.search(r"bot|crawl|spider|slurp|preview|facebookexternalhit", s):
        return "Other", "Bot"
    if "edg/" in s: b = "Edge"
    elif "opr/" in s or "opera" in s: b = "Opera"
    elif "firefox" in s: b = "Firefox"
    elif "chrome" in s or "crios" in s: b = "Chrome"
    elif "safari" in s: b = "Safari"
    else: b = "Other"
    d = "Tablet" if ("ipad" in s or "tablet" in s) else "Mobile" if re.search(r"mobi|android|iphone", s) else "Desktop"
    return b, d

def status_of(l):
    if l.takedown: return "taken_down"
    if not l.is_active: return "disabled"
    if l.expires_at and l.expires_at <= now(): return "expired"
    if l.max_clicks and l.click_count >= l.max_clicks: return "limit_reached"
    return "active"

def out(l):
    return dict(code=l.code, short_url=f"{BASE_URL}/{l.code}", target=l.target, campaign=l.campaign,
                tags=l.tags, protected=bool(l.password_hash), expires_at=l.expires_at,
                max_clicks=l.max_clicks, click_count=l.click_count, is_active=l.is_active,
                takedown=l.takedown, created_at=l.created_at, status=status_of(l),
                owner=l.owner.username if l.owner else None)

def gen_code():
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))

# ---------- schemas ----------
class AuthIn(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=100)

class LinkIn(BaseModel):
    url: str
    alias: Optional[str] = None
    campaign: Optional[str] = Field(None, max_length=60)
    tags: Optional[str] = Field(None, max_length=200)
    password: Optional[str] = Field(None, max_length=100)
    expires_at: Optional[datetime] = None
    max_clicks: Optional[int] = Field(None, ge=1)

def make_link(db, user, d: LinkIn):
    url = validate_url(d.url)
    alias = (d.alias or "").strip()
    if alias:
        if not CODE_RE.match(alias) or alias.lower() in RESERVED:
            raise HTTPException(422, "Alias must be 3-32 letters, numbers, - or _ (and not a reserved word)")
        if db.query(Link).filter(func.lower(Link.code) == alias.lower()).first():
            raise HTTPException(409, "That alias is already taken. Try another.")
        code = alias
    else:
        code = gen_code()
        while db.query(Link).filter_by(code=code).first():
            code = gen_code()
    exp = d.expires_at
    if exp is not None:
        if exp.tzinfo:
            exp = exp.astimezone(timezone.utc).replace(tzinfo=None)
        if exp <= now():
            raise HTTPException(422, "Expiry must be in the future")
    l = Link(code=code, target=url, owner_id=user.id, campaign=(d.campaign or "").strip() or None,
             tags=(d.tags or "").strip() or None, password_hash=hash_pw(d.password) if d.password else None,
             expires_at=exp, max_clicks=d.max_clicks)
    db.add(l); db.commit(); db.refresh(l)
    return l

def get_owned(db, user, code):
    l = db.query(Link).filter_by(code=code).first()
    if not l or (l.owner_id != user.id and not user.is_admin):
        raise HTTPException(404, "Link not found")
    return l

def stats(db, *conds):
    def base(*cols):
        return db.query(*cols).select_from(Click).join(Link, Link.id == Click.link_id).filter(*conds)
    start = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
    per_day = {str(d): c for d, c in base(func.date(Click.ts), func.count(Click.id))
               .filter(Click.ts >= start).group_by(func.date(Click.ts)).all()}
    series = []
    for i in range(30):
        d = (start + timedelta(days=i)).date().isoformat()
        series.append({"date": d[5:], "clicks": per_day.get(d, 0)})
    def top(col):
        rows = base(col, func.count(Click.id)).group_by(col).order_by(func.count(Click.id).desc()).limit(8).all()
        return [{"name": n or "Unknown", "value": c} for n, c in rows]
    return {"total": base(func.count(Click.id)).scalar() or 0, "series": series,
            "referrers": top(Click.referrer), "browsers": top(Click.browser), "devices": top(Click.device)}

# ---------- app ----------
app = FastAPI(title="LinkPulse API")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND, "http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"ok": True}

# ----- auth -----
@app.post("/api/auth/register")
def register(d: AuthIn, request: Request, db=Depends(get_db)):
    limit(request, "auth", 10)
    if db.query(User).filter(func.lower(User.username) == d.username.lower()).first():
        raise HTTPException(409, "Username already taken")
    first = db.query(User).count() == 0  # first account becomes admin
    u = User(username=d.username, password_hash=hash_pw(d.password), is_admin=first)
    db.add(u); db.commit(); db.refresh(u)
    return {"token": token_for(u)}

@app.post("/api/auth/login")
def login(d: AuthIn, request: Request, db=Depends(get_db)):
    limit(request, "auth", 10)
    u = db.query(User).filter(func.lower(User.username) == d.username.lower()).first()
    if not u or not check_pw(d.password, u.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return {"token": token_for(u)}

@app.get("/api/me")
def me(u=Depends(current_user)):
    return {"username": u.username, "is_admin": u.is_admin}

# ----- links -----
@app.post("/api/links")
def create_link(d: LinkIn, request: Request, u=Depends(current_user), db=Depends(get_db)):
    limit(request, "create", 30)
    return out(make_link(db, u, d))

@app.get("/api/links")
def list_links(q: str = "", campaign: str = "", u=Depends(current_user), db=Depends(get_db)):
    qs = db.query(Link).filter(Link.owner_id == u.id)
    if q:
        qs = qs.filter(Link.code.ilike(f"%{q}%") | Link.target.ilike(f"%{q}%") | Link.tags.ilike(f"%{q}%"))
    if campaign:
        qs = qs.filter(Link.campaign == campaign)
    return [out(l) for l in qs.order_by(Link.id.desc()).limit(500).all()]

@app.post("/api/links/bulk")
def bulk(request: Request, file: UploadFile = File(...), u=Depends(current_user), db=Depends(get_db)):
    limit(request, "bulk", 5)
    text = file.file.read(1_000_000).decode("utf-8-sig", errors="ignore")
    rows = list(csv.DictReader(io.StringIO(text)))[:200]
    created, errors = [], []
    for i, r in enumerate(rows, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        try:
            l = make_link(db, u, LinkIn(url=r.get("url", ""), alias=r.get("alias"),
                                        campaign=r.get("campaign"), tags=r.get("tags")))
            created.append(out(l))
        except HTTPException as e:
            errors.append({"row": i, "error": e.detail})
    return {"created": created, "errors": errors}

@app.post("/api/links/{code}/toggle")
def toggle(code: str, u=Depends(current_user), db=Depends(get_db)):
    l = get_owned(db, u, code)
    if l.takedown and not u.is_admin:
        raise HTTPException(403, "This link was disabled by an administrator")
    l.is_active = not l.is_active
    db.commit()
    return out(l)

@app.delete("/api/links/{code}")
def delete_link(code: str, u=Depends(current_user), db=Depends(get_db)):
    l = get_owned(db, u, code)
    db.query(Click).filter_by(link_id=l.id).delete()
    db.delete(l); db.commit()
    return {"deleted": code}

@app.get("/api/links/{code}/qr")
def qr(code: str, download: int = 0, db=Depends(get_db)):
    l = db.query(Link).filter_by(code=code).first()
    if not l:
        raise HTTPException(404, "Link not found")
    buf = io.BytesIO()
    qrcode.make(f"{BASE_URL}/{l.code}").save(buf, format="PNG")
    buf.seek(0)
    disp = "attachment" if download else "inline"
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Content-Disposition": f'{disp}; filename="{l.code}.png"'})

@app.get("/api/links/{code}/analytics")
def link_analytics(code: str, u=Depends(current_user), db=Depends(get_db)):
    l = get_owned(db, u, code)
    return stats(db, Click.link_id == l.id)

@app.get("/api/analytics/overview")
def overview(u=Depends(current_user), db=Depends(get_db)):
    mine = Link.owner_id == u.id
    links = db.query(Link).filter(mine).all()
    camps = (db.query(Link.campaign, func.count(Link.id), func.coalesce(func.sum(Link.click_count), 0))
             .filter(mine).group_by(Link.campaign).all())
    s = stats(db, mine)
    return {"links": len(links), "active": sum(status_of(l) == "active" for l in links),
            "clicks": sum(l.click_count for l in links), "series": s["series"],
            "campaigns": [{"campaign": c or "No campaign", "links": n, "clicks": int(k)} for c, n, k in camps],
            "top": [out(l) for l in sorted(links, key=lambda x: -x.click_count)[:5]]}

# ----- admin -----
def admin_only(u=Depends(current_user)):
    if not u.is_admin:
        raise HTTPException(403, "Admins only")
    return u

@app.get("/api/admin/links")
def admin_links(u=Depends(admin_only), db=Depends(get_db)):
    return [out(l) for l in db.query(Link).order_by(Link.id.desc()).limit(500).all()]

@app.post("/api/admin/links/{code}/takedown")
def takedown(code: str, u=Depends(admin_only), db=Depends(get_db)):
    l = db.query(Link).filter_by(code=code).first()
    if not l:
        raise HTTPException(404, "Link not found")
    l.takedown = not l.takedown
    db.commit()
    return out(l)

# ----- public redirect (keep LAST so it never shadows /api routes) -----
def page(title, msg, code=200):
    return HTMLResponse(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title}</title><body style="font-family:system-ui;display:grid;place-items:center;min-height:100vh;margin:0;background:#f5f7fb">
<div style="background:#fff;padding:32px 40px;border-radius:12px;max-width:420px;text-align:center;box-shadow:0 2px 12px #0001">
<h2 style="margin:0 0 8px">{title}</h2><p style="color:#556">{msg}</p></div>""", status_code=code)

def lock_page(code, err="", status=200):
    e = f'<p style="color:#c0392b">{err}</p>' if err else ""
    return HTMLResponse(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Protected link</title><body style="font-family:system-ui;display:grid;place-items:center;min-height:100vh;margin:0;background:#f5f7fb">
<form method=post action="/{code}" style="background:#fff;padding:32px 40px;border-radius:12px;box-shadow:0 2px 12px #0001;text-align:center">
<h2 style="margin:0 0 8px">This link is protected</h2><p style="color:#556">Enter the password to continue.</p>{e}
<input type=password name=password placeholder=Password required autofocus style="padding:10px;width:100%;box-sizing:border-box;margin-bottom:12px">
<button style="padding:10px 20px;background:#2563eb;color:#fff;border:0;border-radius:6px;cursor:pointer">Open link</button></form>""", status_code=status)

BLOCK_MSG = {"taken_down": "This link was removed by an administrator.", "disabled": "This link has been disabled.",
             "expired": "This link has expired.", "limit_reached": "This link has reached its click limit."}

def record(db, link, request):
    """Count a click atomically (respects max_clicks). Bots are redirected but not counted."""
    browser, device = parse_ua(request.headers.get("user-agent", ""))
    if device == "Bot":
        return True
    q = db.query(Link).filter(Link.id == link.id)
    if link.max_clicks:
        q = q.filter(Link.click_count < link.max_clicks)
    if not q.update({Link.click_count: Link.click_count + 1}):
        db.rollback()
        return False
    ref = (urlparse(request.headers.get("referer", "")).hostname or "Direct")[:100]
    db.add(Click(link_id=link.id, browser=browser, device=device, referrer=ref))
    db.commit()
    return True

@app.get("/{code}")
def go(code: str, request: Request, db=Depends(get_db)):
    l = db.query(Link).filter_by(code=code).first()
    if not l:
        return page("Link not found", "This short link does not exist.", 404)
    s = status_of(l)
    if s != "active":
        return page("Link unavailable", BLOCK_MSG[s], 410)
    if l.password_hash:
        return lock_page(code)
    if not record(db, l, request):
        return page("Link unavailable", BLOCK_MSG["limit_reached"], 410)
    return RedirectResponse(l.target, status_code=302)  # 302 so browsers don't cache and skip counting

@app.post("/{code}")
def unlock(code: str, request: Request, password: str = Form(...), db=Depends(get_db)):
    limit(request, "unlock", 10)
    l = db.query(Link).filter_by(code=code).first()
    if not l:
        return page("Link not found", "This short link does not exist.", 404)
    s = status_of(l)
    if s != "active":
        return page("Link unavailable", BLOCK_MSG[s], 410)
    if not check_pw(password, l.password_hash):
        return lock_page(code, "Wrong password", 401)
    if not record(db, l, request):
        return page("Link unavailable", BLOCK_MSG["limit_reached"], 410)
    return RedirectResponse(l.target, status_code=303)
