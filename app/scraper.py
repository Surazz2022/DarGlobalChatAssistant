import gzip
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

SITES = {
    "DarGlobal": ("https://darglobal.co.uk", ["https://darglobal.co.uk/sitemap.xml"]),
    "Wasalt": (
        "https://wasalt.sa",
        [
            "https://cdn.wasalt.sa/sitemap/static_sitemap_en_sa.xml.gz",
            "https://cdn.wasalt.sa/sitemap/category_sitemap_en_sa.xml.gz",
            "https://cdn.wasalt.sa/sitemap/rental_srp_sitemap_en_sa.xml.gz",
        ],
    ),
}

PUBLIC_FALLBACKS = [{
    "source": "Wasalt",
    "url": "https://wasalt.sa/en",
    "title": "Wasalt | Saudi Real Estate Platform",
    "text": "Wasalt is a Saudi-based real estate platform serving Saudi Arabia. It helps users buy, rent, sell, or invest in residential and commercial properties and connect with property experts. It provides apartments, villas, land, real-estate projects, auctions, and property-listing services. Wasalt describes itself as an AI-backed platform for verified properties and trusted brokers, and operates in English and Arabic.",
    "category": "company overview",
    "scraped_at": datetime.now(timezone.utc).isoformat(),
}]


def can_fetch(base_url: str, url: str) -> bool:
    parser = RobotFileParser()
    parser.set_url(urljoin(base_url, "/robots.txt"))
    try:
        parser.read()
        return parser.can_fetch("DarGlobalWasaltAssignmentBot", url)
    except Exception:
        return True


def extract_sitemap_locations(xml: str) -> list[str]:
    soup = BeautifulSoup(xml, "xml")
    return [tag.text.strip() for tag in soup.find_all("loc") if tag.text.strip()]


def extract_urls(xml: str) -> list[str]:
    return extract_sitemap_locations(xml)


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        tag.decompose()
    containers = [soup.find("main"), soup.find("article")]
    root = next((item for item in containers if item), soup)
    text = re.sub(r"\s+", " ", root.get_text(" ", strip=True))
    return text.strip()


def classify_url(url: str) -> str:
    path = urlparse(url).path.lower()
    if "/press/" in path or "/news/" in path or "/blog/" in path:
        return "news"
    if "/project" in path or "/propert" in path or "/villa" in path or "/apartment" in path:
        return "property"
    if "/about" in path or "/corporate" in path:
        return "company"
    return "general"


def scrape(output: str = "data/pages.json", limit_per_sitemap: int = 300) -> list[dict]:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    seen_urls: set[str] = set()

    with httpx.Client(follow_redirects=True, timeout=30.0,
                      headers={"User-Agent": "DarGlobalWasaltAssignmentBot/1.0 (+public-information-assignment)"}) as client:
        for source, (base_url, sitemaps) in SITES.items():
            for sitemap_url in sitemaps:
                if not can_fetch(base_url, sitemap_url):
                    continue
                try:
                    sitemap_response = client.get(sitemap_url)
                    sitemap_response.raise_for_status()
                except httpx.HTTPError:
                    continue

                body = sitemap_response.content
                if body.startswith(b"\x1f\x8b"):
                    body = gzip.decompress(body)
                xml = body.decode("utf-8", errors="replace")
                urls = extract_urls(xml)

                for url in urls[:limit_per_sitemap]:
                    normalized_url = url.strip().rstrip("/")
                    if normalized_url in seen_urls or not can_fetch(base_url, url):
                        continue
                    host = urlparse(url).netloc.lower()
                    if host not in {urlparse(base_url).netloc.lower(), "cdn.wasalt.sa"}:
                        continue
                    try:
                        page = client.get(url)
                        page.raise_for_status()
                    except httpx.HTTPError:
                        continue

                    text = clean_text(page.text)
                    if len(text) < 160:
                        continue
                    title_tag = BeautifulSoup(page.text, "html.parser").title
                    title = title_tag.get_text(" ", strip=True) if title_tag else source
                    records.append({
                        "source": source,
                        "url": str(page.url),
                        "title": title,
                        "text": text,
                        "category": classify_url(url),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    })
                    seen_urls.add(normalized_url)
                    time.sleep(0.10)

    for fallback in PUBLIC_FALLBACKS:
        if not any(record["url"] == fallback["url"] for record in records):
            records.append(dict(fallback))

    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


if __name__ == "__main__":
    print(f"Scraped {len(scrape())} pages")
