import logging
import os
from pathlib import Path

# Auto-create logs directory
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "server.log", encoding='utf-8'),
        logging.StreamHandler() # Outputs to console as well
    ]
)

logger = logging.getLogger("AI_Server")