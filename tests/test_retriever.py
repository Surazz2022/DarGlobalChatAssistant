import json
from pathlib import Path

from app.retriever import Retriever


def test_retriever_returns_relevant_source(tmp_path: Path):
    pages = tmp_path / "pages.json"
    pages.write_text(json.dumps([
        {"source": "DarGlobal", "title": "Luxury projects", "url": "https://darglobal.co.uk/projects", "category": "property", "text": "DarGlobal develops luxury branded residences in Dubai and Marbella."},
        {"source": "Wasalt", "title": "Saudi rentals", "url": "https://wasalt.sa/en", "category": "company", "text": "Wasalt provides property listings and real estate search in Saudi Arabia."},
    ]), encoding="utf-8")

    results = Retriever(str(pages)).search("Dubai luxury residences")
    assert results
    assert results[0]["source"] == "DarGlobal"


def test_comparison_returns_both_sources(tmp_path: Path):
    pages = tmp_path / "pages.json"
    pages.write_text(json.dumps([
        {"source": "DarGlobal", "title": "Luxury developer", "url": "https://darglobal.co.uk/", "category": "company", "text": "DarGlobal develops and invests in luxury real estate assets globally."},
        {"source": "Wasalt", "title": "Saudi platform", "url": "https://wasalt.sa/en", "category": "company", "text": "Wasalt is a Saudi real estate platform for buying, renting, and listing properties."},
    ]), encoding="utf-8")

    results = Retriever(str(pages)).search("What is the difference between DarGlobal and Wasalt?")
    sources = {result["source"] for result in results}
    assert "DarGlobal" in sources
    assert "Wasalt" in sources


def test_unrelated_query_does_not_return_false_match(tmp_path: Path):
    pages = tmp_path / "pages.json"
    pages.write_text(json.dumps([
        {"source": "DarGlobal", "title": "Luxury developer", "url": "https://darglobal.co.uk/", "category": "company", "text": "DarGlobal develops luxury residential communities."},
    ]), encoding="utf-8")

    results = Retriever(str(pages)).search("quantum physics")
    assert results == []


def test_normalizes_common_misspellings(tmp_path: Path):
    pages = tmp_path / "pages.json"
    pages.write_text(json.dumps([
        {"source": "DarGlobal", "title": "Projects", "url": "https://darglobal.co.uk/projects", "category": "property", "text": "Luxury property projects in Dubai."},
    ]), encoding="utf-8")

    retriever = Retriever(str(pages))
    assert "darglobal" in retriever.normalize_query("Where is Darglobel operting?").lower()
    assert "wasalt" in retriever.normalize_query("What can Wasall do?").lower()


def test_resolves_followup_with_previous_company(tmp_path: Path):
    pages = tmp_path / "pages.json"
    pages.write_text(json.dumps([
        {"source": "DarGlobal", "title": "Developer", "url": "https://darglobal.co.uk/", "category": "company", "text": "DarGlobal is a luxury real estate developer."},
    ]), encoding="utf-8")

    retriever = Retriever(str(pages))
    resolved = retriever.resolve_context(
        "Where does it operate?",
        [{"role": "user", "content": "Tell me about DarGlobal"}],
    )
    assert "darglobal" in resolved.lower()
