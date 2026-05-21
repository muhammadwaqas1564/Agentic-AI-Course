import requests

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

def fetch_papers(topic: str, limit: int = 8) -> list[dict]:
    """Fetch papers from Semantic Scholar API."""
    params = {
        "query": topic,
        "limit": limit,
        "fields": "title,authors,year,abstract,externalIds,url"
    }
    headers = {"User-Agent": "ResearchFlowLite/1.0"}

    try:
        resp = requests.get(SEMANTIC_SCHOLAR_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        papers = []
        for item in data.get("data", []):
            abstract = item.get("abstract") or ""
            if not abstract:
                continue  # skip papers without abstracts
            authors = [a.get("name", "") for a in item.get("authors", [])[:4]]
            paper_id = item.get("paperId", "")
            link = item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
            papers.append({
                "title": item.get("title", "Untitled"),
                "authors": ", ".join(authors) if authors else "Unknown",
                "year": item.get("year") or "N/A",
                "abstract": abstract,
                "link": link,
            })
        return papers[:8]
    except Exception as e:
        return _fallback_arxiv(topic, limit)


def _fallback_arxiv(topic: str, limit: int = 8) -> list[dict]:
    """Fallback: fetch from arXiv API."""
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{topic}",
        "start": 0,
        "max_results": limit,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(resp.text)
        papers = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            link_el = entry.find("atom:id", ns)
            year = ""
            published_el = entry.find("atom:published", ns)
            if published_el is not None:
                year = published_el.text[:4]
            authors = [
                a.find("atom:name", ns).text
                for a in entry.findall("atom:author", ns)[:4]
                if a.find("atom:name", ns) is not None
            ]
            abstract = (summary_el.text or "").strip().replace("\n", " ")
            if not abstract:
                continue
            papers.append({
                "title": (title_el.text or "Untitled").strip().replace("\n", " "),
                "authors": ", ".join(authors) if authors else "Unknown",
                "year": year or "N/A",
                "abstract": abstract,
                "link": (link_el.text or "").strip(),
            })
        return papers[:8]
    except Exception as e:
        return []
