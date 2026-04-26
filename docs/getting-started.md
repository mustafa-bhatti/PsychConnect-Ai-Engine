# Getting Started

This guide walks you through setting up the PsychConnect AI Engine for local development.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required for `match` syntax and type unions |
| pip | Latest | Comes with Python |
| Google Cloud account | — | With Vertex AI API enabled |
| Service Account JSON | — | With `aiplatform.user` role |
| Supabase project | — | Shared with the PsychConnect frontend |
| HTP Manual PDF | — | `book_htp_combined.pdf` placed in `resources/` |

---

## 1. Clone the Repository

```bash
git clone https://github.com/mustafa-bhatti/PsychConnect-Ai-Engine.git
cd PsychConnect-Ai-Engine
```

## 2. Create a Virtual Environment

```bash
python -m venv venv

# Activate:
# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (CMD)
venv\Scripts\activate.bat
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### Dependencies Overview

| Package | Purpose |
|---------|---------|
| `fastapi` | HTTP framework |
| `uvicorn` | ASGI server |
| `google-genai` | Vertex AI / Gemini SDK |
| `google-auth` | Service account authentication |
| `pydantic` | Data validation and schemas |
| `supabase` | Database client (PostgreSQL) |
| `httpx` | Async HTTP client (image downloads) |
| `python-dotenv` | `.env` file loading |
| `python-multipart` | Multipart form parsing |

## 4. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Fill in the required values:

```env
# Google Cloud / Vertex AI
VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=psychconnect-key.json

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key

# Resources
HTP_MANUAL_PATH=resources/book_htp_combined.pdf

# CORS (comma-separated origins)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

> **Security:** Never commit `.env`, `psychconnect-key.json`, or any service account credentials. These are already listed in `.gitignore`.

## 5. Place Required Resources

```
resources/
├── book_htp_combined.pdf    ← HTP manual (REQUIRED for pipeline)
├── test_house.png           ← Test images (optional, for test_local.py)
├── test_tree.png
└── test_person.png
```

The HTP manual PDF is loaded into memory at startup and used as the interpretive reference for all AI calls. Without it, the service will **not start**.

## 6. Run the Service

### Local Development Server

```bash
uvicorn main:app --reload --port 8000
```

The service will:
1. Validate all required environment variables
2. Initialize the Vertex AI client
3. Load the HTP manual PDF into memory
4. Create context caches on Vertex AI (if possible)
5. Start the background assessment worker

### Verify It's Running

```bash
# Health check
curl http://localhost:8000/health

# Interactive API docs
open http://localhost:8000/docs
```

Expected health response:

```json
{
  "status": "ok",
  "service": "htp-assessment",
  "version": "2.1.0",
  "queue_size": 0
}
```

## 7. Run a Local Test (Optional)

If you have test images in `resources/`, you can test the full pipeline without a server:

```bash
python test_local.py
```

This runs the complete 3-phase assessment pipeline against test images and saves the result to `test_output.json`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `FileNotFoundError: Service account JSON not found` | Set `GOOGLE_APPLICATION_CREDENTIALS` to the correct path in `.env` |
| `FileNotFoundError: HTP manual not found` | Place `book_htp_combined.pdf` in `resources/` |
| `Missing required environment variables` | Check all required vars are set in `.env` |
| `RESOURCE_EXHAUSTED` / `429` errors | Vertex AI quota limits — the service retries automatically with exponential backoff |
| Context cache creation fails | Falls back to inline manual sending — performance is slower but functional |

---

## Next Steps

- Read the [Architecture](./architecture.md) guide to understand the pipeline design
- Review the [API Reference](./api-reference.md) to integrate with the frontend
- Check [Configuration](./configuration.md) for tuning parameters
