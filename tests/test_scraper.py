from app.scraper import clean_text, extract_urls


def test_extract_urls():
    xml = '<urlset><url><loc>https://darglobal.co.uk/about</loc></url></urlset>'
    assert extract_urls(xml) == ["https://darglobal.co.uk/about"]


def test_clean_text_removes_scripts():
    html = '<html><main>Public <b>information</b><script>alert(1)</script></main></html>'
    assert clean_text(html) == "Public information"
