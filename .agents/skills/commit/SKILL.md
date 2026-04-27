# SKILL: /commit

## 觸發指令
`/commit`

## 目標
自動執行 git commit 並 push 到遠端倉庫。

## 角色設定
你是一位 DevOps 工程師，負責維護版本控制的最佳實踐。

## Git 使用者設定
- **使用者名稱**：Antigravity（Antigravity 預設值）
- **Email**：antigravity@example.com（Antigravity 預設值）

## 執行步驟

1. 設定 Git 使用者資訊：
```bash
git config user.name "Antigravity"
git config user.email "antigravity@example.com"
```

2. 查看目前變更：
```bash
git status
git diff --stat
```

3. 請使用者確認要 commit 的檔案，然後執行：
```bash
git add .
```

4. 根據變更內容自動產生 commit message（遵循 Conventional Commits 規範）：
```
<type>(<scope>): <description>

[optional body]
```

   type 類型：
   - `feat`: 新功能
   - `fix`: 修復 bug
   - `docs`: 文件變更
   - `style`: 程式碼格式
   - `refactor`: 重構
   - `test`: 測試相關
   - `chore`: 雜項

5. 執行 commit：
```bash
git commit -m "<自動產生的 commit message>"
```

6. Push 到遠端：
```bash
git push
```

## 輸出規範
- Commit message 使用英文
- 每次執行前顯示將要執行的指令，讓使用者確認
- Push 成功後顯示遠端 URL 供確認
