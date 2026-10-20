# LinkPulse: URL Shortener & Analytics Platform

**Team:** Code Striker | **College:** Graphic Era Hill University, Haldwani Campus
**Event:** Tech Geeks Hackathon, Round 2

> Short links. Smart insights. Safer sharing.

## Live Links
- **Live project:** PASTE_YOUR_VERCEL_LINK_HERE
- **GitHub repository:** PASTE_YOUR_GITHUB_REPO_LINK_HERE

## Team Members
| Name | Role |
|------|------|
| Dheeraj Singh Gaira | Team Leader |
| Bharat Mulani | Team Member |
| Himangi Kandpal | Team Member |
| Prince Bhandari | Team Member |
| Yogesh Singh Bhoriyal | Team Member |

## Problem Statement
Long URLs are hard to share and hard to measure.
1. Long links are inconvenient for websites, social media and campaigns.
2. Without analytics, we cannot see how many people clicked, where they came from, or which device they used.
3. Link controls like expiry date, click limit and password are not always available together.
4. Teams need a way to disable suspicious links and compare campaign performance.

## Our Solution
LinkPulse is a web application where a user can **create, control, secure and measure** short links from one dashboard.

Main flow: `create a link -> redirect safely -> record the click -> show analytics`

## Features
- **Create:** short links and custom aliases (duplicate aliases are rejected)
- **Control:** expiry date, click limit, password protection, enable/disable a link
- **Measure:** total clicks, clicks per day, referrer, browser and device charts
- **Manage:** campaigns, tags, search, and bulk upload using a CSV file
- **Share:** downloadable QR code for every link
- **Protect:** only http/https URLs allowed, private/internal addresses blocked, rate limiting, admin takedown
- **Privacy:** we do not store IP addresses; bots are redirected but not counted
- **Login:** register and login system (the first account becomes admin)

## Tech Stack
| Part | Technology |
|------|-----------|
| Frontend | React + Vite, Recharts (charts) |
| Backend | Python + FastAPI |
| Database | SQLite (local), PostgreSQL (deployed) |
| Security | Input validation, password hashing, JWT login, rate limiting |
| Deployment | Vercel (frontend), Render (backend) |

## How It Works
1. The user logs in and pastes a long URL.
2. The backend checks the URL is valid and saves it with a short code in the database.
3. When someone opens the short link, the backend checks if the link is active, not expired, not over its click limit, and asks for the password if one is set.
4. If everything is fine, it records the click (time, referrer, browser, device) and redirects to the original URL.
5. The dashboard reads the saved clicks and shows charts.

If a link is invalid, expired, disabled or over its limit, an error page is shown instead of redirecting.

## Project Structure
```
linkpulse/
├── backend/
│   ├── main.py            # API, redirect logic, analytics
│   ├── test_app.py        # automated tests
│   └── requirements.txt
├── frontend/
│   ├── src/App.jsx        # dashboard and forms
│   ├── src/api.js         # talks to the backend
│   └── src/styles.css
└── README.md
```

## Setup Instructions (run on your own computer)
You need **Python 3.10+** and **Node.js 18+** installed.

### 1. Backend
```
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```
(On Mac/Linux use `.venv/bin/python` instead of `.venv\Scripts\python`.)
API docs open at http://localhost:8000/docs

### 2. Frontend (open a second terminal)
```
cd frontend
npm install
npm run dev
```
Open http://localhost:5173, create an account and start making links.

### 3. Run tests
```
cd backend
.venv\Scripts\python -m pip install pytest httpx
.venv\Scripts\python -m pytest -q
```

### Environment variables (for deployment)
Copy `backend/.env.example` and set your own values. Never upload a real `.env` file to GitHub.
- Backend: `SECRET_KEY`, `BASE_URL`, `FRONTEND_ORIGIN`, `DATABASE_URL`
- Frontend: `VITE_API_URL` (the backend URL)

## Screenshots
Add your screenshots in a `screenshots` folder and update the file names below.

| Login | Dashboard |
|-------|-----------|
| ![Login](screenshots/login.png) | ![Dashboard](screenshots/dashboard.png) |

| Link Analytics | QR Code |
|----------------|---------|
| ![Analytics](screenshots/analytics.png) | ![QR](screenshots/qr.png) |

## Edge Cases Handled
- Invalid or unsafe URL: rejected
- Duplicate alias: asked to choose another
- Expired link or click limit reached: blocked with a clear message
- Bot or repeated clicks: rate limits added and bots are not counted

## Future Improvements
- Team roles (multiple users in one workspace)
- Downloadable reports
- Better abuse and bot detection

## What We Learned
We learned how a URL shortener works, how frontend and backend talk using an API, how a database stores links and clicks, and how to think about security and privacy.
