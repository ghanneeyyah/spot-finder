"""Write the API's OpenAPI schema to a file, or verify the committed file is current.

    python scripts/export_openapi.py            # rewrite packages/shared-types/openapi.json
    python scripts/export_openapi.py --check    # exit 1 if the committed file is out of date

The web app's types are generated from that file, so an API change that is not exported fails CI.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.main import create_app

TARGET = Path(__file__).resolve().parents[3] / "packages" / "shared-types" / "openapi.json"


def render() -> str:
    # The engine never connects at construction time, so no database is needed to export.
    app = create_app(Settings(database_url="postgresql://export:export@localhost/export"))
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    rendered = render()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text() != rendered:
            sys.stderr.write("openapi.json is out of date. Run: python scripts/export_openapi.py\n")
            return 1
        return 0
    TARGET.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
