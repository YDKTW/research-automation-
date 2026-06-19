#!/usr/bin/env python3
import json
import pathlib
import requests
from datetime import date
from typing import Any, Dict, List

BASE_DIR = pathlib.Path("/opt/research-automation")
OUTPUT_DIR = BASE_DIR / "data"
CONFIG_FILE = BASE_DIR / "config" / ".env"


def load_env(env_path: pathlib.Path) -> Dict[str, str]:
    data = {}
    if not env_path.exists():
        raise FileNotFoundError(f".env not found: {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def parse_creators(creators: List[Dict[str, Any]]) -> List[str]:
    names = []
    for c in creators or []:
        first = c.get("firstName", "").strip()
        last = c.get("lastName", "").strip()
        name = f"{first} {last}".strip()
        if not name:
            name = c.get("name", "").strip()
        if name:
            names.append(name)
    return names


def parse_tags(tags: List[Dict[str, Any]]) -> List[str]:
    out = []
    for t in tags or []:
        tag = t.get("tag", "").strip()
        if tag:
            out.append(tag)
    return out


def extract_year(zotero_date: str):
    if not zotero_date:
        return None
    for token in zotero_date.replace("/", "-").split("-"):
        token = token.strip()
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


def build_paper(item: Dict[str, Any], collection_name: str):
    data = item.get("data", {})
    title = (data.get("title") or "").strip()
    if not title:
        return None

    abstract = (data.get("abstractNote") or data.get("abstract") or "").strip()

    return {
        "title": title,
        "authors": parse_creators(data.get("creators", [])),
        "year": extract_year(data.get("date", "")),
        "abstract": abstract,
        "doi": (data.get("DOI") or "").strip(),
        "url": (data.get("url") or "").strip(),
        "publication_title": (
            data.get("publicationTitle")
            or data.get("proceedingsTitle")
            or data.get("bookTitle")
            or ""
        ).strip(),
        "item_type": (data.get("itemType") or "").strip(),
        "tags": parse_tags(data.get("tags", [])),
        "zotero_key": item.get("key"),
        "zotero_version": item.get("version"),
        "zotero_collection": collection_name,
        "date_added": data.get("dateAdded", ""),
        "date_modified": data.get("dateModified", "")
    }


def main():
    env = load_env(CONFIG_FILE)

    zotero_user_id = env["ZOTERO_USER_ID"]
    zotero_api_key = env["ZOTERO_API_KEY"]
    zotero_collection_key = env["ZOTERO_COLLECTION_KEY"]
    topic = env.get("TOPIC", "未命名主題")
    collection_name = env.get("ZOTERO_COLLECTION_NAME", zotero_collection_key)
    limit = int(env.get("ZOTERO_LIMIT", "20"))

    today = date.today().isoformat()
    safe_topic = topic.replace(" ", "-").replace("/", "-")
    run_dir = OUTPUT_DIR / safe_topic / today
    run_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://api.zotero.org/users/{zotero_user_id}/collections/{zotero_collection_key}/items"
    headers = {"Zotero-API-Key": zotero_api_key}
    params = {
        "limit": limit,
        "sort": "dateModified",
        "direction": "desc",
        "format": "json"
    }

    resp = requests.get(url, headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    raw_items = resp.json()

    (run_dir / "raw_zotero.json").write_text(
        json.dumps(raw_items, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    papers = []
    for item in raw_items:
        paper = build_paper(item, collection_name)
        if paper:
            papers.append(paper)

    output = {
        "topic": topic,
        "report_date": today,
        "source": "zotero",
        "collection": collection_name,
        "paper_count": len(papers),
        "papers": papers
    }

    out_path = run_dir / "papers.json"
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(str(out_path))


if __name__ == "__main__":
    main()
