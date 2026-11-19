# DarGlobal / Wasalt Chatbot Workspace

- Build a FastAPI chatbot for publicly available DarGlobal and Wasalt information.
- Scrape only robots.txt-approved public pages and provide attribution/source URLs.
- Never commit API keys or secrets.
- Use OpenRouter chat completions with a configurable free model.
- Prefer a local TF-IDF retriever so the app works without embeddings or vector infrastructure.
- Keep Docker startup suitable for Render and other container platforms.
- Add tests for health, chat, scraper safety, and retrieval behavior.
