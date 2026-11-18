"""`uv run reading-tutor`: serve the app on http://127.0.0.1:8000 (loopback only; there is no host option)."""

from __future__ import annotations

import argparse
import logging

import uvicorn

from reading_tutor.settings import HOST, PORT


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="reading-tutor", description="Bulgarian reading tutor prototype (localhost)")
    p.add_argument("--port", type=int, default=PORT)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(
        "reading_tutor.server.app:create_app",
        factory=True,
        host=HOST,
        port=args.port,
        access_log=False,  # access lines would carry attempt ids only, but keep the console quiet
    )


if __name__ == "__main__":  # pragma: no cover
    main()
