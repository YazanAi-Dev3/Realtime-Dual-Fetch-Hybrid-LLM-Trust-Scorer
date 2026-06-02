import csv
import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette import status
from pydantic import BaseModel
import uvicorn

from config import SERVER_PORT
from logger_config import logger

from core.chatbot_engine import ChatbotManager
from core.analyzer_engine import run_trust_pipeline

app = FastAPI(title="Store Trust & Advisor API", version="1.0")
chatbot_manager = ChatbotManager()

# CORS and preflight handling for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
    max_age=600,
)

# Auto-create data directories and CSV files
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CHAT_CSV = DATA_DIR / "chatbot_sessions.csv"
ANALYZER_CSV = DATA_DIR / "analyzer_records.csv"

# Initialize CSV headers if files do not exist
if not CHAT_CSV.exists():
    with open(CHAT_CSV, mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(["Timestamp", "SessionID", "UserMessage", "BotReply"])

if not ANALYZER_CSV.exists():
    with open(ANALYZER_CSV, mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(["Timestamp", "TargetURL", "Score", "Tier"])

# --- Request Models ---
class ChatRequest(BaseModel):
    session_id: str
    message: str

class AnalyzeRequest(BaseModel):
    url: str

# --- Endpoints ---
@app.options("/{path:path}")
async def options_handler(path: str):
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    logger.info(f"Received chat request from session: {request.session_id}")
    try:
        reply = chatbot_manager.chat(request.session_id, request.message)
        
        # Log to CSV
        with open(CHAT_CSV, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.datetime.now().isoformat(), request.session_id, request.message, reply])
            
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error during chat processing")

@app.post("/api/analyze")
async def analyze_endpoint(request: AnalyzeRequest):
    logger.info(f"Received analysis request for URL: {request.url}")
    
    try:
        result = run_trust_pipeline(request.url)
        
        if result.get("status") == "success":
            score = result["trust_evaluation"]["total_score"]
            tier = result["trust_evaluation"]["tier"]
        else:
            score, tier = 0, "Error"
        
        with open(ANALYZER_CSV, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.datetime.now().isoformat(), request.url, score, tier])
            
        return result
        
    except Exception as e:
        logger.error(f"Analyze Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting AI Microservice Server...")
    uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)