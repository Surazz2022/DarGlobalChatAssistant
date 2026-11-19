# DarGlobal & Wasalt Public Information Chatbot

A FastAPI chatbot that retrieves public DarGlobal and Wasalt content and answers questions using an OpenRouter model.

## Setup

1. Copy `.env.example` to `.env`.
2. Set `OPENROUTER_API_KEY`.
3. Install dependencies:
   `python -m pip install -r requirements.txt`
4. Scrape approved public pages:
   `python app/scraper.py`
5. Start the app:
   `uvicorn app.main:app --reload`

Open `http://localhost:8000`.

## Tests

`python -m pytest -q`

## Docker

`docker build -t property-chatbot .`

`docker run --rm -p 8000:8000 -e OPENROUTER_API_KEY=... property-chatbot`

## Deployment

The included `render.yaml` supports Render. Create a Render Blueprint, set `OPENROUTER_API_KEY`, and deploy.

Only public site content may be scraped. No secret keys or private data should be committed.
