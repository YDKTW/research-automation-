from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_FULLTEXT = {
    "checked": False,
    "status": "unknown",
    "best_url": "",
    "source_type": "",
    "license": "",
    "is_open_access": False,
    "zotero_item_key": "",
    "available_sources": [],
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _append_source(bucket: list[dict], source_type: str, url: str = "", is_open: bool = False,
                   license_value: str = "", version: str = "", note: str = "") -> None:
    item = {
        "source_type": _safe_str(source_type),
        "url": _safe_str(url),
        "is_open": bool(is_open),
        "license": _safe_str(license_value),
        "version": _safe_str(version),
        "note": _safe_str(note),
    }
    if item["source_type"] or item["url"]:
        bucket.append(item)


def _extract_openalex_oa(paper: dict) -> list[dict]:
    candidates: list[dict] = []

    oa_url = (
        paper.get("open_access", {}).get("oa_url")
        if isinstance(paper.get("open_access"), dict)
        else ""
    )
    is_oa = (
        paper.get("open_access", {}).get("is_oa")
        if isinstance(paper.get("open_access"), dict)
        else False
    )

    best_oa_location = paper.get("best_oa_location", {})
    if not isinstance(best_oa_location, dict):
        best_oa_location = {}

    best_oa_url = _safe_str(best_oa_location.get("landing_page_url") or best_oa_location.get("pdf_url"))
    best_oa_license = _safe_str(best_oa_location.get("license"))
    best_oa_version = _safe_str(best_oa_location.get("version"))

    if oa_url:
        candidates.append({
            "source_type": "openalex_oa",
            "url": _safe_str(oa_url),
            "is_open": bool(is_oa or True),
            "license": "",
            "version": "",
            "note": "from open_access.oa_url",
        })

    if best_oa_url:
        candidates.append({
            "source_type": "openalex_oa",
            "url": best_oa_url,
            "is_open": True,
            "license": best_oa_license,
            "version": best_oa_version,
            "note": "from best_oa_location",
        })

    return candidates


def _extract_primary_url(paper: dict) -> list[dict]:
    candidates: list[dict] = []
    url = _safe_str(paper.get("url"))
    if url:
        candidates.append({
            "source_type": "publisher_or_landing_page",
            "url": url,
            "is_open": False,
            "license": "",
            "version": "",
            "note": "primary paper url",
        })
    return candidates


def _extract_zotero(paper: dict) -> list[dict]:
    candidates: list[dict] = []
    zotero = paper.get("zotero", {})
    if not isinstance(zotero, dict):
        return candidates

    zotero_url = _safe_str(zotero.get("pdf_url") or zotero.get("url"))
    zotero_key = _safe_str(zotero.get("item_key"))
    has_pdf = bool(zotero.get("has_pdf"))

    if zotero_url or zotero_key:
        candidates.append({
            "source_type": "zotero",
            "url": zotero_url,
            "is_open": has_pdf,
            "license": "",
            "version": "",
            "note": f"zotero_item_key={zotero_key}" if zotero_key else "from zotero",
        })
    return candidates


def choose_best_fulltext_source(candidates: list[dict]) -> dict:
    if not candidates:
        return deepcopy(DEFAULT_FULLTEXT)

    open_candidates = [c for c in candidates if c.get("is_open") and c.get("url")]
    zotero_candidates = [c for c in candidates if c.get("source_type") == "zotero" and c.get("url")]
    landing_candidates = [c for c in candidates if c.get("url")]

    chosen = None
    status = "unknown"

    if open_candidates:
        chosen = open_candidates[0]
        status = "open_access"
    elif zotero_candidates:
        chosen = zotero_candidates[0]
        status = "zotero_pdf"
    elif landing_candidates:
        chosen = landing_candidates[0]
        status = "publisher_page_only"
    else:
        chosen = {}
        status = "unavailable"

    return {
        "checked": True,
        "status": status,
        "best_url": _safe_str(chosen.get("url")),
        "source_type": _safe_str(chosen.get("source_type")),
        "license": _safe_str(chosen.get("license")),
        "is_open_access": bool(chosen.get("is_open")),
        "zotero_item_key": "",
        "available_sources": candidates,
    }


def enrich_fulltext(paper: dict, enable_fulltext: bool = False) -> dict:
    enriched = deepcopy(paper)

    if not enable_fulltext:
        enriched["fulltext"] = {
            **deepcopy(DEFAULT_FULLTEXT),
            "checked": False,
            "status": "skipped",
        }
        return enriched

    candidates: list[dict] = []
    candidates.extend(_extract_openalex_oa(enriched))
    candidates.extend(_extract_primary_url(enriched))
    candidates.extend(_extract_zotero(enriched))

    enriched["fulltext"] = choose_best_fulltext_source(candidates)
    return enriched


def enrich_fulltext_for_papers(papers: list[dict], enable_fulltext: bool = False) -> list[dict]:
    return [enrich_fulltext(p, enable_fulltext=enable_fulltext) for p in papers]
