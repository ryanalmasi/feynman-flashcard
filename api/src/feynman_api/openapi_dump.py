import json
import sys

from feynman_api.config import Settings
from feynman_api.main import create_app


def main() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://x:x@127.0.0.1:1/x",
        _env_file=None,
    )
    json.dump(create_app(settings).openapi(), sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
