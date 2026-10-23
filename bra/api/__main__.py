"""CLI entry point to launch the BRA API server."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the BRA API server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on (default: 8000)"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload on code changes"
    )
    args = parser.parse_args()

    uvicorn.run("bra.api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
