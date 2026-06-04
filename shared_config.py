import os
import pathlib


def _load_env_file(path: pathlib.Path) -> None:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# .env 탐색 순서:
# 1. shared_config.py 와 같은 폴더 (Webots controllers 폴더에 복사된 경우)
# 2. services/webots/.env (프로젝트 루트에서 실행하는 경우)
_here = pathlib.Path(__file__).resolve().parent
_load_env_file(_here / ".env")
_load_env_file(_here / "services" / "webots" / ".env")


def get_config(key: str, default: str = "") -> str:
    return os.environ.get(key, default)
