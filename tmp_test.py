import asyncio
import concurrent.futures

def _run_sync(coro_func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro_func(*args, **kwargs))).result()
    else:
        return asyncio.run(coro_func(*args, **kwargs))

async def async_db_call(x):
    await asyncio.sleep(0.1)
    return x * 2

def sync_repo_call(x):
    return _run_sync(async_db_call, x)

async def main():
    print("Main loop running")
    try:
        res = sync_repo_call(5)
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
