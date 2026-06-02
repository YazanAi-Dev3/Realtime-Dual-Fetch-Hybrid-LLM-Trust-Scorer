import requests
import json
import time

# إعدادات السيرفر
BASE_URL = "http://localhost:8000"
ANALYZE_ENDPOINT = f"{BASE_URL}/api/analyze"
CHAT_ENDPOINT = f"{BASE_URL}/api/chat"

def print_header(title: str):
    print("\n" + "="*60)
    print(f" {title} ".center(60, "="))
    print("="*60)

def print_json(data: dict):
    # طباعة الـ JSON بشكل مرتب ومقروء وداعم للغة العربية
    print(json.dumps(data, indent=4, ensure_ascii=False))

def test_ai_server():
    try:
        # التأكد من أن السيرفر يعمل قبل بدء الاختبار
        requests.get(f"{BASE_URL}/docs", timeout=5)
    except requests.exceptions.ConnectionError:
        print("❌ السيرفر لا يعمل! يرجى تشغيل 'python main.py' أولاً.")
        return

    # ======================================================
    # 1. اختبار خدمة مستشار التسوق (Chatbot API)
    # ======================================================
    print_header("1. TESTING CHATBOT API")
    session_id = "test_user_99" # توحيد الجلسة لاختبار الذاكرة
    
    # الطلب الأول: سؤال عام
    msg1 = "مرحباً، ما هو السجل التجاري؟"
    print(f"👤 المستخدم ({session_id}): {msg1}")
    print("⏳ جاري انتظار رد المستشار...")
    
    res_chat1 = requests.post(CHAT_ENDPOINT, json={"session_id": session_id, "message": msg1})
    if res_chat1.status_code == 200:
        print(f"🤖 المستشار:\n{res_chat1.json().get('reply')}\n")
    else:
        print(f"❌ خطأ: {res_chat1.status_code}")

    # الطلب الثاني: سؤال مبني على السياق السابق لاختبار الذاكرة (Sliding Window)
    msg2 = "ولماذا من المهم أن أتحقق منه قبل الشراء؟"
    print(f"👤 المستخدم ({session_id}): {msg2}")
    print("⏳ جاري انتظار رد المستشار...")
    
    res_chat2 = requests.post(CHAT_ENDPOINT, json={"session_id": session_id, "message": msg2})
    if res_chat2.status_code == 200:
        print(f"🤖 المستشار:\n{res_chat2.json().get('reply')}\n")
    else:
        print(f"❌ خطأ: {res_chat2.status_code}")


    # ======================================================
    # 2. اختبار خدمة محرك تقييم الموثوقية (Analyzer API)
    # ======================================================
    print_header("2. TESTING ANALYZER API")
    print("⚠️ ملاحظة: هذه الخدمة قد تستغرق من 10 إلى 30 ثانية لكل متجر بسبب القشط والذكاء الاصطناعي.\n")

    stores_to_test = [
        "https://laverne.com",
        "https://niceonesa.com"
    ]

    for index, url in enumerate(stores_to_test, 1):
        print(f"🔍 [Test {index}] Analyzing Store: {url}")
        print("⏳ جاري القشط والتحليل... الرجاء الانتظار...")
        
        start_time = time.time()
        res_analyze = requests.post(ANALYZE_ENDPOINT, json={"url": url})
        elapsed_time = round(time.time() - start_time, 2)
        
        if res_analyze.status_code == 200:
            print(f"✅ تم التحليل بنجاح في {elapsed_time} ثانية!")
            print("📊 النتيجة:")
            # طباعة النتيجة النهائية بشكل منسق
            data = res_analyze.json()
            if "trust_evaluation" in data:
                score = data["trust_evaluation"].get("total_score")
                tier = data["trust_evaluation"].get("tier")
                print(f"   -> Score: {score}/100")
                print(f"   -> Tier : {tier}")
                print("\n   [Full JSON Response]:")
                print_json(data)
            else:
                print_json(data)
        else:
            print(f"❌ خطأ في تحليل المتجر: {res_analyze.status_code}")
            print(res_analyze.text)
        print("-" * 60)

if __name__ == "__main__":
    test_ai_server()