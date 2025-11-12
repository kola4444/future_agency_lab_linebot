import os
import requests
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_API_BASE_URL = os.getenv("DIFY_API_BASE_URL", "https://api.dify.ai/v1")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = FastAPI()
conversation_history = {}

@app.get("/")
def root():
    return {"status": "ok", "message": "Future Agency Lab LINE Bot is running"}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_message = event.message.text
    reply_text = query_dify(user_id, user_message)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

def query_dify(user_id, text):
    url = f"{DIFY_API_BASE_URL}/chat-messages"
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}

    payload = {
        "inputs": {},
        "query": text,
        "response_mode": "blocking",
        "user": user_id
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("answer", "すみません、うまく応答できませんでした。")
    except:
        return "システムエラーが発生しました。しばらくして再度お試しください。"

