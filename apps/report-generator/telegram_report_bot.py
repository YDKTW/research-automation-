#!/usr/bin/env python3
import subprocess
import time
from datetime import datetime
from pathlib import Path
import requests

BASE_DIR = Path('/opt/research-automation')
APP_DIR = BASE_DIR / 'apps' / 'report-generator'
CONFIG_FILE = BASE_DIR / 'config' / '.env'
DATA_DIR = BASE_DIR / 'data'

def load_env(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        data[k.strip()] = v.strip()
    return data

def tg_api(token: str, method: str) -> str:
    return f'https://api.telegram.org/bot{token}/{method}'

def send_message(token: str, chat_id: str, text: str) -> None:
    r = requests.post(
        tg_api(token, 'sendMessage'),
        json={'chat_id': chat_id, 'text': text},
        timeout=60,
    )
    r.raise_for_status()

def send_document(token: str, chat_id: str, file_path: Path, caption: str) -> None:
    with file_path.open('rb') as f:
        r = requests.post(
            tg_api(token, 'sendDocument'),
            data={'chat_id': chat_id, 'caption': caption},
            files={'document': (file_path.name, f, 'application/pdf')},
            timeout=300,
        )
    r.raise_for_status()

def get_updates(token: str, offset=None):
    params = {'timeout': 30, 'allowed_updates': '["message"]'}
    if offset is not None:
        params['offset'] = offset
    r = requests.get(tg_api(token, 'getUpdates'), params=params, timeout=40)
    r.raise_for_status()
    payload = r.json()
    if not payload.get('ok'):
        raise RuntimeError(payload)
    return payload['result']

def parse_date_folder(path: Path):
    try:
        return datetime.strptime(path.name, '%Y-%m-%d')
    except ValueError:
        return None

def get_latest_topic_dir(topic: str) -> Path:
    topic_dir = DATA_DIR / topic
    if not topic_dir.exists():
        raise FileNotFoundError(f'topic directory not found: {topic_dir}')
    dated_dirs = [p for p in topic_dir.iterdir() if p.is_dir() and parse_date_folder(p)]
    if not dated_dirs:
        raise FileNotFoundError(f'no dated folders found under: {topic_dir}')
    return max(dated_dirs, key=parse_date_folder)

def render_pdf(md_path: Path) -> Path:
    pdf_path = md_path.with_suffix('.pdf')
    subprocess.run([
        'pandoc', str(md_path),
        '-o', str(pdf_path),
        '--pdf-engine=xelatex',
        '-V', 'mainfont=Noto Serif CJK TC'
    ], check=True)
    return pdf_path

def get_latest_report_pdf(topic: str) -> Path:
    latest_dir = get_latest_topic_dir(topic)
    pdf_path = latest_dir / 'report.pdf'
    if pdf_path.exists():
        return pdf_path
    md_path = latest_dir / 'report.md'
    if md_path.exists():
        return render_pdf(md_path)
    raise FileNotFoundError(f'no report.pdf or report.md found in: {latest_dir}')

def run_report_workflow() -> Path:
    env = load_env(CONFIG_FILE)
    topic = env['TOPIC']
    subprocess.run(['python', 'run_dify_workflow.py'], cwd=str(APP_DIR), check=True)
    return get_latest_report_pdf(topic)

def main() -> None:
    env = load_env(CONFIG_FILE)
    token = env.get('TELEGRAM_BOT_TOKEN', '').strip()
    allowed_chat_id = str(env.get('TELEGRAM_ALLOWED_CHAT_ID', '')).strip()
    topic = env.get('TOPIC', '').strip()

    if not token:
        raise ValueError('TELEGRAM_BOT_TOKEN is empty in .env')
    if not allowed_chat_id:
        raise ValueError('TELEGRAM_ALLOWED_CHAT_ID is empty in .env')
    if not topic:
        raise ValueError('TOPIC is empty in .env')

    print('Bot started. Waiting for commands...')
    print('Allowed commands: /start, /report, /download')

    offset = None
    while True:
        try:
            updates = get_updates(token, offset)
            for upd in updates:
                offset = upd['update_id'] + 1
                msg = upd.get('message', {})
                text = (msg.get('text') or '').strip()
                chat_id = str(msg.get('chat', {}).get('id', ''))

                if not chat_id:
                    continue
                if chat_id != allowed_chat_id:
                    send_message(token, chat_id, '未授權使用。')
                    continue

                if text == '/start':
                    send_message(token, chat_id, '可用指令：/report 生成最新報告並傳送 PDF；/download 傳送最新日期資料夾中的 report.pdf。')
                elif text == '/download':
                    pdf_path = get_latest_report_pdf(topic)
                    send_document(token, chat_id, pdf_path, caption=f'最新研究報告 PDF：{pdf_path.parent.name}')
                elif text == '/report':
                    send_message(token, chat_id, '開始生成最新研究報告，請稍候...')
                    pdf_path = run_report_workflow()
                    send_document(token, chat_id, pdf_path, caption=f'最新研究報告 PDF：{pdf_path.parent.name}')
                elif text:
                    send_message(token, chat_id, '請輸入 /report 或 /download。')
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f'Error: {e}')
            time.sleep(5)

if __name__ == '__main__':
    main()
