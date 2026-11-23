# vista-flicks-recommendation-api

FastAPI service used by Node `RECOMMENDED_REELS` for authenticated For You reel IDs.

## Env

| Var | Required | Notes |
| --- | --- | --- |
| `MONGO_URI` | yes | Same Mongo cluster as Node (prod/staging) |
| `DB_NAME` | yes | Same DB name as Node (e.g. `vistaFlicks`) |
| `PORT` | Render sets | Uvicorn listen port |

Needs collections: `users`, `reelsrecommends`, `contents`, `reels`, plus preference masters.

## Local

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Smoke:

- `GET /health` → `{ "status": "ok" }`
- `GET /api/v1/reels/feed?user_id=<ObjectId>&limit=10` → `{ "reels": [...] }`
- `/api/v1/reels/feeds` is the same handler (alias)

## Render

1. Build from this repo (Dockerfile) or native Python with start command:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. Set `MONGO_URI` and `DB_NAME` to **prod** values (never commit them).
3. Health check path: `/health`
4. Public URL Node already uses:
   `https://vista-flicks-recommendation-api.onrender.com/api/v1/reels/feed`

## Tests

```bash
python -m unittest discover -s tests -v
```
