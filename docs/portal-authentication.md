# 管理平台登入與授權

本文件說明本專案管理平台目前採用的登入與授權基線。

## 目前做法

管理平台入口 `/portal` 目前採用：

- 應用程式內建的 Google OAuth 2.0 / OpenID Connect code flow
- Google 作為登入提供者
- Google Workspace 內部應用設定作為主要授權邊界
- Azure 與本機共用 `/portal/auth/google/...` 這組登入與登出路徑

原因是管理平台除了需要知道「使用者是誰」，還需要在同一層完成 session 建立，以及本機與正式環境一致的登入體驗。把 Google OAuth flow 收斂進應用程式本身後，本機與 Azure 只差設定值，不差路徑與驗證模式。

Google callback 成功後，應用程式會建立 HttpOnly session cookie，後續 `/portal/dashboard` 與其子頁都會重新驗證這個 cookie，並確認登入帳號仍具有可用的 email 資訊。

目前程式仍保留 `X-MS-CLIENT-PRINCIPAL` 的短期相容讀取邏輯，方便既有 Azure 環境過渡；但標準做法已改為設定 `PORTAL_GOOGLE_*`，讓 local 與 Azure 走同一套流程。

登入頁 `/portal` 目前在未登入、設定未完成與權限不足三種狀態下，都會保留 `返回首頁` 入口，避免使用者被鎖在管理平台頁面。

## 這次實際採用的設定流程

目前專案採用「Google Cloud 兩組 OAuth client + Azure CLI 設定 production app settings」的做法。

### 1. 建立 Google Cloud 專案與品牌

在 Google Cloud Console 建立專案後，先完成 Google Auth Platform 的品牌設定。

至少需設定：

- Project name：依實際專案命名
- Support email：依實際管理或支援信箱設定

### 2. 建立本機 OAuth client

建立 `Web application` 類型的 OAuth client，名稱可設為 `CertificatePortal Local`。

本機 client 目前固定使用 `localhost`：

- Authorized JavaScript Origins：`http://localhost:7075`
- Authorized Redirect URI：`http://localhost:7075/portal/auth/google/callback`

建立後請記下：

- Client ID
- Client Secret

### 3. 建立正式環境 OAuth client

正式環境另建第二組 `Web application` client，名稱可設為 `CertificatePortal Production`。

正式環境目前固定使用自訂網域 `cert.iplayground.io`：

- Authorized JavaScript Origins：`https://cert.iplayground.io`
- Authorized Redirect URI：`https://cert.iplayground.io/portal/auth/google/callback`

這組 production client 應與本機分開，不共用 `client secret`。

## Azure App Settings

Function App 目前使用下列 app settings 控制 portal 登入：

- `PORTAL_GOOGLE_CLIENT_ID`
  - Google OAuth client ID
- `PORTAL_GOOGLE_CLIENT_SECRET`
  - Google OAuth client secret
- `PORTAL_GOOGLE_REDIRECT_URI`
  - 目前建議明確設定，不留空
  - production 目前值：`https://cert.iplayground.io/portal/auth/google/callback`

若未設定 `PORTAL_GOOGLE_CLIENT_ID` 與 `PORTAL_GOOGLE_CLIENT_SECRET`，則無法啟用標準的 portal Google OAuth 流程。

上述設定已納入 `infra/bicep/main.bicep` 的參數定義，可在部署時由 Azure CLI 或其他 IaC 流程傳入。

production 環境目前不要在 Azure Portal 手動輸入這些值，應改用 CLI：

```bash
az functionapp config appsettings set \
  --resource-group iplayground \
  --name ipg-certificate \
  --settings \
    PORTAL_GOOGLE_CLIENT_ID=<production-google-client-id> \
    PORTAL_GOOGLE_CLIENT_SECRET=<production-google-client-secret> \
    PORTAL_GOOGLE_REDIRECT_URI=https://cert.iplayground.io/portal/auth/google/callback
```

設定完成後，可用下列指令驗證非機密值：

```bash
az functionapp config appsettings list \
  --resource-group iplayground \
  --name ipg-certificate \
  --query "[?starts_with(name, 'PORTAL_') && name!='PORTAL_GOOGLE_CLIENT_SECRET'].{name:name,value:value}" \
  -o table
```

## 本機開發

本機直接執行 Azure Functions Core Tools 時，請設定與 Azure 相同命名的 app settings：

- `PORTAL_GOOGLE_CLIENT_ID=<local-google-client-id>`
- `PORTAL_GOOGLE_CLIENT_SECRET=<local-google-client-secret>`
- `PORTAL_GOOGLE_REDIRECT_URI=http://localhost:7075/portal/auth/google/callback`

設定後，`/portal` 會走與 Azure 一致的下列路徑：

- `/portal/auth/google/login`
- `/portal/auth/google/callback`
- `/portal/auth/logout`

Google callback 成功後，應用程式會在 localhost 建立與 Azure 相同格式的 HttpOnly session cookie，後續 `/portal/dashboard` 與其子頁會沿用這個 cookie 判斷登入狀態，並要求該帳號仍具有可用 email。

若缺少 `PORTAL_GOOGLE_CLIENT_ID` 或 `PORTAL_GOOGLE_CLIENT_SECRET`，localhost 的 `/portal` 會直接顯示設定未完成提示，不再退回 Azure `/.auth/...` 路徑。

若只想快速檢視 UI、不需要真的走 Google OAuth，仍可改用 bypass：

- `PORTAL_AUTH_BYPASS_ENABLED=true`
- `PORTAL_AUTH_BYPASS_DISPLAY_NAME=本機管理者`
- `PORTAL_AUTH_BYPASS_EMAIL=local-admin@iplayground.io`

只有 bypass 設定只限本機開發使用，不得部署到正式環境。

## Google Admin 補充

若 Google Workspace 有啟用 API controls，建立完 client 後，可能還需要到 Google Admin Console 把對應的 OAuth client 設成 trusted，否則成員帳號可能無法登入。

授權邊界目前主要依賴 Google OAuth client 本身的 `Internal` 設定；應用程式端不再額外維護其他授權 app setting。

## 目前行為

- 未登入使用者進入 `/portal` 時，會看到 Google SSO 登入入口與 `返回首頁`
- 若本機缺少 Google OAuth 設定，`/portal` 會顯示設定未完成提示、停用中的登入按鈕與 `返回首頁`
- 已登入但缺少可用 email claim 的使用者，會看到權限不足畫面、切換帳號按鈕與 `返回首頁`
- 已登入且具有可用 email 的使用者，會直接被導向 `/portal/dashboard`
- `/portal/dashboard` 及其子頁都會在伺服器端再次檢查 session cookie 與 email claim，不依賴前端狀態
