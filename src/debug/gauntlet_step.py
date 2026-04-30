import asyncio
import sys
from five_by_five_gauntlet import run_single_check

async def main():
    iteration = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    passed = await run_single_check(iteration)
    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
