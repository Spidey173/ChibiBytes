<div align="center">

# 🎌 ChibiBytes
### Full-Stack Anime & Movie Discovery Web Application with AI Assistant

[![Production Deployment](https://img.shields.io/badge/Production-chibibytes.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://chibibytes.vercel.app/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask_2.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL_(Neon)-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![AI Assistant](https://img.shields.io/badge/LLM-Groq_%7C_Gemini-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://groq.com/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<p align="center">
  A responsive media discovery web application built with Flask modular blueprints, PostgreSQL (Neon Cloud) via SQLAlchemy, in-memory catalog caching, interactive cinema-style trailer playback, and a conversational AI companion using Groq and Google Gemini.
</p>

[**Explore Live Application →**](https://chibibytes.vercel.app/)

</div>

---

## 📸 Interface Preview

<div align="center">

| 💬 Conversational AI Assistant | 📑 Personal Watchlist Management |
| :---: | :---: |
| ![AI Assistant Chat](Images/Chat.png) | ![Watchlist Management](Images/Watchlist.png) |

</div>

---

## ⚡ Core Features & Engineering Highlights

- **Dual-Provider AI Assistant**: Integrated chatbot that queries Groq (Llama / open models) for fast generation and gracefully falls back to Google Gemini. Features rule-based intent routing to serve instant recommendation cards, answers, or conversational replies.
- **In-Memory Catalog Caching**: Pre-loads catalog data into memory to minimize redundant database round-trips for frequently requested anime, movie, and genre listings.
- **PostgreSQL Database with SQLAlchemy**: Built on PostgreSQL (hosted on Neon) using SQLAlchemy ORM models. Includes connection pooling (`pool_pre_ping`, `pool_recycle`), schema migrations, and relational cascading for users, watchlists, reviews, and chat logs.
- **Unified Trailer Player**: Embedded YouTube modal player across trending, anime, movie, and watchlist cards with responsive viewport centering.
- **Modular Blueprint Architecture**: Clean separation of concerns across Authentication (`auth`), Media Catalog (`catalog`), and Watchlist Operations (`watchlist`).
- **HTTP Response Compression**: Lightweight gzip middleware applied to response payloads over 500 bytes to reduce network transfer size.
- **CI/CD & Automated Testing**: Automated test suite executing against a containerized PostgreSQL service in GitHub Actions CI with an isolated SQLite fallback for local test runs.

---

## 🏛️ System Architecture

```mermaid
graph TD
    Client["Client Browser (Responsive HTML5 / Vanilla CSS & JS)"]
    Edge["Vercel Serverless Hosting / Local Flask Server"]
    Flask["Flask Application (app.py)"]

    subgraph Blueprints ["Modular Blueprint Layer"]
        AuthBP["Auth Blueprint (PBKDF2 Password Hashing, Session State)"]
        CatalogBP["Catalog Blueprint (Browse, Search, Genres, Reviews)"]
        WatchlistBP["Watchlist Blueprint (Add, Remove, Toggle Favorite)"]
    end

    subgraph DataLayer ["Data & Storage Layer"]
        MemCache["In-Memory Catalog Cache"]
        PostgresDB[("PostgreSQL Database (Neon)")]
    end

    subgraph AIAssistant ["AI Assistant Pipeline"]
        IntentRouter["Intent Classifier & Keyword Matching"]
        Groq["Groq API (Primary)"]
        Gemini["Google Gemini API (Fallback)"]
    end

    Client -->|HTTP / JSON Requests| Edge
    Edge --> Flask
    Flask --> AuthBP
    Flask --> CatalogBP
    Flask --> WatchlistBP

    CatalogBP <--> MemCache
    AuthBP <--> PostgresDB
    WatchlistBP <--> PostgresDB
    CatalogBP <--> PostgresDB

    CatalogBP --> IntentRouter
    IntentRouter --> Groq
    IntentRouter -.->|Fallback| Gemini
    IntentRouter --> MemCache
```

---

## 🛠️ Technology Stack

| Domain | Technology | Usage in Project |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+, Flask 2.3.3 | REST APIs, Jinja2 rendering, and modular blueprints |
| **Database** | PostgreSQL (Neon Cloud) | Persistent storage for users, catalog, watchlists, and reviews |
| **ORM** | SQLAlchemy 2.0+ / Flask-SQLAlchemy | Declarative data modeling, relations, and migrations |
| **AI / LLM** | Groq API & Google Gemini SDK | Natural language anime queries, recommendations, and conversational responses |
| **Frontend** | Vanilla HTML5, CSS3, JavaScript | Custom responsive UI, modal dialogs, and asynchronous fetch requests |
| **Testing** | Python `unittest` | End-to-end route, database constraint, and authentication tests |
| **CI / CD** | GitHub Actions | Automated test pipeline with PostgreSQL container service |
| **Deployment** | Vercel | Serverless web deployment |

---

## 📁 Repository Structure

```text
ChibiBytes/
├── .github/workflows/
│   └── ci.yml              # GitHub Actions CI workflow (PostgreSQL service + tests)
├── api/
│   └── index.py            # Vercel serverless function entrypoint
├── blueprints/
│   ├── auth.py             # User registration, login, logout & session checks
│   ├── catalog.py          # Media catalog, search, genre filtering & reviews
│   └── watchlist.py        # Watchlist CRUD operations & favorite toggles
├── services/
│   └── anime_service.py    # Jikan MAL API ingestion & background catalog sync
├── templates/              # Jinja2 frontend HTML templates
├── app.py                  # Flask application initialization & gzip middleware
├── chatbot.py              # AI assistant logic with Groq and Gemini integrations
├── database.py             # Database engine setup, pooling & seed data
├── models.py               # Declarative SQLAlchemy models (User, Anime, Movie, Watchlist)
├── test_app.py             # Automated unit and integration test suite
├── vercel.json             # Vercel deployment routing configuration
├── requirements.txt        # Python package dependencies
└── README.md               # Project documentation
```

---

## 📡 Key API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/chat` | Send prompt to AI Assistant (Groq/Gemini) | No |
| `GET` | `/api/chat/history` | Retrieve recent user conversation history | Yes |
| `POST` | `/api/chat/clear` | Clear user chat history | Yes |
| `GET` | `/get_watchlist` | Retrieve authenticated user's watchlist | Yes |
| `POST` | `/add_to_watchlist` | Add an anime or movie to user watchlist | Yes |
| `POST` | `/toggle_favorite/<id>` | Toggle favorite flag on a watchlist item | Yes |
| `DELETE`| `/remove_from_watchlist/<id>` | Remove item by ID from user watchlist | Yes |
| `GET` | `/api/anime/search` | Search anime catalog by keyword | No |
| `GET` | `/api/anime/featured` | Fetch featured anime title | No |
| `GET/POST`| `/api/reviews` | Retrieve or submit user review for a title | Read: No / Post: Yes |

---

## 🚀 Local Development Setup

### 1. Clone Repository
```bash
git clone https://github.com/Spidey173/ChibiBytes.git
cd ChibiBytes
```

### 2. Configure Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root:
```env
DATABASE_URL=postgresql://user:password@ep-soft-cloud.neon.tech/neondb?sslmode=require
SECRET_KEY=your_secure_random_key_here
GROQ_API_KEY=gsk_your_groq_api_key_here
GEMINI_API_KEY=AIzaSy_your_gemini_key_here
```
*(Note: If `DATABASE_URL` is omitted during local unit testing, tests automatically fall back to a local SQLite test database).*

### 4. Run the Development Server
```bash
python app.py
```
Access the application at `http://localhost:5002`.

### 5. Run the Automated Test Suite
```bash
python3 -m unittest discover -v
```

---

## 🌐 Production Deployment (Vercel)

The application includes serverless routing configured in [vercel.json](file:///Users/spidey./Downloads/ChibiBytes-main/vercel.json) and [api/index.py](file:///Users/spidey./Downloads/ChibiBytes-main/api/index.py).

1. Link project and configure environment variables in the Vercel dashboard or CLI:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `GROQ_API_KEY` (optional for primary AI responses)
   - `GEMINI_API_KEY` (optional fallback)
2. Deploy:
   ```bash
   vercel deploy --prod
   ```
3. Live production URL: **[https://chibibytes.vercel.app](https://chibibytes.vercel.app)**

---

## 📄 License

Distributed under the [MIT License](LICENSE).
