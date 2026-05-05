# Skill: LINE Bot 股票查詢機器人開發指南

## 目標

將現有的 **FastAPI + Gemini + SQLite 網頁聊天機器人**，擴充成可透過 LINE 操作的股票查詢 Bot。

---

## 1. SDK 版本要求

> **必須使用 `line-bot-sdk-python` v3，嚴禁使用 v2 舊寫法。**

### v2 vs v3 Import 寫法差異

| 功能 | v2（舊，禁用） | v3（新，必用） |
|---|---|---|
| LineBotApi | `from linebot import LineBotApi` | `from linebot.v3.messaging import ApiClient, MessagingApi` |
| WebhookHandler | `from linebot import WebhookHandler` | `from linebot.v3.webhook import WebhookParser` |
| TextSendMessage | `from linebot.models import TextSendMessage` | `from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage` |
| MessageEvent | `from linebot.models import MessageEvent` | `from linebot.v3.webhooks.models import MessageEvent, TextMessageContent` |
| Configuration | 無 | `from linebot.v3.messaging import Configuration` |

### v3 正確初始化範例

```python
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks.models import MessageEvent, TextMessageContent

configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
parser = WebhookParser(channel_secret=os.environ["LINE_CHANNEL_SECRET"])

with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)
```

---

## 2. FastAPI Webhook 路由規範

- Webhook 路由**必須是 `POST /callback`**
- 路徑不可更改為其他名稱（LINE 平台設定需對應）

```python
@app.post("/callback")
async def callback(request: Request):
    ...
```

---

## 3. X-Line-Signature 驗證

每次收到 LINE Webhook 時，**必須驗證 `X-Line-Signature` Header**，否則任何人都能偽造請求。

```python
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        events = parser.parse(body_text, signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    ...
```

---

## 4. Webhook 回傳規範

- Webhook 成功處理後，**必須回傳 HTTP 200 OK**
- 若不回傳 200，LINE 平台會認定失敗並重試

```python
    return {"status": "ok"}  # FastAPI 預設回傳 200
```

---

## 5. Event Handler 規範

### 必須使用 `MessageEvent` + `TextMessageContent`

```python
from linebot.v3.webhooks.models import MessageEvent, TextMessageContent

for event in events:
    if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
        user_id = event.source.user_id
        user_message = event.message.text
        reply_token = event.reply_token
        # 處理訊息...
```

---

## 6. replyToken 使用規範

> **`replyToken` 只能使用一次**，且有時效限制（約 30 秒內）。

- 不可重複呼叫同一個 `replyToken`
- 不可儲存 `replyToken` 供之後使用
- 一個事件只能 reply 一次；若需多次主動傳訊，改用 Push Message

```python
# 正確：reply 一次
line_bot_api.reply_message(
    ReplyMessageRequest(
        reply_token=reply_token,
        messages=[TextMessage(text=bot_reply)]
    )
)
```

---

## 7. 環境變數管理

> **任何金鑰、Token 都不能寫死在程式碼中。**

所有敏感資訊必須透過環境變數讀取：

```python
import os
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
```

---

## 8. .env 檔案規範

### 必要的環境變數

`.env` 檔案必須包含以下三個變數：

```env
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here
LINE_CHANNEL_SECRET=your_channel_secret_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### .env.example（可 commit 的範本）

```env
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
GEMINI_API_KEY=
```

> **`.env` 必須加入 `.gitignore`，嚴禁 commit 到版本控制。**

---

## 9. Gemini 股票回覆整合

使用 Gemini API 根據使用者訊息產生股票相關回覆。

```python
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

def get_stock_reply(user_message: str) -> str:
    prompt = f"""你是一個股票資訊助理。
使用者詢問：{user_message}
請提供繁體中文的股票相關回答，包含股價分析、市場趨勢或投資建議。
若問題與股票無關，請禮貌引導回股票話題。"""
    response = model.generate_content(prompt)
    return response.text
```

---

## 10. SQLite 互動紀錄規範

必須使用 SQLite 記錄所有 LINE 使用者的互動紀錄，資料表**至少**包含以下欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | 自動編號 |
| `user_id` | TEXT NOT NULL | LINE 使用者 ID |
| `user_message` | TEXT NOT NULL | 使用者傳送的訊息 |
| `bot_reply` | TEXT NOT NULL | Bot 回覆的內容 |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | 互動時間戳記 |

### 建立資料表範例

```python
import sqlite3

DB_PATH = "chat.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_interactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            user_message TEXT NOT NULL,
            bot_reply   TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_interaction(user_id: str, user_message: str, bot_reply: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO line_interactions (user_id, user_message, bot_reply) VALUES (?, ?, ?)",
        (user_id, user_message, bot_reply)
    )
    conn.commit()
    conn.close()
```

---

## 11. 常見地雷（避坑清單）

| 地雷 | 說明與解法 |
|---|---|
| ❌ Webhook URL 忘記加 `/callback` | LINE 後台填寫的 Webhook URL 必須是 `https://xxxx.ngrok.io/callback`，不能只填 domain |
| ❌ ngrok 重啟後網址改變 | 每次重啟 ngrok 都會換網址，需更新 LINE 後台的 Webhook URL；建議使用固定 ngrok domain |
| ❌ Auto-reply messages 沒關閉 | LINE 後台的「自動回應訊息」和「加入好友的歡迎訊息」必須關閉，否則 Bot 會回應兩次 |
| ❌ replyToken 重複使用 | 同一個 replyToken 只能呼叫一次 reply_message，重複呼叫會得到 400 錯誤 |
| ❌ `.env` 被 commit | `.env` 必須在 `.gitignore` 中，金鑰洩漏到 GitHub 非常危險 |
| ❌ Token 寫死在 app.py | 所有金鑰都必須用環境變數，不能直接寫在程式碼裡 |
| ❌ 使用 v2 import 語法 | v3 的 import 路徑完全不同，混用會導致 ImportError |
| ❌ 未回傳 200 | LINE 平台會認定 Webhook 失敗並重試，造成重複處理 |

---

## 12. 常見 LINE Event 類型

| Event 類型 | 說明 |
|---|---|
| `MessageEvent` | 使用者傳送訊息時觸發（最常用） |
| `FollowEvent` | 使用者加 Bot 為好友時觸發 |
| `UnfollowEvent` | 使用者封鎖 Bot 時觸發 |
| `JoinEvent` | Bot 被加入群組時觸發 |
| `LeaveEvent` | Bot 被移出群組時觸發 |
| `PostbackEvent` | 使用者點擊 Postback Action 按鈕時觸發 |
| `BeaconEvent` | 使用者進入 Beacon 範圍時觸發 |
| `MemberJoinedEvent` | 成員加入群組時觸發 |
| `MemberLeftEvent` | 成員離開群組時觸發 |

---

## 13. 常見 LINE Message 類型

| Message 類型 | 說明 |
|---|---|
| `TextMessage` | 純文字訊息 |
| `ImageMessage` | 圖片訊息 |
| `VideoMessage` | 影片訊息 |
| `AudioMessage` | 音訊訊息 |
| `FileMessage` | 檔案訊息 |
| `LocationMessage` | 位置訊息 |
| `StickerMessage` | 貼圖訊息 |
| `TemplateMessage` | 範本訊息（按鈕、確認、輪播等） |
| `FlexMessage` | Flex 自訂排版訊息 |

---

## 14. 開發前 Checklist

在開始開發前，確認以下所有項目：

- [ ] 已在 [LINE Developers Console](https://developers.line.biz/) 建立 Messaging API Channel
- [ ] 已取得 **Channel Access Token**（Long-lived）
- [ ] 已取得 **Channel Secret**
- [ ] 已將兩組金鑰填入 `.env` 檔案（勿 commit）
- [ ] `.env` 已加入 `.gitignore`
- [ ] 已在 LINE 後台關閉「自動回應訊息」
- [ ] 已在 LINE 後台關閉「加入好友的歡迎訊息」（或視需求保留）
- [ ] 已安裝 `line-bot-sdk-python >= 3.0.0`（確認 v3）
- [ ] 已安裝 `ngrok` 或其他 tunnel 工具
- [ ] Webhook URL 已設定為 `https://<your-domain>/callback`
- [ ] 已在 LINE 後台點擊「Verify」確認 Webhook 連線正常
- [ ] Gemini API Key 已取得並填入 `.env`

---

## 15. 完成後需產出的檔案

| 檔案 | 說明 |
|---|---|
| `app.py` | 主程式，包含 FastAPI、LINE Webhook、Gemini 整合、SQLite 紀錄 |
| `requirements.txt` | 所有相依套件，須包含 `line-bot-sdk>=3.0.0`、`fastapi`、`uvicorn`、`google-generativeai`、`python-dotenv` |
| `.env.example` | 環境變數範本（不含真實金鑰），可 commit |
| `README.md` | 專案說明，包含安裝步驟、啟動方式、LINE 後台設定說明、ngrok 使用說明 |

### requirements.txt 範例

```txt
fastapi
uvicorn[standard]
line-bot-sdk>=3.0.0
google-generativeai
python-dotenv
```

### README.md 建議章節

1. 專案簡介
2. 環境需求
3. 安裝步驟
4. 設定環境變數（`.env`）
5. 啟動應用程式（`uvicorn app:app --reload`）
6. 使用 ngrok 建立公開 URL
7. LINE 後台 Webhook 設定
8. 功能說明
9. 資料庫結構

---

## 參考資源

- [LINE Bot SDK Python v3 官方文件](https://github.com/line/line-bot-sdk-python)
- [LINE Developers Console](https://developers.line.biz/)
- [LINE Messaging API 文件](https://developers.line.biz/en/docs/messaging-api/)
- [ngrok 官網](https://ngrok.com/)
- [Google Gemini API 文件](https://ai.google.dev/docs)
