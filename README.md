<div align="center">

# 🎌 ChibiBytes
### High-Performance AI-Powered Anime & Media Discovery Engine

[![Production Deployment](https://img.shields.io/badge/Production-chibibytes.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://chibibytes.vercel.app/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask_2.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Neon Database](https://img.shields.io/badge/Database-Neon_PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Groq LPU](https://img.shields.io/badge/LLM_Engine-Groq_LPU-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://groq.com/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<p align="center">
  A modern, production-grade media discovery platform engineered with Flask modular blueprints, Neon PostgreSQL cloud clustering, in-memory catalog caching, and a low-latency conversational AI engine powered by Groq and Google Gemini.
</p>

[**Explore Live Application →**](https://chibibytes.vercel.app/)

</div>

---

## 📸 Interface Preview

<div align="center">

| 💬 Conversational AI Assistant | 📑 Synchronous Watchlist Engine |
| :---: | :---: |
| ![AI Assistant Chat](Images/Chat.png) | ![Watchlist Management](Images/Watchlist.png) |

</div>

---

## ⚡ Engineering & Architectural Highlights

- **Ultra-Low Latency AI Engine (~150ms)**: Dual-layer LLM pipeline utilizing Groq LPU inference (`qwen/qwen3.8-27b`) with automatic failover to Google Gemini 1.5 Flash. Intent detection dynamically separates greetings, queries, recommendations, and card requests.
- **In-Memory Catalog Cache (< 0.1ms)**: Pre-warmed catalog cache in server memory eliminating repetitive database queries across anime, movie, and genre listings.
- **Cloud-Native PostgreSQL (Neon)**: Fully standardized on Neon PostgreSQL with resilient connection pooling (`pool_size=10`, `max_overflow=20`, `pool_recycle=300`) to prevent cold-start bottlenecks.
- **Transparent Gzip Compression**: Custom WSGI HTTP middleware automatically compresses response bodies over 500 bytes, yielding an **80–88% reduction in transfer payloads**.
- **Synchronous Watchlist System**: Instant bookmarking and list updates with optimistic UI updates and idempotent backend synchronization.
- **Modular Flask Blueprint Architecture**: Decoupled domain separation across Authentication (`auth_bp`), Media Catalog (`catalog_bp`), and Watchlist Operations (`watchlist_bp`).

---

## 🏛️ System Architecture

```mermaid
graph TD
    Client["Client Browser (Glassmorphism UI / Vanilla JS)"]
    Edge["Vercel Edge Network / Serverless Runtime"]
    Flask["Flask Application Gateway (app.py)"]

    subgraph Blueprints ["Modular Blueprint Layer"]
        AuthBP["Auth Blueprint (PBKDF2 Password Hashing)"]
        CatalogBP["Catalog Blueprint (Browse, Search, Filter)"]
        WatchlistBP["Watchlist Blueprint (CRUD & Synchronization)"]
    end

    subgraph CachingAndData ["Data & Storage Layer"]
        MemCache["In-Memory Catalog Cache (<0.1ms)"]
        NeonDB[("Neon Cloud PostgreSQL Cluster")]
    end

    subgraph AIEngine ["Intelligent Assistant Pipeline"]
        IntentRouter["Intent Classifier & Sanitizer"]
        Groq["Groq LPU (Primary: ~150ms)"]
        Gemini["Google Gemini (Fallback)"]
    end

    Client -->|HTTPS / Gzip Encoded| Edge
    Edge --> Flask
    Flask --> AuthBP
    Flask --> CatalogBP
    Flask --> WatchlistBP

    CatalogBP <--> MemCache
    AuthBP <--> NeonDB
    WatchlistBP <--> NeonDB
    CatalogBP <--> NeonDB

    CatalogBP --> IntentRouter
    IntentRouter --> Groq
    IntentRouter -.->|Fallback| Gemini
    Groq --> MemCache
```

---

## 🛠️ Technology Stack

| Domain | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+, Flask 2.3.3 | Microframework with modular blueprint architecture |
| **Database** | Neon Cloud PostgreSQL | Managed serverless PostgreSQL with ACID compliance |
| **ORM** | SQLAlchemy 2.0+ & Flask-SQLAlchemy | Declarative data models with connection pool recycling |
| **AI / LLM** | Groq LPU & Google Gemini SDK | High-speed structured dialogue and media intelligence |
| **Compression** | Gzip Middleware | Dynamic HTTP response body compression |
| **Frontend** | Modern Vanilla CSS & JavaScript | Zero-framework glassmorphism, responsive CSS grid |
| **Hosting** | Vercel Serverless | Python serverless function deployment with zero cold starts |

---

## 📁 Repository Structure

```text
ChibiBytes/
├── api/
│   └── index.py            # Vercel serverless gateway
├── app.py                  # Application entrypoint & HTTP compression middleware
├── chatbot.py              # Groq & Gemini hybrid AI assistant engine
├── database.py             # Neon PostgreSQL connection pooling & data migrations
├── models.py               # Declarative SQLAlchemy ORM models
├── requirements.txt        # Production dependencies
├── vercel.json             # Vercel deployment configuration
├── blueprints/
│   ├── auth.py             # Authentication, session state & user RBAC
│   ├── catalog.py          # Media catalog, genre indexing & reviews
│   └── watchlist.py        # Watchlist persistence & bookmark handlers
├── services/
│   ├── anime_service.py    # Jikan REST API data ingest & background sync
│   └── movie_service.py    # Movie catalog ingestion & trailer bindings
├── templates/              # Jinja2 frontend views (Anime, Movies, Chat, Trending)
└── Images/                 # Showcase screenshots & application previews
```

---

## 📡 API Specification

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/chat` | Send prompt to AI Assistant (Groq/Gemini) | No |
| `POST` | `/api/chat/clear` | Clear user chat history | Yes |
| `GET` | `/api/watchlist` | Retrieve user watchlist items | Yes |
| `POST` | `/api/watchlist/add` | Add an anime/movie to user watchlist | Yes |
| `POST` | `/api/watchlist/remove` | Remove item from user watchlist | Yes |
| `POST` | `/api/reviews` | Submit user rating and review | Yes |
| `GET` | `/api/trending` | Fetch ranked trending media titles | No |

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

### 4. Run the Development Server
```bash
python app.py
```
Access the application at `http://localhost:5002`.

---

## 🌐 Production Deployment (Vercel)

The application is configured out-of-the-box for **Vercel Serverless Functions**.

1. Link the project and set environment variables:
   ```bash
   vercel link --project chibibytes
   vercel env add DATABASE_URL production
   vercel env add SECRET_KEY production
   vercel env add GROQ_API_KEY production
   ```
2. Deploy to production:
   ```bash
   vercel deploy --prod
   ```
3. Live production domain: **[https://chibibytes.vercel.app](https://chibibytes.vercel.app)**

---

## 📄 License

Distributed under the [MIT License](LICENSE).
