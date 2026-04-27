# SKILL: /models

## 觸發指令
`/models`

## 目標
產出 `docs/MODELS.md`，定義 AI 聊天機器人的資料模型文件。

## 角色設定
你是一位資深後端工程師，擅長設計清晰的資料模型與資料庫 Schema。

## 執行步驟

1. 讀取 `docs/ARCHITECTURE.md`（如果存在）
2. 產出以下結構的 `docs/MODELS.md`：

```markdown
# 資料模型文件

## 1. 資料庫模型

### Sessions（聊天室）
| 欄位 | 類型 | 說明 |
| ---- | ---- | ---- |

### Messages（訊息）
| 欄位 | 類型 | 說明 |
| ---- | ---- | ---- |

### UserPreferences（使用者偏好）
| 欄位 | 類型 | 說明 |
| ---- | ---- | ---- |

## 2. Pydantic 模型（API Schema）

### Request Models
### Response Models

## 3. 模型關聯圖
```

3. 將文件寫入 `docs/MODELS.md`

## 輸出規範
- 每個欄位需標示是否為主鍵、外鍵、是否可為 NULL
- Pydantic 模型需附帶型別標注與範例值
- 關聯圖使用 Mermaid ER Diagram 格式
