from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import PlainTextResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
import os

app = FastAPI()

# === LINE 設定 ===
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === Gemini 設定 ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemma-3n-e4b-it",
    generation_config={
        "temperature": 0.7,
        "max_output_tokens": 1024,
    }
)

# === 全域 dict 保存上下文 ===
user_context = {}  # {user_id: [msg1, msg2, ...]}

# === Render 健康檢查 ===
@app.get("/")
async def root():
    return {"status": "OK", "message": "LINE Gemini Bot is running with context."}

# === LINE Webhook ===
@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return PlainTextResponse("OK", status_code=200)

# === 訊息處理 ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    # 取得舊上下文
    context = user_context.get(user_id, [])

    # 新增這次訊息
    context.append(f"使用者: {user_message}")
    # 限制只保留最近 5 則
    if len(context) > 5:
        context = context[-5:]
    user_context[user_id] = context

    # 檢查指令
    if user_message.startswith("#摘要"):
        reply_message = "（暫未串接）這裡會幫你做文章摘要"
    elif user_message.startswith("#翻譯"):
        reply_message = "（暫未串接）這裡會幫你翻譯文字"
    else:
        try:
            # 把上下文傳給 Gemini
            prompt = f"""
你是阿統，一個有個性的聊天機器人。雖然不喜歡做事，但通常很心軟，會幫我做摘要、解程式，也會聊天。
若用戶沒有特別指令，就用你的個性回應。
以下是最近的對話紀錄（含使用者與阿統）：
{chr(10).join(context)}

現在使用者最新的訊息是：
{user_message}

請根據上下文繼續回應。
"""
            response = model.generate_content(prompt)
            reply_message = response.text

            # 把 AI 回覆也存入上下文
            context.append(f"阿統: {reply_message}")
            if len(context) > 5:
                context = context[-5:]
            user_context[user_id] = context

        except Exception as e:
            reply_message = f"目前無法使用 Gemini，已切換簡易回覆：{user_message}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )


