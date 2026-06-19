#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


REQUIRED_ENV_KEYS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send report summary and optional report file to Telegram."
    )
    parser.add_argument("--topic", required=True, help="Research topic name")
    parser.add_argument("--date", required=True, help="Run date in YYYY-MM-DD format")
    parser.add_argument(
        "--data-dir",
        required=False,
        help="Explicit data directory. If omitted, uses OUTPUT_BASE_DIR/topic/date",
    )
    parser.add_argument(
        "--send-report-file",
        action="store_true",
        help="Also send report.md as a Telegram document",
    )
    return parser.parse_args()


def load_settings() -> dict:
    load_dotenv()
    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    output_base_dir = os.getenv(
        "OUTPUT_BASE_DIR",
        "/opt/research-automation/research-agent-platform/data",
    )

    return {
        "telegram_bot_token": os.environ["TELEGRAM_BOT_TOKEN"],
        "telegram_chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "telegram_parse_mode": os.getenv("TELEGRAM_PARSE_MODE", "HTML"),
        "output_base_dir": output_base_dir,
    }


def resolve_data_dir(args: argparse.Namespace, settings: dict) -> Path:
    if args.data_dir:
        return Path(args.data_dir).expanduser().resolve()
    return Path(settings["output_base_dir"]).expanduser().resolve() / args.topic / args.date


def load_meta(meta_path: Path) -> dict:
    if not meta_path.exists():
        raise FileNotFoundError(f"meta.json not found: {meta_path}")
    with meta_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_summary(summary_path: Path) -> str:
    if not summary_path.exists():
        raise FileNotFoundError(f"executive_summary.txt not found: {summary_path}")
    return summary_path.read_text(encoding="utf-8").strip()


def build_message(topic: str, run_date: str, meta: dict, summary: str) -> str:
    status = meta.get("status", "unknown")
    elapsed_time = meta.get("elapsed_time", "N/A")
    total_tokens = meta.get("total_tokens", "N/A")
    paper_count_input = meta.get("paper_count_input", "N/A")
    workflow_run_id = meta.get("workflow_run_id", "N/A")

    escaped_topic = html.escape(topic)
    escaped_summary = html.escape(summary).replace("\n", "\n")

    lines = [
        "📘 <b>研究報告通知</b>",
        f"主題：<b>{escaped_topic}</b>",
        f"日期：{html.escape(run_date)}",
        f"狀態：<b>{html.escape(str(status))}</b>",
        f"輸入文獻數：{html.escape(str(paper_count_input))}",
        f"耗時：{html.escape(str(elapsed_time))} 秒",
        f"Tokens：{html.escape(str(total_tokens))}",
        f"Run ID：<code>{html.escape(str(workflow_run_id))}</code>",
        "",
        "<b>摘要</b>",
        escaped_summary,
    ]
    return "\n".join(lines)


def send_message(token: str, chat_id: str, text: str, parse_mode: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def send_document(token: str, chat_id: str, file_path: Path, caption: str | None = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]

    with file_path.open("rb") as f:
        files = {"document": (file_path.name, f)}
        response = requests.post(url, data=data, files=files, timeout=120)
        response.raise_for_status()
        return response.json()


def main() -> int:
    try:
        args = parse_args()
        settings = load_settings()
        data_dir = resolve_data_dir(args, settings)

        meta_path = data_dir / "meta.json"
        summary_path = data_dir / "executive_summary.txt"
        report_path = data_dir / "report.md"

        meta = load_meta(meta_path)
        summary = load_summary(summary_path)
        message = build_message(args.topic, args.date, meta, summary)

        result = send_message(
            settings["telegram_bot_token"],
            settings["telegram_chat_id"],
            message,
            settings["telegram_parse_mode"],
        )
        print("[INFO] Telegram sendMessage OK")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if args.send_report_file:
            if not report_path.exists():
                raise FileNotFoundError(f"report.md not found: {report_path}")
            doc_result = send_document(
                settings["telegram_bot_token"],
                settings["telegram_chat_id"],
                report_path,
                caption=f"{args.topic} - {args.date} report.md",
            )
            print("[INFO] Telegram sendDocument OK")
            print(json.dumps(doc_result, ensure_ascii=False, indent=2))

        return 0

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
