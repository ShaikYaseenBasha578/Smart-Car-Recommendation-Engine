# API service, Docker, CI and deployment

The v3 recommender is available as a small typed HTTP service (`api_service/`, FastAPI) beside the Flask site. Both call the same engine, `services/recsys/api.py`; nothing in `services/` is changed by the service.

## Run the API locally

```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-api.txt
uvicorn api_service.main:app --port 8000
```

Interactive docs: http://localhost:8000/docs

The service sets `RANKER=v3` and `CARREC_CATALOGUE_DIR=data/catalogue_v3` for its own process only, and only where you have not set them. It never touches a knowledge-base file.

Environment variables (all optional):

| Variable | Effect |
|---|---|
| `API_CORS_ORIGINS` | Comma-separated allowed origins. Unset = CORS off. `*` is ignored. |
| `GEMINI_API_KEY` (or the variable named by `LLM_PARSER_KEY_ENV`) | Lets a request with `"llm": true` use the optional LLM parser. Without a key, or without `llm: true`, the parser is off. Keys are read from the environment only. |
| `PORT` | Port inside the container (default 8000). |

## Endpoints

Errors are JSON `{"error": code, "detail": ...}` with 404 or 422; a server fault is a 500 with a fixed message (the trace stays in the server log).

**GET /health** - status, engine version, catalogue row and model counts, data file dates.
```
curl localhost:8000/health
```

**POST /v1/recommend** - `{query (1-500 chars), limit (1-20, default 8), llm (default false)}`. Returns `{engine, query_understood, results, relaxed, generated_at}` plus `message`, `data_as_of` and `llm`. `results` are the v3 cards exactly as `services.recsys.api.recommend` returns them (cut to `limit`); `relaxed` is null unless no car met every requirement.
```
curl -X POST localhost:8000/v1/recommend -H 'Content-Type: application/json' \
  -d '{"query": "family suv under 15 lakh automatic", "limit": 3}'
```

**GET /v1/models/{model}/evidence** - expert rows, owner ratings and owner themes for one model from `data/assessments.csv`, `owner_ratings.csv` and `owner_themes.csv`, each with its source URL. A catalogue model with no reviews returns empty lists; an unknown name returns 404.
```
curl localhost:8000/v1/models/Creta/evidence
```

**POST /v1/compare** - `{models: [2-4 catalogue model names], query: optional}`. The engine has no compare function, so for each model the service parses the query once with the existing parser, pins the intent to that model and calls `recommend(intent=...)`; you get that model's best-matching variant card side by side. An unknown model is a 404 naming it.
```
curl -X POST localhost:8000/v1/compare -H 'Content-Type: application/json' \
  -d '{"models": ["Creta", "Seltos"], "query": "automatic diesel"}'
```

## Docker

One `Dockerfile` (multi-stage, pinned `python:3.12.7-slim-bookworm`, non-root user, `/health` healthcheck). The default command runs the API. The image holds the app code, `data/` and `car_recommendation_assets/`; `.dockerignore` keeps out the knowledge base, `*.db`, backups, `eval/`, tests, `.env` and keys.

```
docker build -t carrec .
docker run --rm -p 8000:8000 carrec
curl localhost:8000/health
```

## Compose

```
docker compose up --build
```

`web` is the Flask site (gunicorn `app:app`, http://localhost:5001, v3 ranker on); `api` is the FastAPI service (http://localhost:8000/docs). Both use the same image.

## CI

`.github/workflows/ci.yml` runs on pull requests and on pushes to every branch except `main`. Job `test`: Python 3.12, cached pip, installs `requirements.txt` and `requirements-api.txt`, runs `python -m pytest tests -q` (the whole `tests/` directory only, never from the repo root), uploads `test-report.xml` as an artifact. Job `docker`: builds the image without pushing. No secrets, no deployment. The repo has no linter config, so there is no lint step.

## Beside the Flask app on Render (description only)

Render keeps deploying the Flask site as it does today, and `main` still deploys only on merge. The API can be a second Render web service from the same repository and the same Dockerfile, with start command `uvicorn api_service.main:app --host 0.0.0.0 --port $PORT` and health check path `/health`. The Flask service can switch to the Dockerfile later with start command `gunicorn app:app --bind 0.0.0.0:$PORT`. Environment variables go in the Render dashboard (`GEMINI_API_KEY`, `API_CORS_ORIGINS`). This change adds no file that Render reads; the owner decides whether to create the second service.

## Azure Container Apps (optional, steps only)

1. Create a resource group and a container registry: `az group create`, `az acr create`.
2. Build and push: `az acr build -r <registry> -t carrec:1 .`
3. Create an environment and the app: `az containerapp env create`, then `az containerapp create --image <registry>.azurecr.io/carrec:1 --target-port 8000 --ingress external --env-vars API_CORS_ORIGINS=...`, with `GEMINI_API_KEY` added as a secret reference.
4. For the Flask site, create a second app from the same image with command `gunicorn app:app --bind 0.0.0.0:5001` and target port 5001.
5. Set the probe path to `/health` for the API.
