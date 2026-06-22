import asyncio

from session import demo_loop


async def main() -> None:
    await demo_loop()


if __name__ == "__main__":
    asyncio.run(main())
