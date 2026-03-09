import asyncio
import os
import re
from dotenv import load_dotenv
from pathlib import Path
import asyncpg

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
cs = os.getenv("POSTGRES_CONNECTION_STRING", "")

async def main():
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    u, p, h, port, db = m.groups()
    conn = await asyncpg.connect(host=h, port=int(port), user=u, password=p, database=db)
    
    try:
        # Check current type of user_id
        current_type = await conn.fetchval(
            "SELECT data_type FROM information_schema.columns WHERE table_name='user_info' AND column_name='user_id'"
        )
        print(f"Current user_id type: {current_type}")
        
        if current_type and "character" not in current_type.lower() and "text" not in current_type.lower() and "varchar" not in current_type.lower():
            print("Type mismatch! Dropping user_info CASCADE...")
            await conn.execute("DROP TABLE IF EXISTS user_info CASCADE")
            print("Dropped.")
            
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
