import os
import logging
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import requests
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション
app = FastAPI()

# LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_API_BASE_URL = os.getenv("DIFY_API_BASE_URL", "https://api.dify.ai/v1")

# 環境変数チェック
logger.info("=== Starting Future Agency Lab LINE Bot ===")
logger.info(f"LINE_CHANNEL_ACCESS_TOKEN: {'SET' if LINE_CHANNEL_ACCESS_TOKEN else 'NOT SET'}")
logger.info(f"LINE_CHANNEL_SECRET: {'SET' if LINE_CHANNEL_SECRET else 'NOT SET'}")
logger.info(f"DIFY_API_KEY: {'SET' if DIFY_API_KEY else 'NOT SET'}")
logger.info(f"DIFY_API_BASE_URL: {DIFY_API_BASE_URL}")

# LINE Messaging API設定
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.get("/")
async def root():
    """ヘルスチェック用エンドポイント"""
    return {
        "status": "ok",
        "message": "Future Agency Lab LINE Bot is running"
    }


@app.post("/webhook")
async def webhook(request: Request):
    """LINE Webhookエンドポイント"""
    logger.info("=== Webhook received ===")
    
    # リクエストボディを取得
    body = await request.body()
    body_str = body.decode('utf-8')
    logger.info(f"Request body length: {len(body_str)}")
    
    # 署名検証
    signature = request.headers.get('X-Line-Signature', '')
    logger.info(f"Signature present: {'Yes' if signature else 'No'}")
    
    try:
        # Webhookハンドラーで署名検証とイベント処理
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature error")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error in webhook handler: {str(e)}")
        logger.error(traceback.format_exc())
    
    return JSONResponse(content={"status": "ok"})


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """メッセージイベントハンドラー"""
    try:
        # ユーザーメッセージを取得
        user_message = event.message.text
        user_id = event.source.user_id
        
        logger.info(f"=== Message received ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Message: {user_message}")
        
        # Dify APIに問い合わせ
        logger.info("Querying Dify API...")
        dify_response = query_dify(user_message, user_id)
        logger.info(f"Dify response: {dify_response[:100]}...")  # 最初の100文字のみログ出力
        
        # LINEに返信
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=dify_response)]
                )
            )
        
        logger.info("Reply sent successfully")
        
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        logger.error(traceback.format_exc())
        
        # エラー時もユーザーに返信
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="申し訳ございません。システムエラーが発生しました。しばらくしてから再度お試しください。")]
                    )
                )
        except Exception as reply_error:
            logger.error(f"Error sending error message: {str(reply_error)}")


def query_dify(user_message: str, user_id: str) -> str:
    """Dify APIに問い合わせて応答を取得"""
    try:
        url = f"{DIFY_API_BASE_URL}/chat-messages"
        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": {},
            "query": user_message,
            "response_mode": "blocking",
            "user": user_id
        }
        
        logger.info(f"Dify API URL: {url}")
        logger.info(f"Dify API payload: {payload}")
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        logger.info(f"Dify API status code: {response.status_code}")
        logger.info(f"Dify API response: {response.text[:200]}...")  # 最初の200文字のみ
        
        response.raise_for_status()
        data = response.json()
        
        # レスポンスから回答を抽出
        if "answer" in data:
            return data["answer"]
        elif "message" in data:
            return data["message"]
        else:
            logger.warning(f"Unexpected Dify response structure: {data}")
            return "申し訳ございません。応答の取得に失敗しました。"
            
    except requests.exceptions.Timeout:
        logger.error("Dify API timeout")
        return "申し訳ございません。応答に時間がかかりすぎています。しばらくしてから再度お試しください。"
    except requests.exceptions.HTTPError as e:
        logger.error(f"Dify API HTTP error: {e}")
        logger.error(f"Response content: {e.response.text}")
        return "申し訳ございません。AIサービスでエラーが発生しました。"
    except requests.exceptions.RequestException as e:
        logger.error(f"Dify API request error: {e}")
        return "申し訳ございません。通信エラーが発生しました。"
    except Exception as e:
        logger.error(f"Unexpected error in query_dify: {str(e)}")
        logger.error(traceback.format_exc())
        return "申し訳ございません。予期しないエラーが発生しました。"


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
