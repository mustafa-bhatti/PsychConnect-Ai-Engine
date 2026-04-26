# Deployment

This guide covers deploying the PsychConnect AI Engine to production environments.

---

## Option 1: Railway (Recommended)

Railway auto-detects the `Procfile` and deploys from GitHub.

### Steps

1. Push this repository to GitHub
2. Create a new Railway project → **Deploy from GitHub**
3. Set environment variables in the Railway dashboard:
   - `VERTEX_PROJECT_ID`
   - `GOOGLE_APPLICATION_CREDENTIALS` (upload the JSON file and set path)
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `ALLOWED_ORIGINS` (your Next.js production domain)
   - `HTP_MANUAL_GCS_URI` (recommended for production — upload manual to GCS)
4. Railway auto-detects the `Procfile` and starts the service

### Health Check

Configure Railway's health check to `GET /health` for automatic restarts on failure.

---

## Option 2: Docker

### Build

```bash
docker build -t htp-service .
```

### Run

```bash
docker run -p 8000:8000 \
  -e VERTEX_PROJECT_ID=your-project \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -e SUPABASE_URL=https://your-project.supabase.co \
  -e SUPABASE_SERVICE_ROLE_KEY=eyJ... \
  -e ALLOWED_ORIGINS=https://your-frontend.com \
  -v /path/to/credentials.json:/app/credentials.json \
  -v /path/to/resources:/app/resources \
  htp-service
```

### Docker Compose (example)

```yaml
version: "3.8"
services:
  htp-engine:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./psychconnect-key.json:/app/psychconnect-key.json
      - ./resources:/app/resources
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Option 3: Google Cloud Run

1. Build and push the Docker image to Google Artifact Registry
2. Deploy to Cloud Run with the required environment variables
3. Mount the service account key as a secret
4. Set `VERTEX_LOCATION` to match your Cloud Run region

### Benefits

- Native Vertex AI integration (same GCP project)
- Auto-scaling to zero when idle
- Lower latency to Gemini API endpoints

---

## Production Checklist

- [ ] All required environment variables set
- [ ] Service account has `aiplatform.user` role
- [ ] HTP manual uploaded to GCS (set `HTP_MANUAL_GCS_URI`)
- [ ] `ALLOWED_ORIGINS` restricted to production domain(s) only
- [ ] Health check endpoint configured for auto-restart
- [ ] Logging/monitoring configured (CloudWatch, Railway logs, etc.)
- [ ] `.env` and credential files excluded from the deployed image
- [ ] Context cache TTL appropriate for expected usage patterns

---

## Monitoring

### Key Metrics to Watch

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Queue size | `GET /health` → `queue_size` | > 10 |
| Pipeline failures | Server logs (`status: failed`) | Any |
| Processing time | `ai_report_json.processing_time_seconds` | > 120s |
| Context cache status | Startup logs (`ACTIVE` / `INACTIVE`) | `INACTIVE` in production |
| Vertex AI quota usage | Google Cloud Console | > 80% |
