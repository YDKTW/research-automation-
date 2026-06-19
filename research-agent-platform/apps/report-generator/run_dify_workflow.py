#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


REQUIRED_ENV_KEYS = [
    "DIFY_BASE_URL",
    "DIFY_API_KEY",
    "OUTPUT_BASE_DIR",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a published Dify workflow with papers.json and save outputs."
    )
    parser.add_argument("--topic", required=True, help="Research topic name")
    parser.add_argument(
        "--date",
        required=False,
        help="Run date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--data-dir",
        required=False,
        help="Explicit data directory. If omitted, uses OUTPUT_BASE_DIR/topic/date",
    )
    parser.add_argument(
        "--papers-file",
        required=False,
        default="papers.json",
        help="Papers JSON filename inside data directory. Default: papers.json",
    )
    parser.add_argument(
        "--user",
        required=False,
        default="allen-cli",
        help="User identifier sent to Dify API. Default: allen-cli",
    )
    return parser.parse_args()


def load_settings() -> dict:
    load_dotenv()
    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return {
        "dify_base_url": os.environ["DIFY_BASE_URL"].rstrip("/"),
        "dify_api_key": os.environ["DIFY_API_KEY"],
        "output_base_dir": os.environ["OUTPUT_BASE_DIR"],
        "default_language": os.getenv("DEFAULT_LANGUAGE", "zh-TW"),
    }


def resolve_data_dir(args: argparse.Namespace, settings: dict) -> tuple[Path, str]:
    run_date = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.data_dir:
        data_dir = Path(args.data_dir).expanduser().resolve()
    else:
        data_dir = Path(settings["output_base_dir"]).expanduser().resolve() / args.topic / run_date
    return data_dir, run_date


def load_papers(papers_path: Path) -> list:
    if not papers_path.exists():
        raise FileNotFoundError(f"papers file not found: {papers_path}")

    with papers_path.open("r", encoding="utf-8") as f:
        papers = json.load(f)

    if not isinstance(papers, list):
        raise ValueError("papers.json must contain a JSON array")

    return papers


def build_report_data(topic: str, papers: list) -> str:
    lines = [
        f"研究主題：{topic}",
        f"納入文獻數量：{len(papers)}",
        "以下為本次納入文獻清單與摘要：",
    ]

    for idx, paper in enumerate(papers, start=1):
        title = paper.get("title", "未提供標題")
        authors = paper.get("authors", [])
        authors_text = ", ".join(authors) if isinstance(authors, list) else str(authors or "未提供作者")
        year = paper.get("year", "未提供年份")
        abstract = paper.get("abstract", "未提供摘要")
        source = paper.get("source", "未提供來源")
        doi = paper.get("doi", "")
        url = paper.get("url", "")

        lines.extend(
            [
                f"[{idx}] 標題：{title}",
                f"作者：{authors_text}",
                f"年份：{year}",
                f"來源：{source}",
                f"DOI：{doi or '未提供'}",
                f"URL：{url or '未提供'}",
                f"摘要：{abstract}",
                "---",
            ]
        )

    return "\n".join(lines)


def call_dify_workflow(settings: dict, topic: str, report_data: str, papers: list, user: str) -> dict:
    url = f"{settings['dify_base_url']}/workflows/run"
    headers = {
        "Authorization": f"Bearer {settings['dify_api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {
            "topic": topic,
            "report_data": report_data,
            "papers_json": json.dumps(papers, ensure_ascii=False),
        },
        "response_mode": "blocking",
        "user": user,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=180)
    response.raise_for_status()
    return response.json()


def extract_outputs(result: dict) -> dict:
    data = result.get("data") or {}
    outputs = data.get("outputs") or {}
    if not outputs:
        raise ValueError("Dify response has no outputs")

    return {
        "workflow_run_id": result.get("workflow_run_id") or data.get("id"),
        "task_id": result.get("task_id"),
        "workflow_id": data.get("workflow_id"),
        "status": data.get("status"),
        "elapsed_time": data.get("elapsed_time"),
        "total_tokens": data.get("total_tokens"),
        "total_steps": data.get("total_steps"),
        "created_at": data.get("created_at"),
        "finished_at": data.get("finished_at"),
        "outputs": outputs,
        "error": data.get("error"),
    }


def write_outputs(data_dir: Path, topic: str, run_date: str, papers_path: Path, result: dict, extracted: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)

    outputs = extracted["outputs"]
    report_markdown = outputs.get("report_markdown", "")
    executive_summary = outputs.get("executive_summary", "")

    report_path = data_dir / "report.md"
    summary_path = data_dir / "executive_summary.txt"
    meta_path = data_dir / "meta.json"
    raw_result_path = data_dir / "dify_result.json"

    report_path.write_text(report_markdown, encoding="utf-8")
    summary_path.write_text(executive_summary, encoding="utf-8")
    raw_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with papers_path.open("r", encoding="utf-8") as f:
        paper_count_input = len(json.load(f))

    meta = {
        "topic": topic,
        "run_date": run_date,
        "status": extracted.get("status"),
        "workflow_id": extracted.get("workflow_id"),
        "workflow_run_id": extracted.get("workflow_run_id"),
        "task_id": extracted.get("task_id"),
        "elapsed_time": extracted.get("elapsed_time"),
        "total_tokens": extracted.get("total_tokens"),
        "total_steps": extracted.get("total_steps"),
        "paper_count_input": paper_count_input,
        "paper_count_output": outputs.get("paper_count"),
        "source_file": str(papers_path),
        "output_files": {
            "report_markdown": str(report_path),
            "executive_summary": str(summary_path),
            "raw_result": str(raw_result_path),
        },
        "key_findings": outputs.get("key_findings"),
        "limitations": outputs.get("limitations"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    try:
        args = parse_args()
        settings = load_settings()
        data_dir, run_date = resolve_data_dir(args, settings)
        papers_path = data_dir / args.papers_file

        print(f"[INFO] topic: {args.topic}")
        print(f"[INFO] run_date: {run_date}")
        print(f"[INFO] data_dir: {data_dir}")
        print(f"[INFO] papers_file: {papers_path}")

        papers = load_papers(papers_path)
        print(f"[INFO] loaded papers: {len(papers)}")

        report_data = build_report_data(args.topic, papers)
        print("[INFO] report_data built")

        result = call_dify_workflow(settings, args.topic, report_data, papers, args.user)
        extracted = extract_outputs(result)

        print(f"[INFO] workflow status: {extracted.get('status')}")
        print(f"[INFO] workflow_run_id: {extracted.get('workflow_run_id')}")

        write_outputs(data_dir, args.topic, run_date, papers_path, result, extracted)
        print("[INFO] output files written successfully")
        return 0

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
