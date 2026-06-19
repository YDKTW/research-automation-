#!/usr/bin/env python3
import json
import os
import sys
import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.sources.crossref import enrich_papers_with_crossref


DATA_DIR = PROJECT_ROOT / "data"
OPENALEX_URL = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def normalize_doi(doi):
    if not doi:
        return None
    doi = doi.strip()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("https://dx.doi.org/", "")
    doi = doi.replace("http://dx.doi.org/", "")
    doi = doi.replace("doi:", "")
    return doi.strip() or None


def search_openalex(query, from_date, per_page=20, page=1):
    params = {
        "search": query,
        "filter": f"from_publication_date:{from_date}",
        "per_page": per_page,
        "page": page,
    }
    try:
        r = requests.get(OPENALEX_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json() or {}
        return data.get("results", [])
    except requests.RequestException as exc:
        print(f"[WARN] OpenAlex request failed for query: {query} ({exc})")
        return []


def search_semantic_scholar(query, from_date, limit=10):
    year_from = int(from_date[:4])
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,year,authors,externalIds,url,venue,citationCount",
    }

    try:
        r = requests.get(SEMANTIC_SCHOLAR_URL, params=params, timeout=30)

        if r.status_code == 429:
            print(f"[WARN] Semantic Scholar rate limited for query: {query}")
            return []

        r.raise_for_status()
        data = r.json() or {}
        papers = data.get("data", []) or []

        filtered = []
        for p in papers:
            year = p.get("year")
            if year and year >= year_from:
                filtered.append(p)
        return filtered

    except requests.RequestException as exc:
        print(f"[WARN] Semantic Scholar request failed for query: {query} ({exc})")
        return []
    except Exception as exc:
        print(f"[WARN] Semantic Scholar parse failed for query: {query} ({exc})")
        return []


def normalize_openalex(item):
    doi = normalize_doi(item.get("doi"))
    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}

    abstract = None
    inverted_index = item.get("abstract_inverted_index")
    if inverted_index and isinstance(inverted_index, dict):
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        abstract = " ".join(word for _, word in word_positions)

    return {
        "title": item.get("title"),
        "abstract": abstract,
        "year": item.get("publication_year"),
        "publication_date": item.get("publication_date"),
        "doi": doi,
        "authors": [
            a.get("author", {}).get("display_name")
            for a in item.get("authorships", [])
            if a.get("author", {}).get("display_name")
        ],
        "source": "openalex",
        "source_id": item.get("id"),
        "journal": source.get("display_name"),
        "publisher": None,
        "url": doi and f"https://doi.org/{doi}" or item.get("id"),
        "citation_count": item.get("cited_by_count", 0),
        "topic_match_note": "",
    }


def normalize_semantic_scholar(item):
    external_ids = item.get("externalIds") or {}
    doi = normalize_doi(external_ids.get("DOI"))

    return {
        "title": item.get("title"),
        "abstract": item.get("abstract"),
        "year": item.get("year"),
        "publication_date": None,
        "doi": doi,
        "authors": [
            a.get("name")
            for a in item.get("authors", [])
            if a.get("name")
        ],
        "source": "semanticscholar",
        "source_id": item.get("paperId"),
        "journal": item.get("venue"),
        "publisher": None,
        "url": item.get("url") or (doi and f"https://doi.org/{doi}"),
        "citation_count": item.get("citationCount", 0),
        "topic_match_note": "",
    }


def dedupe_papers(papers):
    seen = set()
    deduped = []

    for p in papers:
        doi = normalize_doi(p.get("doi"))
        title = (p.get("title") or "").strip().lower()
        year = p.get("year")

        if doi:
            key = ("doi", doi)
        else:
            key = ("title_year", title, year)

        if key in seen:
            continue

        seen.add(key)
        deduped.append(p)

    return deduped


def score_paper(p):
    title = (p.get("title") or "").lower()
    abstract = (p.get("abstract") or "").lower()
    journal = (p.get("journal") or "").lower()
    text = f"{title} {abstract} {journal}"

    score = 0

    strong_keywords = [
        "military education",
        "professional military education",
        "military academy",
        "officer education",
        "war college",
        "defense education",
        "military higher education",
    ]

    medium_keywords = [
        "military",
        "defense",
        "armed forces",
        "officer",
        "cadet",
        "curriculum",
        "higher education",
        "teaching",
        "learning",
        "pedagogy",
    ]

    target_keywords = [
        "general education",
        "liberal education",
        "humanities",
        "civic education",
        "ethics",
        "critical thinking",
    ]

    negative_keywords = [
        "primary school",
        "secondary school",
        "kindergarten",
        "children",
        "language learning",
        "mathematics education",
        "medical education",
        "nursing education",
    ]

    matched = []

    for kw in strong_keywords:
        if kw in text:
            score += 6
            matched.append(kw)

    for kw in medium_keywords:
        if kw in text:
            score += 2
            matched.append(kw)

    for kw in target_keywords:
        if kw in text:
            score += 3
            matched.append(kw)

    for kw in negative_keywords:
        if kw in text:
            score -= 4

    if p.get("abstract"):
        score += 2

    if p.get("doi"):
        score += 1

    if p.get("year"):
        if p["year"] >= 2023:
            score += 3
        elif p["year"] >= 2020:
            score += 2

    score += min(int((p.get("citation_count") or 0) / 20), 3)

    p["topic_match_note"] = ", ".join(sorted(set(matched))) if matched else ""
    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--run-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--days-back", type=int, default=365)
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()

    run_date = datetime.strptime(args.run_date, "%Y-%m-%d").date()
    from_date = (run_date - timedelta(days=args.days_back)).isoformat()

    topic_dir = DATA_DIR / args.topic / args.run_date
    ensure_dir(topic_dir)

    papers_file = topic_dir / "papers.json"
    meta_file = topic_dir / "paper_update_meta.json"

    queries = [
        '"military education" AND curriculum',
        '"professional military education"',
        '"military academy" AND teaching',
        '"officer education" AND curriculum',
        '"war college" AND education',
        '"military higher education" AND learning',
        'military AND ("general education" OR "liberal education")',
        'defense education AND curriculum',
    ]

    all_raw_openalex = []
    all_raw_s2 = []

    for q in queries:
        all_raw_openalex.extend(search_openalex(q, from_date, per_page=20))
        all_raw_s2.extend(search_semantic_scholar(q, from_date, limit=10))
        time.sleep(1)

    normalized = [normalize_openalex(x) for x in all_raw_openalex] + [
        normalize_semantic_scholar(x) for x in all_raw_s2
    ]

    merged = dedupe_papers(normalized)
    ranked = sorted(merged, key=score_paper, reverse=True)
    selected = ranked[: args.max_results]

    for p in selected:
        p["topic_match_score"] = score_paper(p)
        p.setdefault("publisher", None)
        p.setdefault("license", None)
        p.setdefault("best_fulltext_url", None)
        p.setdefault("crossref_checked", False)
        p.setdefault("crossref_meta", {})
        p.setdefault("is_open_access", False)

    selected = enrich_papers_with_crossref(
        selected,
        mailto=os.getenv("CROSSREF_MAILTO")
    )

    for p in selected:
        provenance = p.get("provenance") or {}
        found_in = provenance.get("found_in") or []

        if p.get("source") and p["source"] not in found_in:
            found_in.append(p["source"])

        if p.get("crossref_checked") and "crossref" not in found_in:
            found_in.append("crossref")

        provenance["found_in"] = found_in
        provenance["enriched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        provenance["enrichment_version"] = "v1"
        p["provenance"] = provenance

    with open(papers_file, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    meta = {
        "topic": args.topic,
        "run_date": args.run_date,
        "days_back": args.days_back,
        "source_summary": {
            "openalex_raw": len(all_raw_openalex),
            "semanticscholar_raw": len(all_raw_s2),
            "merged_unique": len(merged),
            "selected_final": len(selected),
        },
        "status": "succeeded",
    }

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
