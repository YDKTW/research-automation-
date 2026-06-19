from dotenv import load_dotenv
import os

load_dotenv()

keys = [
    "DIFY_BASE_URL",
    "DIFY_API_KEY",
    "DIFY_WORKFLOW_ID",
    "OUTPUT_BASE_DIR"
]

for key in keys:
    print(f"{key} = {os.getenv(key)}")
