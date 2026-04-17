"""CLI entry point — `python -m open_arangodb.ui` / `openarangodb-ui`."""

from __future__ import annotations

import argparse
import os

from open_arangodb.ui.app import build_app


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenArangoDB Signal Room web UI")
    parser.add_argument("--host", default=os.environ.get("OPENARANGODB_UI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENARANGODB_UI_PORT", "8800")))
    parser.add_argument("--no-demo", action="store_true", help="Use live ArangoDB (ARANGODB_* env vars)")
    args = parser.parse_args()

    if args.no_demo:
        os.environ["OPENARANGODB_UI_DEMO"] = "0"

    try:
        import uvicorn
    except ImportError as exc:  # noqa: F841
        raise SystemExit(
            "uvicorn is required. Install with: pip install 'OpenArangoDB[ui]'"
        ) from exc

    app = build_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
