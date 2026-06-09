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


# .env 탐색 순서: 컨트롤러 디렉토리 → services/webots/ → services/
_here = pathlib.Path(__file__).resolve().parent
_load_env_file(_here / ".env")
_load_env_file(_here.parent / ".env")


def get_config(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_int_config(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default
