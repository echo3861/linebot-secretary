import os
from datetime import datetime
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import PlainTextResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI()

# ==========================================
# 1. 配置區域 (環境變數)
# ==========================================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Gemini 配置
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # 建議使用 flash 速度較快且穩定
    generation_config={"temperature": 0.7, "max_output_tokens": 1024}
)

# ==========================================
# 2. Google Calendar 工具類別
# ==========================================
class CalendarManager:
    def __init__(self, credential_path='credentials.json'):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        # 檢查金鑰是否存在，避免程式崩潰
        if os.path.exists(credential_path):
            self.creds = service_account.Credentials.from_service_account_file(
                credential_path, scopes=self.scopes)
            self.service = build('calendar', 'v3', credentials=self.creds)
        else:
            self.service = None

    def list_upcoming_events(self):
        if not self.service:
            return "⚠️ 找不到 credentials.json，日曆功能尚未啟動。"
        
        now = datetime.utcnow().isoformat() + 'Z' # 'Z' 表示 UTC 時間
        try:
            events_result = self.service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=5, singleEvents=True,
                orderBy='startTime').execute()
            events = events_result.get('items', [])

            if not events:
                return "阿統查過了，你接下來沒什麼正事，可以繼續休息。"
            
            res = "📅 幫你查好了，接下來的行程：\n"
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # 簡單格式化時間：2024-05-20T10:00:00+08:00 -> 05/20 10:00
                clean_time = start.split('T')[0][5:] + " " + (start.split('T')[1][:5] if 'T' in start else "")
                res += f"▫️ {clean_time}：{event['summary']}\n"
            return res
        except Exception as e:
            return f"❌ 讀取日曆時出錯了：{str(e)}"

cal_manager = CalendarManager()

# ==========================================
# 3. 聊天上下文與 Webhook
# ==========================================
user_context = {}  # {user_id: [messages]}

@app.get("/")
async def root():
    return {"status": "OK", "message": "Guard-Link Bot is online."}

@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return PlainTextResponse("OK", status_code=200)

# ==========================================
# 4. 訊息邏輯處理
# ==========================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # --- 1. 指令優先判定 ---
    if user_message == "#行程":
        reply_message = cal_manager.list_upcoming_events()
    
    elif user_message.startswith("#摘要"):
        reply_message = "（摘要功能開發中，請先餵我文章～）"
        
    # --- 2. 沒指令就進入 Gemini 聊天 ---
    else:
        # 管理上下文
        context = user_context.get(user_id, [])
        context.append(f"使用者: {user_message}")
        if len(context) > 6: context = context[-6:]
        user_context[user_id] = context

        try:
            prompt = f"""
你是阿統，一個有個性、講話有點機車但心地善良的助理。
你現在有權限讀取使用者的 Google 日曆。
當使用者說出「#行程」時，你會幫他查詢。
目前對話紀錄：
{chr(10).join(context)}

請根據上下文回應使用者的最新訊息。
"""
            response = model.generate_content(prompt)
            reply_message = response.text
            
            # 存入 AI 回應
            context.append(f"阿統: {reply_message}")
            user_context[user_id] = context
            
        except Exception as e:
            reply_message = "阿統現在腦袋有點卡住，晚點再聊。"

    # --- 3. 發送回覆 ---
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )
