# ADR 0003: 管理平台登入採用 Google Workspace Internal SSO

- 狀態：Accepted
- 日期：2026-04-23

## 背景

管理平台 `/portal` 需要採用與組織既有帳號體系一致的登入與授權基線，而實際組織成員使用的是 Google Workspace 帳號。

若登入提供者與實際帳號來源不一致：

- 會讓實際身分來源與登入入口脫節
- 需要維護與組織日常帳號體系分離的另一套管理者授權模型
- 容易造成使用者明明已完成登入，卻仍因為授權模型不一致而無法使用

同時，本專案仍希望保留：

- `/portal` 可匿名進入，由應用程式自行決定顯示登入入口或設定提示
- `/portal/dashboard` 與其子頁一律由伺服器端重新檢查授權
- 本機與 Azure 使用同一套登入路徑與 session 模型

## 決策

本專案決定：

1. 管理平台登入採用應用程式內建的 Google OAuth / OIDC code flow。
2. 管理平台授權主要依賴 Google OAuth client 本身的 `Internal` 設定，不再額外維護額外授權 app setting。
3. Google OAuth client 設定以 `PORTAL_GOOGLE_CLIENT_ID`、`PORTAL_GOOGLE_CLIENT_SECRET` 與可選的 `PORTAL_GOOGLE_REDIRECT_URI` 表示，local 與 Azure 共用同一組命名。
4. Google callback 成功後，由應用程式建立 HttpOnly session cookie；`/portal/dashboard` 與其子頁一律在伺服器端重新檢查這個 cookie，不信任前端狀態。
5. 若只需要檢視 UI，才使用 `PORTAL_AUTH_BYPASS_ENABLED` 做本機 bypass，不把假的帳號密碼表單留在產品路徑。

## 影響

正面影響：

- 登入提供者與實際組織帳號來源一致
- 本機與 Azure 使用相同的登入路徑、callback 與 session 模型
- 授權模型收斂成 Google Workspace 內部應用邊界，少一個需要同步維護的 app setting
- 管理平台登入入口與 dashboard 都可維持單一 Azure Functions 應用程式內處理

代價與限制：

- 正式環境仍需設定 Google OAuth client 與對應 app settings
- 應用程式需要自行維護 OAuth callback、session cookie 與基本錯誤處理
- 授權正確性更依賴 Google OAuth client 的 `Internal` 設定與 Workspace 管理端配置
- Google callback 成功與否仍取決於 Google 回傳的有效登入資訊

## 後續

- 若未來需要更細的管理者權限分級，可再評估 Google 群組、外部授權服務，或其他可與 Google Workspace 對齊的模型
- 若未來需要完全移除過渡期相容邏輯，可再移除對 Azure `X-MS-CLIENT-PRINCIPAL` 的 fallback 讀取
