import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def _load_env():
    """从 .env 文件加载环境变量（不覆盖已有的环境变量）。"""

    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()

# Compatibility identifier only. Historical model names remain in stored records.
DEFAULT_MODEL = "legacy-disabled"
DEFAULT_SIZE = "1024*1024"
POLL_INTERVAL = 3
POLL_TIMEOUT = 120
