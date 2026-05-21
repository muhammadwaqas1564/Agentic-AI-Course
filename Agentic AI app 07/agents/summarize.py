import re
from collections import Counter

# ── HuggingFace Inference API (free, no key needed for small models) ──────────
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"


def _hf_summarize(text: str) -> str | None:
    """Try HuggingFace Inference API for summarization."""
    try:
        import requests
        payload = {
            "inputs": text[:1024],
            "parameters": {"max_length": 120, "min_length": 40, "do_sample": False},
        }
        resp = requests.post(HF_API_URL, json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            if isinstance(result, list) and result:
                return result[0].get("summary_text", "").strip()
    except Exception:
        pass
    return None


def _extractive_summarize(text: str, num_sentences: int = 3) -> str:
    """Simple extractive summarizer — no dependencies."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if len(s.split()) > 6]
    if not sentences:
        return text[:300]

    # Score by word frequency (tf-style)
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    freq = Counter(words)
    stopwords = {
        "that", "this", "with", "from", "have", "been", "they", "their",
        "which", "also", "more", "than", "when", "were", "these", "those",
        "into", "such", "each", "show", "study", "paper", "results",
    }
    for sw in stopwords:
        freq.pop(sw, None)

    def score(sent):
        ws = re.findall(r"\b[a-z]{4,}\b", sent.lower())
        return sum(freq.get(w, 0) for w in ws)

    scored = sorted(enumerate(sentences), key=lambda x: score(x[1]), reverse=True)
    top = sorted(scored[:num_sentences], key=lambda x: x[0])
    return " ".join(s for _, s in top)


def _extract_key_points(text: str, n: int = 4) -> list[str]:
    """Pull key noun-phrase-like chunks as bullet points."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if len(s.split()) > 5]
    points = []
    for s in sentences:
        if any(kw in s.lower() for kw in [
            "propose", "present", "show", "demonstrate", "achieve",
            "outperform", "novel", "state-of-the-art", "improve",
            "introduce", "develop", "find", "result", "significant",
            "first", "new", "approach", "method", "model", "framework",
        ]):
            points.append(s)
        if len(points) >= n:
            break
    # Pad with first sentences if not enough
    for s in sentences:
        if s not in points:
            points.append(s)
        if len(points) >= n:
            break
    return points[:n]


def summarize_papers(papers: list[dict]) -> list[dict]:
    """Add 'summary' and 'key_points' to each paper dict."""
    enriched = []
    for paper in papers:
        abstract = paper.get("abstract", "")
        if not abstract:
            paper["summary"] = "No abstract available."
            paper["key_points"] = []
            enriched.append(paper)
            continue

        # Try HuggingFace first, fall back to extractive
        summary = _hf_summarize(abstract)
        if not summary:
            summary = _extractive_summarize(abstract)

        paper["summary"] = summary
        paper["key_points"] = _extract_key_points(abstract)
        enriched.append(paper)
    return enriched
