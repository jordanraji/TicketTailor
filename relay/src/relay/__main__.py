"""Entrypoint: ``python -m relay``."""

import asyncio

from relay.loop import main

if __name__ == "__main__":
    asyncio.run(main())
