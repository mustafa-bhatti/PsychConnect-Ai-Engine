# PsychConnect AI Engine — Documentation

Welcome to the **PsychConnect AI Engine** documentation. This service powers the House-Tree-Person (HTP) projective drawing analysis for the PsychConnect telepsychology platform.

> **Clinical Notice:** All outputs are AI-assistive tools for licensed psychologists only. This service never provides autonomous diagnoses.

---

## 📚 Table of Contents

| Document | Description |
|----------|-------------|
| [Getting Started](./getting-started.md) | Installation, environment setup, and first run |
| [Architecture](./architecture.md) | System design, pipeline phases, and data flow |
| [API Reference](./api-reference.md) | HTTP endpoints, request/response schemas, and error codes |
| [Configuration](./configuration.md) | Environment variables and tuning parameters |
| [Data Models](./data-models.md) | Pydantic schemas and database tables |
| [Clinical Rules](./clinical-rules.md) | The 9 clinical safety rules enforced in every AI prompt |
| [Prompt Engineering](./prompt-engineering.md) | How Phase 1 / 2 / 3 prompts are structured and why |
| [Deployment](./deployment.md) | Docker, Railway, and production deployment guides |
| [Testing](./testing.md) | Local testing, test data, and validation |
| [Contributing](./contributing.md) | Code standards, PR workflow, and prompt change policy |

---

## 🏗️ Project at a Glance

| Attribute | Value |
|-----------|-------|
| **Language** | Python 3.11+ |
| **Framework** | FastAPI 0.115 |
| **AI Backend** | Google Vertex AI (Gemini 2.5 Flash + Pro) |
| **Database** | Supabase (PostgreSQL) |
| **Auth** | Google Service Account (Vertex AI) + Supabase Service Role Key |
| **Deployment** | Railway / Docker / Cloud Run |
| **Version** | 2.1.0 |

---

## 🔗 Related Repositories

- **PsychConnect (Frontend)** — Next.js 16 web application that consumes this API
- **Supabase** — Shared PostgreSQL database with Row Level Security (RLS)
