"""
Test asyncpg JSONB handling

Test how asyncpg handles JSONB columns
"""

import asyncio
import asyncpg
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

async def test_jsonb():
    """Test JSONB insert and retrieve"""
    
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(conn_str)
    
    try:
        print("=== Testing JSONB Handling ===\n")
        
        # Test data
        test_data = {"version": "1.0", "test": "data", "number": 123}
        test_id = "test-jsonb-001"
        
        # Clean up first
        await conn.execute("DELETE FROM reports WHERE report_id = $1", test_id)
        
        # Method 1: json.dumps() (STRING)
        print("Method 1: Using json.dumps()")
        try:
            await conn.execute(
                "INSERT INTO reports (report_id, report_data, created_at) VALUES ($1, $2, NOW())",
                test_id,
                json.dumps(test_data)
            )
            print("  ✓ INSERT successful with json.dumps()")
            
            row = await conn.fetchrow("SELECT report_data FROM reports WHERE report_id = $1", test_id)
            retrieved_data = row['report_data']
            
            print(f"  Type retrieved: {type(retrieved_data)}")
            print(f"  Value: {retrieved_data}")
            print(f"  Equals original: {retrieved_data == test_data}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        await conn.execute("DELETE FROM reports WHERE report_id = $1", test_id)
        
        # Method 2: Direct dict
        print("\nMethod 2: Using dict directly")
        try:
            await conn.execute(
                "INSERT INTO reports (report_id, report_data, created_at) VALUES ($1, $2, NOW())",
                test_id,
                test_data  # Direct dict
            )
            print("  ✓ INSERT successful with dict")
            
            row = await conn.fetchrow("SELECT report_data FROM reports WHERE report_id = $1", test_id)
            retrieved_data = row['report_data']
            
            print(f"  Type retrieved: {type(retrieved_data)}")
            print(f"  Value: {retrieved_data}")
            print(f"  Equals original: {retrieved_data == test_data}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        await conn.execute("DELETE FROM reports WHERE report_id = $1", test_id)
        
        # Method 3: Using CAST
        print("\nMethod 3: Using explicit CAST to JSONB")
        try:
            await conn.execute(
                "INSERT INTO reports (report_id, report_data, created_at) VALUES ($1, $2::jsonb, NOW())",
                test_id,
                json.dumps(test_data)
            )
            print("  ✓ INSERT successful with ::jsonb cast")
            
            row = await conn.fetchrow("SELECT report_data FROM reports WHERE report_id = $1", test_id)
            retrieved_data = row['report_data']
            
            print(f"  Type retrieved: {type(retrieved_data)}")
            print(f"  Value: {retrieved_data}")
            print(f"  Equals original: {retrieved_data == test_data}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        # Clean up
        await conn.execute("DELETE FROM reports WHERE report_id = $1", test_id)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_jsonb())
