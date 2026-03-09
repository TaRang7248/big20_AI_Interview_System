import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("verify_qbank")

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from packages.imh_qbank.db_repository import DBQuestionRepository

async def main():
    repo = DBQuestionRepository()
    
    logger.info("--- Testing get_random_questions(3) ---")
    random_qs = await repo.get_random_questions(limit=3)
    for q in random_qs:
        logger.info(f"ID: {q.id} | Content: {q.content[:50]}...")
        
    logger.info("\n--- Testing get_by_category('general', 3) ---")
    cat_qs = await repo.get_by_category("general", limit=3)
    for q in cat_qs:
        logger.info(f"ID: {q.id} | Content: {q.content[:50]}...")
        
    logger.info("\n--- Testing get_by_tag('non-existent-tag', 3) ---")
    tag_qs = await repo.get_by_tag("non-existent-tag", limit=3)
    logger.info(f"Found {len(tag_qs)} questions with tag 'non-existent-tag'")
    
    logger.info("\nVerification complete.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
