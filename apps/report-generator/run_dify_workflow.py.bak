#!/usr/bin/env python3
import json
from datetime import date
from pathlib import Path

import requests

BASE_DIR = Path('/opt/research-automation')
CONFIG_FILE = BASE_DIR / 'config' / '.env'
DATA_DIR = BASE_DIR / 'data'


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()
    return env


def get_topic_dir(topic: str, run_date: str | None = None) -> Path:
    folder = run_date or date.today().isoformat()
    topic_dir = DATA_DIR / topic / folder
    topic_dir.mkdir(parents=True, exist_ok=True)
    return topic_dir


def read_papers(papers_path: Path) -> list:
    data = json.loads(papers_path.read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'papers' in data:
        papers = data['papers']
    elif isinstance(data, list):
        papers = data
    else:
        raise ValueError('papers.json must be a list or an object containing a papers field')
    if not isinstance(papers, list):
        raise ValueError('papers must be a list')
    return papers


def build_inputs(topic: str, report_type: str, papers: list) -> dict:
    return {
        'topic': topic,
        'report_data': report_type,
        'papers_json': json.dumps(papers, ensure_ascii=False, indent=2),
    }


def run_workflow(base_url: str, api_key: str, workflow_id: str, inputs: dict, user: str) -> dict:
    url = f"{base_url.rstrip('/')}/workflows/run"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'workflow_id': workflow_id,
        'inputs': inputs,
        'response_mode': 'blocking',
        'user': user,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=600)
    response.raise_for_status()
    return response.json()


def extract_outputs(resp: dict) -> dict:
    data = resp.get('data', {}) if isinstance(resp.get('data'), dict) else {}
    outputs = resp.get('outputs') or data.get('outputs') or {}
    if not outputs:
        raise ValueError(f'No outputs found in workflow response: {json.dumps(resp, ensure_ascii=False)}')

    result = {
        'workflow_run_id': data.get('workflow_run_id') or resp.get('workflow_run_id') or data.get('id') or resp.get('id') or '',
        'status': data.get('status') or resp.get('status') or '',
        'executive_summary': outputs.get('executive_summary', ''),
        'report_markdown': outputs.get('report_markdown', ''),
        'paper_count': outputs.get('paper_count', 0),
        'key_findings': outputs.get('key_findings', []),
        'limitations': outputs.get('limitations', []),
        'raw_response': resp,
    }

    if not result['report_markdown']:
        raise ValueError('Workflow succeeded but report_markdown is empty')

    return result


def write_outputs(topic_dir: Path, result: dict) -> dict:
    report_md_path = topic_dir / 'report.md'
    summary_path = topic_dir / 'executive_summary.txt'
    workflow_outputs_path = topic_dir / 'workflow_outputs.json'
    raw_response_path = topic_dir / 'raw_dify_response.json'
    meta_path = topic_dir / 'meta.json'

    report_md_path.write_text(result['report_markdown'], encoding='utf-8')
    summary_path.write_text(result['executive_summary'], encoding='utf-8')
    raw_response_path.write_text(json.dumps(result['raw_response'], ensure_ascii=False, indent=2), encoding='utf-8')

    workflow_outputs = {
        'executive_summary': result['executive_summary'],
        'report_markdown': result['report_markdown'],
        'paper_count': result['paper_count'],
        'key_findings': result['key_findings'],
        'limitations': result['limitations'],
    }
    workflow_outputs_path.write_text(json.dumps(workflow_outputs, ensure_ascii=False, indent=2), encoding='utf-8')

    meta = {
        'workflow_run_id': result['workflow_run_id'],
        'status': result['status'],
        'paper_count': result['paper_count'],
        'key_findings': result['key_findings'],
        'limitations': result['limitations'],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'report_md': str(report_md_path),
        'executive_summary_txt': str(summary_path),
        'workflow_outputs_json': str(workflow_outputs_path),
        'raw_response_json': str(raw_response_path),
        'meta_json': str(meta_path),
    }


def main():
    env = load_env(CONFIG_FILE)
    topic = env['TOPIC']
    run_date = env.get('RUN_DATE', date.today().isoformat())
    report_data = env.get(
        'REPORT_DATA',
        '本次整理之文獻主要來自探索式學習相關研究，目的是從軍事通識教育應用角度萃取啟發與研究方向。'
    )
    base_url = env['DIFY_BASE_URL']
    api_key = env['DIFY_API_KEY']
    workflow_id = env['DIFY_WORKFLOW_ID']
    user = env.get('DIFY_USER', 'telegram-bot')

    topic_dir = get_topic_dir(topic, run_date)
    papers_path = topic_dir / 'papers.json'
    if not papers_path.exists():
        raise FileNotFoundError(f'papers.json not found: {papers_path}')

    papers = read_papers(papers_path)
    inputs = build_inputs(topic, report_data, papers)
    resp = run_workflow(base_url, api_key, workflow_id, inputs, user)
    result = extract_outputs(resp)
    paths = write_outputs(topic_dir, result)

    print(f"papers_json: {papers_path}")
    print(f"raw_response: {paths['raw_response_json']}")
    print(f"workflow_outputs: {paths['workflow_outputs_json']}")
    print(f"executive_summary: {paths['executive_summary_txt']}")
    print(f"report_md: {paths['report_md']}")
    print(f"meta_json: {paths['meta_json']}")


if __name__ == '__main__':
    main()
