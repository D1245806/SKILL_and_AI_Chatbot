# Product Requirements Document (PRD)

**專案名稱**：股票 LINE Bot — AI 股票分析助理
**版本**：v2.0.0
**技術棧**：FastAPI + LINE Bot SDK v3 + Google Gemini API + SQLite + ngrok
**撰寫日期**：2026-05-05

---

## 1. 專案背景

這週的作業是把上週做的 FastAPI + Gemini + SQLite 網頁聊天機器人，擴充成一個可以在 LINE 上使用的股票分析 Bot。

上週的基礎架構（FastAPI 後端、Gemini AI 回覆、SQLite 資料庫）都可以繼續保留，這週主要是加上 LINE Messaging API 的 Webhook 整合，讓使用者可以直接在 LINE 上傳訊息問股票相關問題，然後 Bot 用 Gemini 產生分析回覆。

這個專案的核心概念很簡單：**使用者用 LINE 傳問題 → Bot 用 AI 回覆 → 紀錄存進資料庫**。

---

## 2. 專案目標

- 讓使用者可以在 LINE 上傳送股票相關問題，並且得到 AI 產生的分析回覆
- 把原本的 FastAPI 後端擴充成支援 LINE Webhook 的伺服器
- 繼續使用 Gemini API 產生股票相關的繁體中文回覆
- 用 SQLite 記錄每一次 LINE 使用者的互動紀錄（誰問了什麼、Bot 回了什麼）
- 透過 ngrok 把本地伺服器公開，讓 LINE 平台可以呼叫 Webhook

---

## 3. 使用者情境

### 情境一：問股票走勢

> 使用者：「台積電最近走勢怎麼樣？」
>
> Bot：「台積電（2330）近期受到 AI 晶片需求帶動，整體走勢偏多頭…（AI 分析）」

### 情境二：詢問投資建議

> 使用者：「我手上有 50 萬，適合買哪檔股票？」
>
> Bot：「我可以提供一些分析方向，但最終投資決策還是要你自己判斷。以下幾點可以參考…」

### 情境三：查詢產業資訊

> 使用者：「半導體產業最近有什麼趨勢？」
>
> Bot：「根據近期報告，半導體產業受到…（Gemini 分析回覆）」

### 情境四：非股票問題

> 使用者：「今天天氣怎樣？」
>
> Bot：「我主要負責股票相關問題，如果你有股票方面的疑問歡迎問我！」

---

## 4. 核心功能

### F-01：使用者在 LINE 傳股票相關問題

- 使用者加 Bot 為 LINE 好友後，可以直接傳送文字訊息
- 主題以股票、投資、產業分析為主
- 非股票問題也接受，但 Bot 會引導回股票話題

### F-02：FastAPI 接收 LINE Webhook

- 使用 FastAPI 建立 `POST /callback` 路由作為 Webhook 端點
- 每次收到請求時，必須驗證 `X-Line-Signature` Header，確保請求來自 LINE 平台
- 驗證成功後解析 Event，失敗回傳 400
- 成功處理後回傳 HTTP 200 OK

### F-03：Gemini 產生股票分析回覆

- 使用 Gemini API（`gemini-2.0-flash` 或以上）根據使用者訊息產生回覆
- Prompt 設計成股票分析助理角色，回覆以繁體中文為主
- 若使用者問的與股票無關，禮貌引導回股票話題

### F-04：SQLite 記錄互動紀錄

每次 Bot 成功回覆後，把以下資料寫進 SQLite 資料庫：

| 欄位 | 說明 |
|---|---|
| `user_id` | LINE 使用者的 UID |
| `user_message` | 使用者傳送的訊息 |
| `bot_reply` | Bot 回覆的內容 |
| `created_at` | 互動的時間戳記 |

---

## 5. 不做的功能（Out of Scope）

- ❌ **不做真正下單**：這個 Bot 只提供 AI 分析，不會串接任何券商 API 執行下單
- ❌ **不提供投資保證**：所有回覆都是 AI 生成的參考資訊，不保證獲利，Bot 回覆時需附上免責說明
- ❌ **不要求即時股價查詢**：這次不串接即時股價 API（如 Yahoo Finance），回覆內容以 Gemini 的知識庫為主
- ❌ 不做使用者帳號系統（LINE 的 user_id 就夠用了）
- ❌ 不做網頁前端（這次重點是 LINE Bot，不是瀏覽器介面）
- ❌ 不支援圖片、語音等非文字訊息（這次只處理 TextMessage）

---

## 6. 技術需求

| 套件 / 工具 | 用途 | 備註 |
|---|---|---|
| **FastAPI** | 建立 Webhook 路由 `POST /callback` | 繼續沿用上週的框架 |
| **LINE Bot SDK v3** | 驗證 Signature、解析 Event、呼叫 Reply API | 必須用 v3，不能用舊版 v2 寫法 |
| **Gemini API** | 產生股票分析回覆 | 使用 `google-generativeai` 套件 |
| **SQLite** | 記錄互動紀錄 | 使用內建 `sqlite3` 模組，不需額外安裝 |
| **ngrok** | 把本地 8000 port 公開為 HTTPS URL | LINE 平台要求 Webhook 必須是 HTTPS |
| **python-dotenv** | 讀取 `.env` 環境變數 | 金鑰不能寫死在程式碼裡 |

---

## 7. 環境變數需求

`.env` 檔案必須包含以下三個變數（不能少，也不能寫死在程式碼裡）：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的_Channel_Access_Token
LINE_CHANNEL_SECRET=你的_Channel_Secret
GEMINI_API_KEY=你的_Gemini_API_Key
```

> ⚠️ `.env` 必須加入 `.gitignore`，絕對不能 commit 到 GitHub。
> 可以 commit 的是 `.env.example`（空值版本）。

---

## 8. 驗收標準

完成後，以下每一項都要可以正常運作才算完成：

- [ ] 執行 `uvicorn app:app --reload` 後伺服器可以正常啟動，沒有 import 錯誤
- [ ] 執行 `ngrok http 8000` 後可以取得公開的 HTTPS 網址
- [ ] 把 `https://<ngrok-domain>/callback` 填入 LINE Developers Console 的 Webhook URL 欄位後，按下 **Verify** 可以成功（顯示 Success）
- [ ] 用自己的 LINE 帳號傳訊息給 Bot，Bot 可以在幾秒內回覆股票相關分析
- [ ] 查看 SQLite 資料庫（`chat.db`），可以看到剛才的互動紀錄（user_id、user_message、bot_reply、created_at 都有值）
- [ ] `.env` 沒有被 commit 到 GitHub（確認 `.gitignore` 有包含 `.env`）
