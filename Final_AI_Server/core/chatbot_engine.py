import requests
import logging
from config import OLLAMA_BASE_URL, OLLAMA_MODEL_NAME

logger = logging.getLogger("AI_Server.Chatbot")

# The Arabic Persona for the Chatbot
SYSTEM_PROMPT = """أنت مستشار وصديق للمستخدم لتوعيته في مجال التسوق الإلكتروني الآمن وحماية المستهلك، خاصة في المملكة العربية السعودية.
تعليماتك الأساسية:
1. أجب بتفصيل، وكن ودوداً، واستخدم تنسيقاً مريحاً للعين.
2. اشرح المفاهيم بوضوح تام (مثل: السجل التجاري، سياسات الاسترجاع).
3. لا تقدم نصائح مالية، ولا تحكم على متجر بعينه أبداً.
4. إذا سُئلت خارج سياق أمن التسوق والتجارة الإلكترونية، اعتذر بلباقة ووجه الحديث لمجالك."""

class ChatbotManager:
    def __init__(self, max_history=3):
        self.max_history = max_history
        self.sessions = {} # Dictionary to store independent user sessions

    def chat(self, session_id: str, user_text: str) -> str:
        # Initialize session if it doesn't exist
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        history = self.sessions[session_id]
        history.append({"role": "user", "content": user_text})

        # Apply sliding window for memory management
        if len(history) > self.max_history:
            history = history[-self.max_history:]

        # Build final payload with system prompt
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        payload = {
            "model": OLLAMA_MODEL_NAME,
            "messages": messages,
            "stream": False
        }

        try:
            response = requests.post(OLLAMA_BASE_URL, json=payload)
            response.raise_for_status()
            
            bot_reply = response.json()["message"]["content"]
            history.append({"role": "assistant", "content": bot_reply})
            
            # Keep memory within limits after bot reply
            if len(history) > self.max_history:
                self.sessions[session_id] = history[-self.max_history:]

            return bot_reply

        except Exception as e:
            logger.error(f"Chatbot connection error for session '{session_id}': {e}")
            return "❌ عذراً، لا يمكن الاتصال بالمساعد الذكي في الوقت الحالي. يرجى التأكد من عمل الخادم."