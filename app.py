"""
AI 聊天機器人後端（含股票 LINE Bot 擴充）
技術棧：FastAPI + SQLite + Google Gemini API + LINE Bot SDK v3
"""

import os
import uuid
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from google import genai
from google.genai import types
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# ── LINE Bot SDK v3 import（必須使用 v3，不可用 v2 舊寫法）──────
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# ── 載入環境變數 ─────────────────────────────────────────────
load_dotenv()
GEMINI_API_KEY            = os.getenv("GEMINI_API_KEY", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET       = os.getenv("LINE_CHANNEL_SECRET", "")

# ── 設定 Gemini API (新版 google-genai SDK) ───────────────────
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ── LINE Bot v3 設定 ──────────────────────────────────────────
line_configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ── FastAPI 應用程式 ──────────────────────────────────────────
app = FastAPI(title="AI 聊天機器人 + 股票 LINE Bot", version="2.0.0")

# ── 資料庫路徑 ──────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "chat.db"
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════
# 資料庫初始化
# ════════════════════════════════════════════════════════════

def get_db():
    """取得 SQLite 連線"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 讓查詢結果可以用欄位名稱存取
    conn.execute("PRAGMA foreign_keys = ON")  # 啟用外鍵約束
    return conn


def init_db():
    """初始化資料庫，建立資料表"""
    conn = get_db()
    cursor = conn.cursor()

    # 建立 sessions 資料表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 建立 messages 資料表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            has_attachment INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)

    # 建立 user_preferences 資料表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 建立 line_interactions 資料表（LINE Bot 互動紀錄，本週新增）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_interactions (
            id           INTEGER  PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT     NOT NULL,
            user_message TEXT     NOT NULL,
            bot_reply    TEXT     NOT NULL,
            created_at   TEXT     NOT NULL
        )
    """)

    # 插入預設偏好設定
    defaults = [
        ("language", "zh-TW"),
        ("response_style", "friendly"),
        ("username", "使用者"),
    ]
    for key, value in defaults:
        cursor.execute("""
            INSERT OR IGNORE INTO user_preferences (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value), now()))

    conn.commit()
    conn.close()


def now() -> str:
    """回傳 ISO 8601 格式的當前時間"""
    return datetime.now().isoformat()


# ════════════════════════════════════════════════════════════
# Pydantic 資料模型
# ════════════════════════════════════════════════════════════

class CreateSessionRequest(BaseModel):
    title: str = "新對話"


class SendMessageRequest(BaseModel):
    content: str
    attachment_path: Optional[str] = None


class UpdatePreferencesRequest(BaseModel):
    language: Optional[str] = None
    response_style: Optional[str] = None
    username: Optional[str] = None


# ════════════════════════════════════════════════════════════
# 輔助函式
# ════════════════════════════════════════════════════════════

def get_preferences() -> dict:
    """從資料庫取得使用者偏好設定"""
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
    conn.close()
    return {row["key"]: json.loads(row["value"]) for row in rows}


def build_system_prompt(prefs: dict) -> str:
    """根據使用者偏好建立系統提示詞（記憶機制）"""
    style_map = {
        "friendly": "親切友善、使用日常語言、適時加入 emoji",
        "formal": "正式專業、使用學術用語、避免口語",
        "concise": "簡潔扼要、條列重點、避免冗言",
    }
    style = style_map.get(prefs.get("response_style", "friendly"), "親切友善")
    username = prefs.get("username", "使用者")
    lang = prefs.get("language", "zh-TW")

    return (
        f"你是一個聰明、有幫助的 AI 助理。"
        f"使用者的名字是「{username}」，請在適當時候稱呼他。"
        f"請用 {lang} 回覆。"
        f"回應風格：{style}。"
        f"如果使用者詢問天氣，請提醒他可以直接問「台北天氣」等具體問題，系統會自動查詢。"
    )


async def call_gemini(history: list, new_message: str, attachment_path: Optional[str] = None, prefs: dict = None) -> str:
    """呼叫 Gemini API 產生回覆（使用新版 google-genai SDK）"""
    if prefs is None:
        prefs = {}

    system_prompt = build_system_prompt(prefs)

    # 建立對話歷史格式（新版 SDK 格式）
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    # 加入當前訊息（含系統提示）
    if attachment_path and Path(attachment_path).exists():
        import PIL.Image
        img = PIL.Image.open(attachment_path)
        import io
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_bytes = buf.getvalue()
        contents.append(types.Content(role="user", parts=[
            types.Part(text=system_prompt + "\n\n" + new_message),
            types.Part(inline_data=types.Blob(mime_type="image/png", data=img_bytes))
        ]))
    else:
        contents.append(types.Content(role="user", parts=[types.Part(text=system_prompt + "\n\n" + new_message)]))

    response = gemini_client.models.generate_content(
        model="gemini-1.5-flash",
        contents=contents
    )
    return response.text


# ════════════════════════════════════════════════════════════
# 路由：前端頁面
# ════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """回傳前端 HTML 頁面"""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>找不到 templates/index.html</h1>", status_code=404)


# ════════════════════════════════════════════════════════════
# 路由：Session 管理
# ════════════════════════════════════════════════════════════

@app.post("/sessions")
async def create_session(req: CreateSessionRequest):
    """建立新聊天室"""
    session_id = str(uuid.uuid4())
    timestamp = now()

    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (session_id, req.title, timestamp, timestamp)
    )
    conn.commit()
    conn.close()

    return {"id": session_id, "title": req.title, "created_at": timestamp, "updated_at": timestamp}


@app.get("/sessions")
async def list_sessions():
    """列出所有聊天室（依更新時間降序排列）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """刪除指定聊天室（及其所有訊息）"""
    conn = get_db()
    result = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="找不到指定的聊天室")

    return {"message": "聊天室已刪除"}


# ════════════════════════════════════════════════════════════
# 路由：訊息管理
# ════════════════════════════════════════════════════════════

@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """取得指定聊天室的所有訊息"""
    conn = get_db()

    # 確認 session 存在
    session = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到指定的聊天室")

    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, req: SendMessageRequest):
    """
    發送訊息並獲取 AI 回覆
    - 先儲存使用者訊息
    - 讀取歷史對話作為上下文
    - 呼叫 Gemini API
    - 儲存 AI 回覆
    """
    conn = get_db()

    # 確認 session 存在
    session = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到指定的聊天室")

    timestamp = now()

    # 儲存使用者訊息
    user_msg_id = str(uuid.uuid4())
    has_attachment = 1 if req.attachment_path else 0
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp, has_attachment) VALUES (?, ?, ?, ?, ?, ?)",
        (user_msg_id, session_id, "user", req.content, timestamp, has_attachment)
    )

    # 讀取歷史訊息作為上下文（最多 20 則）
    history_rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT 20",
        (session_id,)
    ).fetchall()
    history = [{"role": row["role"], "content": row["content"]} for row in history_rows]

    # 取得使用者偏好（記憶機制）
    prefs = get_preferences()

    conn.commit()

    # 檢查是否為天氣查詢（工具整合）
    content_lower = req.content.lower()
    weather_keywords = ["天氣", "氣溫", "weather", "溫度", "下雨", "晴天"]
    ai_reply = ""

    if any(kw in content_lower for kw in weather_keywords):
        # 嘗試從訊息中提取城市名稱
        city_map = {
            "台北": "Taipei", "台中": "Taichung", "高雄": "Kaohsiung",
            "台南": "Tainan", "新竹": "Hsinchu", "桃園": "Taoyuan",
        }
        detected_city = None
        for zh, en in city_map.items():
            if zh in req.content:
                detected_city = (zh, en)
                break

        if detected_city:
            weather_info = await fetch_weather(detected_city[1])
            if weather_info:
                weather_context = f"[系統工具回傳的即時天氣資料]\n城市：{detected_city[0]}\n{weather_info}\n\n請根據以上天氣資料回覆使用者的問題。"
                ai_reply = await call_gemini(history[:-1], weather_context + "\n\n使用者問：" + req.content, None, prefs)
            else:
                ai_reply = await call_gemini(history, req.content, req.attachment_path, prefs)
        else:
            ai_reply = await call_gemini(history, req.content, req.attachment_path, prefs)
    else:
        # 一般對話
        ai_reply = await call_gemini(history, req.content, req.attachment_path, prefs)

    # 儲存 AI 回覆
    ai_msg_id = str(uuid.uuid4())
    ai_timestamp = now()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp, has_attachment) VALUES (?, ?, ?, ?, ?, ?)",
        (ai_msg_id, session_id, "assistant", ai_reply, ai_timestamp, 0)
    )

    # 更新 session 的 updated_at
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (ai_timestamp, session_id)
    )

    # 如果是第一輪對話，自動更新 session 標題
    msg_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()["cnt"]

    if msg_count <= 2:
        # 取前 20 字作為標題
        new_title = req.content[:20] + ("..." if len(req.content) > 20 else "")
        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))

    conn.commit()
    conn.close()

    return {
        "user_message": {
            "id": user_msg_id, "session_id": session_id, "role": "user",
            "content": req.content, "timestamp": timestamp, "has_attachment": bool(has_attachment)
        },
        "ai_message": {
            "id": ai_msg_id, "session_id": session_id, "role": "assistant",
            "content": ai_reply, "timestamp": ai_timestamp, "has_attachment": False
        }
    }


@app.post("/sessions/{session_id}/regenerate")
async def regenerate_response(session_id: str):
    """
    重新生成最後一則 AI 回覆（Regenerate）
    - 刪除最後一則 assistant 訊息
    - 重新呼叫 Gemini API
    """
    conn = get_db()

    # 取得最後一則 assistant 訊息
    last_ai = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY timestamp DESC LIMIT 1",
        (session_id,)
    ).fetchone()

    if not last_ai:
        conn.close()
        raise HTTPException(status_code=404, detail="沒有可重新生成的 AI 回覆")

    # 刪除最後一則 AI 訊息
    conn.execute("DELETE FROM messages WHERE id = ?", (last_ai["id"],))
    conn.commit()

    # 取得剩餘歷史訊息
    history_rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    ).fetchall()
    history = [{"role": row["role"], "content": row["content"]} for row in history_rows]

    if not history:
        conn.close()
        raise HTTPException(status_code=400, detail="沒有足夠的對話歷史")

    # 取出最後一則使用者訊息
    last_user_content = history[-1]["content"]
    context_history = history[:-1]

    prefs = get_preferences()

    # 重新呼叫 Gemini
    ai_reply = await call_gemini(context_history, last_user_content, None, prefs)

    # 儲存新的 AI 回覆
    ai_msg_id = str(uuid.uuid4())
    ai_timestamp = now()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp, has_attachment) VALUES (?, ?, ?, ?, ?, ?)",
        (ai_msg_id, session_id, "assistant", ai_reply, ai_timestamp, 0)
    )
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (ai_timestamp, session_id))
    conn.commit()
    conn.close()

    return {
        "id": ai_msg_id,
        "session_id": session_id,
        "role": "assistant",
        "content": ai_reply,
        "timestamp": ai_timestamp,
        "has_attachment": False
    }


# ════════════════════════════════════════════════════════════
# 路由：檔案上傳
# ════════════════════════════════════════════════════════════

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上傳圖片或文件
    - 儲存到 uploads/ 目錄
    - 回傳檔案路徑供後續對話使用
    """
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf", "text/plain"]

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"不支援的檔案類型：{file.content_type}")

    # 產生唯一檔名
    ext = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / unique_filename

    # 儲存檔案
    content = await file.read()
    file_path.write_bytes(content)

    return {
        "filename": file.filename,
        "path": str(file_path),
        "content_type": file.content_type,
        "size": len(content)
    }


# ════════════════════════════════════════════════════════════
# 路由：天氣工具整合（Open-Meteo API）
# ════════════════════════════════════════════════════════════

CITY_COORDS = {
    "Taipei": (25.0330, 121.5654),
    "Taichung": (24.1477, 120.6736),
    "Kaohsiung": (22.6273, 120.3014),
    "Tainan": (22.9999, 120.2269),
    "Hsinchu": (24.8138, 120.9675),
    "Taoyuan": (24.9937, 121.3009),
}


async def fetch_weather(city_en: str) -> Optional[str]:
    """呼叫 Open-Meteo API 取得天氣資訊"""
    if city_en not in CITY_COORDS:
        return None

    lat, lon = CITY_COORDS[city_en]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        f"&timezone=Asia/Taipei"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            data = resp.json()

        current = data.get("current", {})
        temp = current.get("temperature_2m", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        wind_speed = current.get("wind_speed_10m", "N/A")
        weather_code = current.get("weather_code", 0)

        # 天氣代碼轉說明
        weather_desc = get_weather_description(weather_code)

        return (
            f"氣溫：{temp}°C\n"
            f"濕度：{humidity}%\n"
            f"風速：{wind_speed} km/h\n"
            f"天氣狀況：{weather_desc}"
        )
    except Exception:
        return None


def get_weather_description(code: int) -> str:
    """將 Open-Meteo 天氣代碼轉為中文說明"""
    if code == 0:
        return "☀️ 晴天"
    elif code in [1, 2, 3]:
        return "⛅ 多雲"
    elif code in [45, 48]:
        return "🌫️ 有霧"
    elif code in [51, 53, 55]:
        return "🌦️ 毛毛雨"
    elif code in [61, 63, 65]:
        return "🌧️ 下雨"
    elif code in [71, 73, 75]:
        return "❄️ 下雪"
    elif code in [80, 81, 82]:
        return "🌧️ 陣雨"
    elif code in [95, 96, 99]:
        return "⛈️ 雷雨"
    else:
        return "🌤️ 天氣多變"


@app.get("/weather")
async def get_weather(city: str = "Taipei"):
    """查詢天氣資訊 API"""
    weather_info = await fetch_weather(city)
    if not weather_info:
        raise HTTPException(status_code=404, detail=f"找不到城市 {city} 的天氣資訊")
    return {"city": city, "weather": weather_info}


# ════════════════════════════════════════════════════════════
# 路由：使用者偏好（記憶機制）
# ════════════════════════════════════════════════════════════

@app.get("/preferences")
async def get_user_preferences():
    """取得使用者偏好設定"""
    return get_preferences()


@app.put("/preferences")
async def update_preferences(req: UpdatePreferencesRequest):
    """更新使用者偏好設定"""
    conn = get_db()
    updates = {}

    if req.language is not None:
        updates["language"] = req.language
    if req.response_style is not None:
        updates["response_style"] = req.response_style
    if req.username is not None:
        updates["username"] = req.username

    timestamp = now()
    for key, value in updates.items():
        conn.execute(
            "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), timestamp)
        )

    conn.commit()
    conn.close()

    return get_preferences()


# ════════════════════════════════════════════════════════════
# LINE Bot：輔助函式
# ════════════════════════════════════════════════════════════

def generate_stock_reply(user_text: str) -> str:
    """
    使用 Gemini 產生股票相關回覆。
    - 聚焦股票分析、投資趨勢、產業資訊
    - 若與股票無關，引導使用者輸入股票問題
    - 若 Gemini 發生錯誤，回傳友善錯誤訊息
    """
    stock_keywords = [
        "股票", "股價", "台積電", "大盤", "上市", "上櫃",
        "漲", "跌", "K線", "技術分析", "基本面", "ETF",
        "投資", "美股", "台股", "選股", "產業", "半導體",
        "AI", "晶片", "財報", "EPS", "本益比", "殖利率",
    ]
    is_stock_related = any(kw in user_text for kw in stock_keywords)

    if not is_stock_related:
        return (
            "我是股票分析助理，專門回答股票和投資相關問題 📈\n"
            "請輸入想分析的股票名稱或代號，例如：\n"
            "・請分析台積電\n"
            "・台灣50 ETF 最近走勢\n"
            "・半導體產業趨勢分析"
        )

    prompt = (
        "你是一個專業的股票資訊分析助理，請用繁體中文回覆。\n"
        "回覆風格：清楚、條列式、適合投資新手閱讀。\n"
        "\n"
        f"使用者問題：{user_text}\n"
        "\n"
        "請提供股票相關分析，可包含走勢說明、產業背景、注意事項等。\n"
        "⚠️ 最後必須附上：「本回覆僅供學習參考，不構成投資建議，請自行判斷風險。」"
    )

    try:
        response = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])]
        )
        return response.text
    except Exception as e:
        return (
            f"抱歉，目前 AI 分析服務暫時無法使用 😅\n"
            f"請稍後再試，或換個方式提問！\n"
            f"（錯誤：{type(e).__name__}）"
        )


def save_line_interaction(user_id: str, user_message: str, bot_reply: str) -> None:
    """將 LINE 互動紀錄寫入 SQLite 的 line_interactions 資料表"""
    conn = get_db()
    conn.execute(
        """
        INSERT INTO line_interactions (user_id, user_message, bot_reply, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, user_message, bot_reply, now())
    )
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
# LINE Bot：Webhook 路由（POST /callback）
# ════════════════════════════════════════════════════════════

@app.post("/callback")
async def line_callback(request: Request):
    """
    LINE Webhook 端點。
    1. 讀取 X-Line-Signature Header
    2. 用 LINE_CHANNEL_SECRET 驗證簽名
    3. 驗證失敗 → 400 Bad Request
    4. 驗證成功 → 交給 handler 分派 Event
    5. 成功回傳 HTTP 200 OK
    """
    signature = request.headers.get("X-Line-Signature", "")
    body_bytes = await request.body()
    body_text  = body_bytes.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid LINE signature")

    return PlainTextResponse("OK", status_code=200)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_line_message(event: MessageEvent) -> None:
    """
    處理 LINE 文字訊息 Event。
    - 取得 user_id 與使用者訊息
    - 呼叫 Gemini 產生股票分析回覆
    - 儲存互動紀錄到 SQLite
    - 用 replyToken 回覆使用者（replyToken 只能使用一次）
    """
    user_id      = event.source.user_id
    user_message = event.message.text
    reply_token  = event.reply_token

    # 產生股票回覆
    bot_reply = generate_stock_reply(user_message)

    # 儲存互動紀錄
    save_line_interaction(user_id, user_message, bot_reply)

    # 回覆使用者（replyToken 只能用一次）
    with ApiClient(line_configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=bot_reply)]
            )
        )


# ════════════════════════════════════════════════════════════
# 應用程式啟動
# ════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """應用程式啟動時初始化資料庫"""
    init_db()
    # 使用 sys.stdout 避免 Windows cp950 編碼問題
    import sys
    sys.stdout.buffer.write(b"[OK] DB initialized (sessions + messages + line_interactions)\n")
    sys.stdout.buffer.write(b"[OK] Gemini API Key: " + (b"SET" if GEMINI_API_KEY else b"NOT SET") + b"\n")
    sys.stdout.buffer.write(b"[OK] LINE Token:     " + (b"SET" if LINE_CHANNEL_ACCESS_TOKEN else b"NOT SET") + b"\n")
    sys.stdout.buffer.write(b"[OK] LINE Secret:    " + (b"SET" if LINE_CHANNEL_SECRET else b"NOT SET") + b"\n")
    sys.stdout.flush()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
