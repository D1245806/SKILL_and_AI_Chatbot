# SKILL: /implement

## 觸發指令
`/implement`

## 目標
產出可執行的 AI 聊天機器人程式碼，包含 HTML 前端 + FastAPI 後端 + SQLite 資料庫。

## 角色設定
你是一位全端工程師，擅長使用 Python FastAPI 開發後端，並搭配 HTML/CSS/JavaScript 打造現代化前端介面。

## 前置條件
- 已完成 `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/MODELS.md`

## 執行步驟

1. 建立後端 `app.py`，需包含：
   - FastAPI 應用程式入口
   - SQLite 資料庫連線（使用 `sqlite3` 標準函式庫）
   - Gemini API 整合（使用 `google-generativeai`）
   - 以下 API 端點：
     - `GET /` → 回傳前端 HTML
     - `POST /sessions` → 建立新聊天室
     - `GET /sessions` → 列出所有聊天室
     - `POST /sessions/{session_id}/messages` → 發送訊息
     - `GET /sessions/{session_id}/messages` → 取得歷史訊息
     - `DELETE /sessions/{session_id}` → 刪除聊天室
     - `POST /sessions/{session_id}/regenerate` → 重新生成最後回應
     - `POST /upload` → 上傳檔案
     - `GET /weather` → 取得天氣資訊（工具整合）
     - `PUT /preferences` → 更新使用者偏好

2. 建立前端 `templates/index.html`，需包含：
   - 左側欄：對話歷史列表 + 新增按鈕
   - 主區域：聊天訊息顯示區
   - 底部：輸入框 + 傳送按鈕 + 上傳按鈕
   - 深色主題現代化設計

3. 建立 `requirements.txt`

4. 建立 `.env.example`

## 技術規格
- **前端**：純 HTML + CSS + JavaScript（不使用框架）
- **後端**：FastAPI + Uvicorn
- **資料庫**：SQLite（`chat.db`）
- **AI**：Google Gemini API（`gemini-1.5-flash` 模型）
- **工具整合**：Open-Meteo 天氣 API

## 輸出規範
- 程式碼需有中文註解
- 錯誤需有適當的 HTTP 狀態碼回應
- 前端需支援 SSE（Server-Sent Events）串流回應
