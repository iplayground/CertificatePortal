# ADR 0003: 管理平台登入與授權採用 Google Workspace Internal SSO + Google Group

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

Google OAuth client 的 `Internal` 設定仍是必要的第一層邊界，用來排除非本組織的 Google 帳號。它能確認登入者屬於組織帳號範圍，但不足以表達「哪些組織內成員可以使用本專案管理平台」這種較細的授權邊界。

若直接把授權綁在 Google Admin custom role：

- 權限語意會與 Google Admin console 的實際管理權限耦合
- 角色一旦指派，使用者就真的取得對應的 Workspace 管理能力
- 不適合只想表達本專案 portal 存取資格的需求

因此，本專案需要採用雙層邊界：先由 Google Workspace Internal SSO 排除非組織帳號，再由 Google Group 表達本專案管理平台的存取資格。

## 決策

本專案決定：

1. 管理平台登入採用應用程式內建的 Google OAuth / OIDC code flow，且 OAuth client 必須設定為 Google Workspace `Internal`。
2. `Internal` 是第一層組織邊界，用來排除非本組織帳號；Google Group 是第二層管理平台存取邊界，用來決定哪些組織內帳號可進入 `/portal/dashboard`。
3. Google OAuth client 設定以 `PORTAL_GOOGLE_CLIENT_ID`、`PORTAL_GOOGLE_CLIENT_SECRET` 與可選的 `PORTAL_GOOGLE_REDIRECT_URI` 表示，local 與 Azure 共用同一組命名。
4. Google OAuth callback 成功後，應用程式必須使用登入者自己的 Google access token 呼叫 Cloud Identity Groups API，逐一確認登入者是否為允許群組的直接成員。
5. 只有通過群組驗證的帳號，才建立 HttpOnly session cookie；`/portal/dashboard` 與其子頁一律在伺服器端重新檢查這個 cookie，不信任前端狀態。
6. 群組授權只檢查 direct membership，不處理巢狀群組，也不先列出使用者所有群組。
7. 目標群組必須允許組織內使用者查看群組與成員資訊，且 OAuth client 所屬 Google Cloud project 必須啟用 Cloud Identity API。
8. 若只需要檢視 UI，才使用 `PORTAL_AUTH_BYPASS_ENABLED` 做本機 bypass，不把假的帳號密碼表單留在產品路徑。

## 影響

正面影響：

- 登入提供者與實際組織帳號來源一致
- `Internal` 會先排除非組織帳號，避免外部 Google 帳號進入後續 portal 授權流程
- 授權語意可直接對應「哪些人能進 portal」
- 變更管理者名單時，只需調整 Google Group 成員
- 不必把本專案的 portal 存取權限綁成 Google Admin 實際管理權
- 本機與 Azure 仍可共用相同的登入路徑、callback 與 session 模型
- 管理平台登入入口與 dashboard 都可維持單一 Azure Functions 應用程式內處理

代價與限制：

- 正式環境除了 OAuth client 外，仍需另外準備 Google Group 與 Cloud Identity Groups API 設定
- 應用程式需要自行維護 OAuth callback、session cookie 與基本錯誤處理
- callback 需要額外呼叫 Cloud Identity Groups API，增加外部依賴與失敗面；若 API 未在 OAuth client 所屬 project 啟用，授權檢查會失敗
- 授權正確性同時依賴 Google OAuth client 的 `Internal` 設定、Google Admin 群組設定與 Google Cloud API 設定
- 因目前只檢查直接成員，若未來要支援巢狀群組，需要重新評估 API 方法、可見度與授權錯誤處理
- session 建立後，群組成員變更不會立刻回溯撤銷既有 cookie

## 後續

- 若未來需要更細的 app 內權限分級，可在 Google Group 之上再增加本專案自己的 role mapping
