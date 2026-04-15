"""Compatibility launcher for the current async AERIS engine."""

import asyncio

from core.engine import main as run_engine


def main():
    asyncio.run(run_engine())


if __name__ == "__main__":
    main()
