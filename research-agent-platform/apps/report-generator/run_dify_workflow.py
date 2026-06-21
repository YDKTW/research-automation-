#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import requests


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Dify workflow and write UTF-8 outputs.")
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--date", dest="run_date", default="", help="Run date, e.g. 2026-06-21")
    parser.add_argument("--data-dir", default="", help="Absolute or relative data directory")
    parser.add_argument("--env-file", default="config/.env", help="Path to .env file")
    return parser.parse_args()


def ensure_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def build_report_data(papers: list[dict]) -> str:
    lines: list[str] = []
    for idx, paper in enumerate(papers, start=1):
        title = ensure_text(paper.get("title"))
        authors = paper.get("authors") or []
        if isinstance(authors, list):
            author_text = ", ".join([ensure_text(a) for a in authors if a])
        else:
            author_text = ensure_text(authors)

        year = ensure_text(paper.get("year"))
        abstract = ensure_text(paper.get("abstract"))
        source = ensure_text(paper.get("source"))
        doi = ensure_text(paper.get("doi"))
        url = ensure_text(paper.get("url"))
        journal = ensure_text(paper.get("journal"))
        citation_count = ensure_text(paper.get("citationcount", paper.get("citation_count", "")))

        lines.append(f"[{idx}] {title}")
        if author_text:
            lines.append(f"Authors: {author_text}")
        if year:
            lines.append(f"Year: {year}")
        if journal:
            lines.append(f"Journal: {journal}")
        if source:
            lines.append(f"Source: {source}")
        if doi:
            lines.append(f"DOI: {doi}")
        if url:
            lines.append(f"URL: {url}")
        if citation_count:
            lines.append(f"Citations: {citation_count}")
        if abstract:
            lines.append(f"Abstract: {abstract}")
        lines.append("")
    return "\n".join(lines).strip()


def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json_file(path: Path, data: dict | list) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def markdown_to_basic_html(markdown_text: str, title: str) -> str:
    safe_body = (
        markdown_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
      line-height: 1.7;
      max-width: 900px;
      margin: 40px auto;
      padding: 0 20px;
      color: #1f2937;
      background: #ffffff;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    h1, h2, h3 {{ line-height: 1.3; }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
  </style>
</head>
<body>
{safe_body}
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    base_dir = Path("/opt/research-automation/research-agent-platform")
    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = base_dir / env_path
    load_env_file(env_path)

    run_date = args.run_date or datetime.now().strftime("%Y-%m-%d")

    if args.data_dir:
        data_dir = Path(args.data_dir)
        if not data_dir.is_absolute():
            data_dir = base_dir / data_dir
    else:
        data_dir = base_dir / "data" / args.topic / run_date

    data_dir.mkdir(parents=True, exist_ok=True)

    papers_path = data_dir / "papers.json"
    if not papers_path.exists():
        raise FileNotFoundError(f"papers.json not found: {papers_path}")

    papers_data = json.loads(papers_path.read_text(encoding="utf-8"))
    if isinstance(papers_data, dict) and "papers" in papers_data:
        papers = papers_data["papers"]
    elif isinstance(papers_data, list):
        papers = papers_data
    else:
        raise ValueError("papers.json must be a list or an object with a 'papers' key")

    report_data = build_report_data(papers)

    base_url = os.getenv("DIFY_BASE_URL", "").rstrip("/")
    api_key = os.getenv("DIFY_API_KEY", "")
    user = os.getenv("DIFY_USER", "research-agent")
    workflow_id = os.getenv("DIFY_WORKFLOW_ID", "")

    if not base_url:
        raise ValueError("Missing DIFY_BASE_URL in env")
    if not api_key:
        raise ValueError("Missing DIFY_API_KEY in env")

    payload = {
        "inputs": {
            "topic": args.topic,
            "report_data": report_data,
            "papers_json": json.dumps(papers, ensure_ascii=False),
        },
        "response_mode": "blocking",
        "user": user,
    }

    if workflow_id:
        payload["workflow_id"] = workflow_id

    response = requests.post(
        f"{base_url}/workflows/run",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    result = response.json()

    data = result.get("data", {})
    outputs = data.get("outputs", {}) if isinstance(data, dict) else {}

    report_markdown = (
        ensure_text(outputs.get("report_markdown"))
        or ensure_text(outputs.get("report"))
        or ensure_text(outputs.get("markdown"))
    )
    executive_summary = (
        ensure_text(outputs.get("executive_summary"))
        or ensure_text(outputs.get("summary"))
    )
    key_findings = outputs.get("key_findings", [])
    limitations = outputs.get("limitations", [])

    if not report_markdown:
        report_markdown = "# 報告產生成功\n\n但 workflow 未回傳 report_markdown 欄位。"
    if not executive_summary:
        executive_summary = "本次 workflow 已執行成功，但未回傳 executive_summary 欄位。"

    report_path = data_dir / "report.md"
    summary_path = data_dir / "executive_summary.txt"
    result_path = data_dir / "dify_result.json"
    meta_path = data_dir / "meta.json"
    html_path = data_dir / "report.html"

    write_text_file(report_path, report_markdown)
    write_text_file(summary_path, executive_summary)
    write_json_file(result_path, result)

    meta = {
        "topic": args.topic,
        "run_date": run_date,
        "generated_at": datetime.now().isoformat(),
        "workflow_run_id": data.get("workflow_run_id", ""),
        "task_id": data.get("task_id", ""),
        "status": data.get("status", ""),
        "elapsed_time": data.get("elapsed_time", ""),
        "total_tokens": data.get("total_tokens", ""),
        "total_steps": data.get("total_steps", ""),
        "paper_count_input": len(papers),
        "paper_count_output": outputs.get("paper_count", ""),
        "key_findings": key_findings,
        "limitations": limitations,
        "input_files": {
            "papers_json": str(papers_path),
        },
        "output_files": {
            "report_md": str(report_path),
            "report_html": str(html_path),
            "executive_summary_txt": str(summary_path),
            "dify_result_json": str(result_path),
            "meta_json": str(meta_path),
        },
        "encoding": "utf-8",
    }
    write_json_file(meta_path, meta)
    write_text_file(html_path, markdown_to_basic_html(report_markdown, f"{args.topic} - {run_date}"))

    print(f"[INFO] topic={args.topic}")
    print(f"[INFO] run_date={run_date}")
    print(f"[INFO] data_dir={data_dir}")
    print(f"[INFO] papers={len(papers)}")
    print(f"[INFO] report={report_path}")
    print(f"[INFO] summary={summary_path}")
    print(f"[INFO] html={html_path}")
    print(f"[INFO] meta={meta_path}")


if __name__ == "__main__":
    main()
