# 股票 LINE Bot (AI 股票分析助理)

> **作業名稱**：LINE Bot 結合 FastAPI 與 AI 應用
> **作業性質**：個人作業

---

## 1. 專案簡介

這是這週的作業，將原本的網頁 AI 聊天機器人擴充為可以在 LINE 上面互動的「股票 LINE Bot」。
使用者只要在 LINE 傳送股票相關的問題（例如：台積電最近走勢如何？），Bot 就會透過 Gemini API 產生分析報告並回覆。所有的互動紀錄都會存進 SQLite 資料庫裡。

---

## 2. 使用技術

*   **FastAPI**: 擔任後端伺服器，負責接收 LINE 的 Webhook 請求。
*   **LINE Bot SDK v3**: 處理 LINE 的訊息接收與回覆（這週規定一定要用 v3！）。
*   **Gemini API**: 負責當大腦，產生股票分析內容。
*   **SQLite**: 輕量級資料庫，用來把每一筆聊天紀錄存下來。
*   **ngrok**: 把本地端的 localhost:8000 變成外網可以連線的 HTTPS 網址，這樣 LINE 才能把訊息傳過來。

---

## 3. 專案結構

```text
your-repo/
├── .agents/
│   └── skills/
│       ├── prd/SKILL.md
│       ├── architecture/SKILL.md
│       ├── models/SKILL.md
│       ├── implement/SKILL.md
│       ├── test/SKILL.md
│       ├── commit/SKILL.md
│       └── linebot-dev/SKILL.md   ← 這週新增的：LINE Bot 開發指引 Skill
├── docs/
│   ├── PRD.md                     ← 已更新為股票 LINE Bot 規格
│   ├── ARCHITECTURE.md            ← 已更新 LINE Webhook 流程
│   └── MODELS.md                  ← 已更新 line_interactions 資料表與 Event 模型
├── screenshots/
│   └── chat.png                   ← LINE 實際對話截圖
├── templates/
│   └── index.html                 ← 原本的網頁版前端 (保留)
├── app.py                         ← 主程式（包含原有的網頁路由 + 新增的 POST /callback）
├── chat.db                        ← 執行後自動產生的資料庫
├── requirements.txt               ← 相依套件 (包含 line-bot-sdk>=3.0.0)
├── .env.example                   ← 環境變數範本 (可以 push)
└── README.md                      ← 本檔案
```

---

## 4. 安裝方式

1. 把專案 clone 下來。
2. 建立虛擬環境並啟動：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
3. 安裝需要的套件：
   ```bash
   pip install -r requirements.txt
   ```

---

## 5. .env 設定方式

1. 複製 `.env.example` 變成 `.env` 檔案：
   ```bash
   cp .env.example .env
   ```
2. 打開 `.env` 填寫以下三個金鑰：
   ```env
   # Google Gemini API
   GEMINI_API_KEY=你的_GEMINI_API_KEY

   # LINE Bot 設定
   LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_CHANNEL_ACCESS_TOKEN
   LINE_CHANNEL_SECRET=你的_LINE_CHANNEL_SECRET
   ```
   > 取得方式：登入 LINE Developers Console，在 Messaging API 頁籤可以拿到 Access Token，在 Basic settings 頁籤可以拿到 Channel Secret。

---

## 6. 啟動 FastAPI

打開一個終端機，啟動 FastAPI 伺服器：
```bash
uvicorn app:app --reload
```
（預設會跑在 `http://127.0.0.1:8000`）

---

## 7. 啟動 ngrok

打開**第二個**終端機，執行 ngrok：
```bash
ngrok http 8000
```
（這會產生一個 Forwarding 網址，像是 `https://xxxxx.ngrok-free.app`）

---

## 8. LINE Developers Console Webhook URL 設定

1. 登入 LINE Developers Console，進入你的 Messaging API Channel。
2. 找到 **Webhook URL** 欄位。
3. 填入你剛剛拿到的 ngrok 網址，後面加上 `/callback`。
   例如：`https://xxxxx.ngrok-free.app/callback`
4. 開啟 **Use webhook** 功能。
5. 按下 **Verify** 按鈕，如果顯示 Success 就代表連線成功！

---

## 9. 測試流程

1. 掃描 LINE Developers Console 裡的 QR Code，把你的 Bot 加為好友。
2. 在 LINE 傳送一則訊息給 Bot，例如：「請分析台積電」。
3. 等待幾秒鐘，Bot 應該會回傳 Gemini 產生的股票分析，並且最後會帶有一句免責聲明。
4. 可以用 DB Browser for SQLite 打開 `chat.db`，確認 `line_interactions` 資料表有沒有成功存下剛剛的對話。

---

## 10. 截圖說明

請在 `screenshots/chat.png` 放入你在 LINE 上面跟 Bot 實際對話的截圖（至少要有一輪完整的問答）。

---

## 11. 注意事項 (避坑指南)

*   **`.env` 千萬不要 commit**：裡面有真實的 API Key，推上 GitHub 會被盜用，一定要確認它在 `.gitignore` 裡面。
*   **`*.db` 檔不要 commit**：資料庫檔案不需要進版控，避免衝突。
*   **ngrok 重啟後要更新 Webhook URL**：因為免費版 ngrok 每次重開網址都會變，所以重開後記得去 LINE 後台改網址。
*   **Webhook URL 必須加 `/callback`**：網址不能只填 domain，一定要對到我們程式裡寫的 `@app.post("/callback")` 路由。
*   **Auto-reply messages 要關閉**：LINE 後台預設會開啟自動回應，沒關掉的話，你傳一句話 Bot 會回覆兩次（一次是自動回應，一次是你寫的程式）。

---

## 心得報告

**姓名**：楊永蘭
**學號**：D1245806

### Q1. 你在 `/linebot-dev` Skill 的「注意事項」寫了哪些規則？寫這些規則的原因是什麼？

> 我在注意事項寫了這些：一定要用 v3 SDK、Webhook URL 要記得加 `/callback`、ngrok 重啟網址會換、要關閉 LINE 後台的 Auto-reply、replyToken 只能用一次、金鑰絕對不能寫死在程式碼或 commit `.env`，還有如果沒回傳 200 OK LINE 會一直重試。
> 寫這些原因是因為 LINE Bot 開發有很多環境設定的「地雷」，如果 AI 只懂寫程式，沒顧慮到 LINE 的平台特性（像是 replyToken 會過期、Webhook 需要 HTTPS），就算 code 沒寫錯也會跑不起來。先把這些地雷寫成規則，可以大幅減少後面 debug 的痛苦。

### Q2. 你的 Skill 第一次執行後，AI 產出的程式直接能跑嗎？如果不能，你需要修改哪些地方？修改後有沒有更新 Skill？

> （請根據你實際的操作情況填寫。如果直接成功就寫直接成功；如果有修改就寫修改了哪裡，例如 import 寫錯、少回傳 200 等。）

### Q3. 你遇到什麼問題是 AI 沒辦法自己解決、需要你介入的？

> LINE 後台的設定（像是填寫 Webhook URL、關閉自動回應、按 Verify）還有啟動 ngrok 這些「不在程式碼範圍內」的操作，AI 沒辦法幫我點擊，必須我親自去設定。另外就是 ngrok 網址每次都會變，這也需要我手動把新網址複製貼上給 LINE。

### Q4. 如果你要把這個 LINE Bot 讓朋友使用，你還需要做什麼？

> 1. 不能只用本機的 ngrok 跑，要把程式部署到雲端伺服器（例如 Render、Heroku 或 Zeabur），這樣電腦關機 Bot 也能動，而且網址是固定的。
> 2. 要確認 Gemini API 的免費額度夠不夠朋友一起用。
> 3. 要把 LINE Bot 的 LINE Official Account Manager 後台設定弄好（例如設定好圖文選單、歡迎訊息），如果有需要也可以申請認證帳號。
