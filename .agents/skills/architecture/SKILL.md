# SKILL: /architecture

## 觸發指令
`/architecture`

## 目標
產出 `docs/ARCHITECTURE.md`，定義 AI 聊天機器人的系統架構文件。

## 角色設定
你是一位資深軟體架構師（Software Architect），擅長設計可擴展、高效能的系統架構。

## 執行步驟

1. 讀取 `docs/PRD.md`（如果存在）
2. 產出以下結構的 `docs/ARCHITECTURE.md`：

```markdown
# 系統架構文件

## 1. 架構概覽
   - 架構圖（使用 ASCII art 或 Mermaid）
## 2. 技術選型
   - 前端：HTML + CSS + JavaScript
   - 後端：FastAPI (Python)
   - 資料庫：SQLite
   - AI：Google Gemini API
## 3. 系統元件說明
   - 各元件職責與介面
## 4. 資料流程圖
## 5. API 端點設計
## 6. 資料庫 Schema
## 7. 部署架構
```

3. 將文件寫入 `docs/ARCHITECTURE.md`

## 輸出規範
- 架構圖使用 Mermaid 格式
- API 設計遵循 RESTful 規範
- 資料庫 Schema 使用 SQL 語法表示
