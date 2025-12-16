import os
import requests
import logging
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_API_BASE_URL = os.getenv("DIFY_API_BASE_URL", "https://api.dify.ai/v1")

logger.info("=== Starting Future Agency Lab LINE Bot ===")
logger.info(f"LINE_CHANNEL_ACCESS_TOKEN: {'SET' if LINE_CHANNEL_ACCESS_TOKEN else 'NOT SET'}")
logger.info(f"LINE_CHANNEL_SECRET: {'SET' if LINE_CHANNEL_SECRET else 'NOT SET'}")
logger.info(f"DIFY_API_KEY: {'SET' if DIFY_API_KEY else 'NOT SET'}")
logger.info(f"DIFY_API_BASE_URL: {DIFY_API_BASE_URL}")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = FastAPI()
conversation_history = {}

@app.get("/")
def root():
    logger.info("Health check endpoint accessed")
    return {"status": "ok", "message": "Future Agency Lab LINE Bot is running"}

@app.post("/webhook")
async def webhook(request: Request):
    logger.info("=== Webhook received ===")
    
    try:
        body = await request.body()
        signature = request.headers.get("X-Line-Signature", "")
        
        logger.info(f"Request body length: {len(body)}")
        logger.info(f"Signature present: {'Yes' if signature else 'No'}")
        
        handler.handle(body.decode("utf-8"), signature)
        return {"status": "ok"}
        
    except InvalidSignatureError as e:
        logger.error(f"Invalid signature error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Unexpected error in webhook: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

@handler.add(MessageEvent, message=TextSendMessage)
def handle_text(event):
    try:
        user_id = event.source.user_id
        user_message = event.message.text
        
        logger.info(f"=== New message from user {user_id} ===")
        logger.info(f"Message: {user_message}")
        
        reply_text = query_dify(user_id, user_message)
        
        logger.info(f"Reply text: {reply_text}")
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        
        logger.info("Reply sent successfully")
        
    except Exception as e:
        logger.error(f"Error in handle_text: {str(e)}", exc_info=True)
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="申し訳ございません。システムエラーが発生しました。しばらくしてから再度お試しください。")
            )
        except Exception as reply_error:
            logger.error(f"Error sending error message: {str(reply_error)}")

def query_dify(user_id, text):
    logger.info(f"=== Querying Dify API ===")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Query: {text}")
    
    url = f"{DIFY_API_BASE_URL}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {},
        "query": text,
        "response_mode": "blocking",
        "user": user_id
    }
    
    logger.info(f"API URL: {url}")
    logger.info(f"Payload: {payload}")
    
    try:
        logger.info("Sending request to Dify...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Response data: {data}")
        
        # Dify APIのレスポンス形式に応じて処理
        if "answer" in data:
            answer = data.get("answer", "")
            logger.info(f"Answer found: {answer}")
            return answer
        elif "message" in data:
            message = data.get("message", "")
            logger.info(f"Message found: {message}")
            return message
        else:
            logger.warning(f"Unexpected response format: {data}")
            return "すみません、うまく応答できませんでした。"
            
    except requests.exceptions.Timeout as e:
        logger.error(f"Dify API timeout: {str(e)}")
        return "申し訳ございません。応答に時間がかかりすぎています。しばらくしてから再度お試しください。"
    except requests.exceptions.HTTPError as e:
        logger.error(f"Dify API HTTP error: {str(e)}")
        logger.error(f"Response content: {e.response.text if e.response else 'No response'}")
        return "申し訳ございません。AIサービスとの通信でエラーが発生しました。"
    except requests.exceptions.RequestException as e:
        logger.error(f"Dify API request error: {str(e)}")
        return "申し訳ございません。ネットワークエラーが発生しました。"
    except Exception as e:
        logger.error(f"Unexpected error in query_dify: {str(e)}", exc_info=True)
        return "申し訳ございません。予期しないエラーが発生しました。"
