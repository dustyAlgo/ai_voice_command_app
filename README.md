# Voice Command Shopping Assistant

## Approach
- `voice/` orchestrates voice workflow (`/api/voice/command/`).
- `ai/` contains Gemini client, prompt builder, and response validator.
- `shopping/` persists list items and interaction history.
- `catalog/` is the deterministic source for products and season tags.
- Voice search supports `name`, `brand`, `size`, and price range filters.

## Voice Flow
1. Frontend sends transcript to `/api/voice/command/` with JWT.
2. Backend gathers context (active list, recent history, season, catalog snapshot).
3. Gemini (configurable via `GEMINI_MODEL`, default `gemini-2.5-flash`) returns JSON.
4. Backend validates output and executes add/remove/modify/search.
5. API returns updated list, suggestions, substitutes, and search results.

## Local Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py loaddata catalog/fixtures/products.json
python manage.py runserver
```

## Database
- Local defaults to SQLite.
- If `DATABASE_URL` is set, backend switches to PostgreSQL automatically.

## Deployment
- Frontend: Vercel
- Backend: Render
- DB: Render PostgreSQL
