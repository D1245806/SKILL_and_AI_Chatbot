# 系統架構文件

**專案名稱**：AI 聊天機器人 + 股票 LINE Bot
**版本**：v2.0.0（新增 LINE Bot 擴充）
**最後更新**：2026-05-05

---

## 1. 系統架構說明

本專案分為兩個部分：

- **原有功能**：網頁版 AI 聊天機器人（FastAPI + Gemini + SQLite + HTML 前端）
- **本週新增**：股票 LINE Bot（LINE Messaging API v3 + Webhook + ngrok）

兩個功能共用同一份 `app.py`，跑在同一個 FastAPI 伺服器上。網頁聊天走 `/` 路由，LINE Bot 走 `/callback` 路由。

```
┌──────────────────────────────────────────────────┐
│                 FastAPI (app.py)                 │
│                                                  │
│  GET  /           → 網頁聊天前端 (HTML)           │
│  POST /sessions   → 聊天室管理                   │
│  POST /callback   → LINE Bot Webhook ← 本週新增  │
└──────────────────────────────────────────────────┘
         │                        │
    SQLite (chat.db)         Gemini API
    ├── sessions              股票分析回覆
    ├── messages
    └── line_interactions ← 本週新增
```

---

## 2. LINE Bot 訊息流程

### 完整流程

```
使用者在 LINE 傳訊息
        │
        ▼
LINE Platform
（LINE 官方伺服器，負責轉發 Webhook）
        │  POST https://<ngrok-domain>/callback
        │  Header: X-Line-Signature: <簽名>
        ▼
ngrok（HTTPS → localhost 轉發）
        │  轉發到 http://localhost:8000/callback
        ▼
FastAPI POST /callback
  1. 讀取 X-Line-Signature Header
  2. 用 LINE_CHANNEL_SECRET 驗證簽名
  3. 驗證失敗 → 回傳 400 Bad Request
  4. 驗證成功 → 解析 Event
  5. 取得 userId 和文字訊息（TextMessageContent）
        │
        ▼
Gemini API
  - 傳入：使用者訊息（股票 Prompt）
  - 傳出：股票分析回覆文字
        │
        ▼
SQLite (chat.db → line_interactions)
  - 寫入：user_id / user_message / bot_reply / created_at
        │
        ▼
LINE Reply API
  - 用 replyToken 回傳分析結果給使用者
  - replyToken 只能用一次
        │
        ▼
回傳 HTTP 200 OK 給 LINE Platform
        │
        ▼
使用者在 LINE 收到 Bot 回覆
```

### 步驟說明

| 步驟 | 負責方 | 說明 |
|---|---|---|
| 使用者傳訊息 | LINE App | 使用者在 LINE 輸入股票問題並傳送 |
| 轉發 Webhook | LINE Platform | 把 Event 以 POST 送到我們設定的 Webhook URL |
| HTTPS Tunnel | ngrok | 把 HTTPS 請求轉到本地 localhost:8000 |
| 驗證簽名 | FastAPI | 用 `LINE_CHANNEL_SECRET` 驗證 `X-Line-Signature` |
| 解析訊息 | FastAPI | 取出 `userId`、訊息文字、`replyToken` |
| 產生回覆 | Gemini API | 根據股票 Prompt 生成繁體中文分析 |
| 儲存紀錄 | SQLite | 寫入 `line_interactions` 資料表 |
| 回覆使用者 | LINE Reply API | 呼叫 `reply_message()`，使用 `replyToken` |
| 回傳 200 | FastAPI | 通知 LINE Platform Webhook 處理成功 |

---

## 3. 主要檔案說明

```
SKILL_and_AI_Chatbot/
│
├── app.py                          主程式（FastAPI 伺服器）
│   ├── GET  /                      網頁聊天前端入口
│   ├── POST /sessions              聊天室建立
│   ├── POST /sessions/{id}/messages 發送訊息（網頁版）
│   └── POST /callback              LINE Bot Webhook（本週新增）
│
├── requirements.txt                相依套件清單
│   ├── fastapi
│   ├── uvicorn[standard]
│   ├── line-bot-sdk>=3.0.0        ← 本週新增（必須 v3）
│   ├── google-generativeai
│   └── python-dotenv
│
├── .env.example                    環境變數範本（可 commit）
│   ├── LINE_CHANNEL_ACCESS_TOKEN=  ← 本週新增
│   ├── LINE_CHANNEL_SECRET=        ← 本週新增
│   └── GEMINI_API_KEY=
│
├── .env                            實際金鑰（不可 commit，已加入 .gitignore）
│
├── chat.db                         SQLite 資料庫（自動建立）
│   ├── sessions                    原有：網頁聊天室
│   ├── messages                    原有：聊天訊息
│   └── line_interactions           本週新增：LINE 互動紀錄
│
├── templates/
│   └── index.html                  網頁聊天前端 HTML
│
├── .agents/skills/
│   ├── prd/SKILL.md
│   ├── architecture/SKILL.md
│   ├── models/SKILL.md
│   ├── implement/SKILL.md
│   ├── test/SKILL.md
│   ├── commit/SKILL.md
│   └── linebot-dev/SKILL.md        ← 本週新增：LINE Bot 開發指引
│
└── README.md                       專案說明 + 啟動方式 + 心得報告
```

---

## 4. 資料庫設計

### 4.1 原有資料表（網頁聊天功能保留）

**sessions（聊天室）**

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | TEXT PK | UUID 格式 |
| `title` | TEXT | 聊天室標題 |
| `created_at` | TEXT | 建立時間 |
| `updated_at` | TEXT | 最後更新時間 |

**messages（訊息）**

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | TEXT PK | UUID 格式 |
| `session_id` | TEXT FK | 關聯的聊天室 |
| `role` | TEXT | `user` 或 `assistant` |
| `content` | TEXT | 訊息內容 |
| `timestamp` | TEXT | 訊息時間 |

### 4.2 本週新增資料表（LINE Bot 互動紀錄）

**line_interactions**

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | 自動遞增，不需手動填 |
| `user_id` | TEXT NOT NULL | LINE 使用者 UID（`U` 開頭的 33 位字串） |
| `user_message` | TEXT NOT NULL | 使用者傳送的訊息內容 |
| `bot_reply` | TEXT NOT NULL | Gemini 產生的 Bot 回覆 |
| `created_at` | DATETIME DEFAULT CURRENT_TIMESTAMP | 互動時間，自動填入 |

**建立 SQL**：

```sql
CREATE TABLE IF NOT EXISTS line_interactions (
    id           INTEGER  PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT     NOT NULL,
    user_message TEXT     NOT NULL,
    bot_reply    TEXT     NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 環境變數設計

`.env` 檔案（不能 commit，放在 `.gitignore`）：

```env
# LINE Bot 設定（本週新增）
LINE_CHANNEL_ACCESS_TOKEN=你的_Channel_Access_Token
LINE_CHANNEL_SECRET=你的_Channel_Secret

# Gemini AI（原有）
GEMINI_API_KEY=你的_Gemini_API_Key
```

`.env.example`（可以 commit 的空白範本）：

```env
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
GEMINI_API_KEY=
```

| 變數 | 從哪裡取得 | 用途 |
|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers Console → Messaging API → Channel access token | 呼叫 LINE Reply API |
| `LINE_CHANNEL_SECRET` | LINE Developers Console → Basic settings → Channel secret | 驗證 Webhook 簽名 |
| `GEMINI_API_KEY` | Google AI Studio | 呼叫 Gemini API |

---

## 6. 本機測試架構

本機開發時需要同時開兩個終端機：

```
終端機 1：啟動 FastAPI 伺服器
─────────────────────────────
$ uvicorn app:app --reload --port 8000
INFO: Uvicorn running on http://127.0.0.1:8000

終端機 2：啟動 ngrok Tunnel
─────────────────────────────
$ ngrok http 8000
Forwarding  https://xxxx-xxx-xxx.ngrok-free.app -> http://localhost:8000
```

測試流程：

1. 確認 FastAPI 正常啟動（無 import 錯誤）
2. 確認 ngrok 拿到 HTTPS URL
3. 把 `https://xxxx.ngrok-free.app/callback` 填入 LINE 後台
4. 點 **Verify**，確認收到 200（表示 Webhook 驗證通過）
5. 用 LINE 傳訊息測試 Bot 回覆
6. 查看 SQLite 確認紀錄有寫入

---

## 7. ngrok 與 LINE Webhook 設定

### ngrok 安裝與啟動

```bash
# 安裝（Windows，用 Chocolatey 或直接下載 exe）
# https://ngrok.com/download

# 啟動
ngrok http 8000
```

### LINE Developers Console 設定步驟

1. 登入 [LINE Developers Console](https://developers.line.biz/)
2. 選擇你的 Provider → 選擇 Messaging API Channel
3. 進入 **Messaging API** 分頁
4. 找到 **Webhook settings**：
   - **Webhook URL**：填入 `https://<ngrok-domain>/callback`
   - 打開 **Use webhook** 開關
5. 點擊 **Verify** → 應該顯示 **Success**
6. 回到 **Basic settings** 分頁：
   - 複製 **Channel secret** → 填入 `.env` 的 `LINE_CHANNEL_SECRET`
7. 回到 **Messaging API** 分頁：
   - 點 **Issue** 產生 **Channel access token (long-lived)**
   - 複製後填入 `.env` 的 `LINE_CHANNEL_ACCESS_TOKEN`
8. 關閉 **Auto-reply messages**（否則 Bot 會回兩次）

### 常見問題

| 問題 | 原因 | 解法 |
|---|---|---|
| Verify 失敗 | URL 沒加 `/callback` | 確認填的是 `.../callback` |
| Verify 失敗 | FastAPI 沒在跑 | 先啟動 uvicorn |
| Bot 沒有回覆 | ngrok 重啟後網址變了 | 更新 LINE 後台的 Webhook URL |
| Bot 回覆兩次 | Auto-reply 沒關 | 在 LINE 後台關閉 Auto-reply messages |
| 500 錯誤 | `.env` 金鑰錯誤或沒讀到 | 確認 `.env` 存在且格式正確 |
