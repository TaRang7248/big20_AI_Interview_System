import sys
import os
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("verify_full_read_replay")

# Env setup
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("POSTGRES_CONNECTION_STRING"):
    print("SKIPPING: POSTGRES_CONNECTION_STRING not found in env.")
    sys.exit(0)

# Import dependencies
try:
    from IMH.api.dependencies import get_session_state_repository
    from packages.imh_session.infrastructure.dual_repo import DualSessionStateRepository
    from packages.imh_session.infrastructure.memory_repo import MemorySessionRepository
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def deep_compare(d1: Dict, d2: Dict, path: str = "") -> list:
    errors = []
    # Keys
    keys1 = set(d1.keys())
    keys2 = set(d2.keys())
    
    if keys1 != keys2:
        missing_in_2 = keys1 - keys2
        missing_in_1 = keys2 - keys1
        if missing_in_2: errors.append(f"{path} Keys missing in Postgres: {missing_in_2}")
        if missing_in_1: errors.append(f"{path} Extra keys in Postgres: {missing_in_1}")
    
    # Values
    for key in keys1.intersection(keys2):
        val1 = d1[key]
        val2 = d2[key]
        
        current_path = f"{path}.{key}" if path else key
        
        # Simple types
        if type(val1) != type(val2):
             # Exception: Timestamp float vs int? or None
             if val1 is None and val2 is None: continue
             errors.append(f"{current_path} Type mismatch: {type(val1)} vs {type(val2)}")
             continue
        
        if isinstance(val1, dict):
            errors.extend(deep_compare(val1, val2, current_path))
        elif isinstance(val1, list):
            if len(val1) != len(val2):
                errors.append(f"{current_path} List length mismatch: {len(val1)} vs {len(val2)}")
            else:
                for i, (item1, item2) in enumerate(zip(val1, val2)):
                    if isinstance(item1, dict) and isinstance(item2, dict):
                        errors.extend(deep_compare(item1, item2, f"{current_path}[{i}]"))
                    elif item1 != item2:
                        errors.append(f"{current_path}[{i}] Value mismatch: {item1} vs {item2}")
        else:
            # Value check
            # Float tolerance for timestamps
            if isinstance(val1, float) and isinstance(val2, float):
                if abs(val1 - val2) > 0.001:
                     errors.append(f"{current_path} Float mismatch: {val1} vs {val2}")
            elif val1 != val2:
                errors.append(f"{current_path} Value mismatch: {val1} vs {val2}")
                
    return errors

def run_verification():
    print("=== Checkpoint 4.3: Full Read Replay Verification ===")
    
    repo = get_session_state_repository()
    
    if not isinstance(repo, DualSessionStateRepository):
        print("FAIL: Repository is not DualSessionStateRepository")
        sys.exit(1)
        
    primary = repo.primary
    secondary = repo.secondary
    
    if not isinstance(primary, MemorySessionRepository):
        print("FAIL: Primary is not MemorySessionRepository (Access to _store needed)")
        sys.exit(1)

    # 1. Get All Session IDs from Memory
    all_sessions = list(primary._store.keys())
    print(f"Total Sessions in Memory: {len(all_sessions)}")
    
    success_count = 0
    fail_count = 0
    mismatches = []
    
    for sid in all_sessions:
        # Fetch directly to bypass any service logic
        ctx_primary = primary.get_state(sid)
        ctx_secondary = secondary.get_state(sid)
        
        if not ctx_secondary:
            print(f"[FAIL] {sid}: Missing in Postgres")
            mismatches.append(f"{sid}: ID_MISS")
            fail_count += 1
            continue
            
        # Serialize to dict for comparison
        d1 = ctx_primary.model_dump(mode='json') if hasattr(ctx_primary, 'model_dump') else ctx_primary.dict()
        d2 = ctx_secondary.model_dump(mode='json') if hasattr(ctx_secondary, 'model_dump') else ctx_secondary.dict()
        
        # Compare
        diffs = deep_compare(d1, d2)
        
        if not diffs:
            success_count += 1
            # print(f"[PASS] {sid}")
        else:
            print(f"[FAIL] {sid}: Mismatches found")
            for d in diffs:
                print(f"  - {d}")
            mismatches.append(f"{sid}: PAYLOAD_DIFF")
            fail_count += 1

    print("\n--- Summary ---")
    print(f"Total: {len(all_sessions)}")
    print(f"PASS: {success_count}")
    print(f"FAIL: {fail_count}")
    
    if fail_count == 0:
        print("RESULT: GO")
    else:
        print("RESULT: NO-GO")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
