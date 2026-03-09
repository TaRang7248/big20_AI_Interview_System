import sys
import os
import shutil

# Add the project root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
sys.path.append(BASE_DIR)

from packages.imh_core.logging import get_logger

logger = get_logger("verification_script")

def verify_logging():
    print(f"Base Directory: {BASE_DIR}")
    
    # Generate logs
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")
    
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("This is an INTENTIONAL EXCEPTION")

    # Verify files existence
    agent_log = os.path.join(BASE_DIR, "logs", "agent", "agent.log")
    error_log = os.path.join(BASE_DIR, "logs", "agent", "agent.error.log")
    
    if os.path.exists(agent_log):
        print(f"[SUCCESS] {agent_log} exists.")
        with open(agent_log, "r", encoding="utf-8") as f:
            content = f.read()
            if "DEBUG message" in content and "INTENTIONAL EXCEPTION" in content:
                print(f"[SUCCESS] agent.log contains generated logs.")
            else:
                print(f"[FAILURE] agent.log missing expected content.")
    else:
         print(f"[FAILURE] {agent_log} does not exist.")

    if os.path.exists(error_log):
        print(f"[SUCCESS] {error_log} exists.")
        with open(error_log, "r", encoding="utf-8") as f:
            content = f.read()
            if "ERROR message" in content and "INTENTIONAL EXCEPTION" in content:
                print(f"[SUCCESS] agent.error.log contains generated error logs.")
            if "DEBUG message" in content:
                print(f"[FAILURE] agent.error.log contains DEBUG logs (should not).")
            else:
                 print(f"[SUCCESS] agent.error.log does not contain DEBUG logs.")

    else:
         print(f"[FAILURE] {error_log} does not exist.")

if __name__ == "__main__":
    verify_logging()
