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


# services/webots/.env 를 우선 로드 (OS 환경변수보다 낮은 우선순위)
_webots_dir = pathlib.Path(__file__).resolve().parent / "services" / "webots"
_load_env_file(_webots_dir / ".env")


def get_config(key: str, default: str = "") -> str:
    return os.environ.get(key, default)
