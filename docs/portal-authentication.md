# 管理平台登入與授權

本文件說明本專案管理平台 `/portal` 目前採用的登入與授權基線。

## 目前做法

管理平台目前採用兩層判斷：

- 應用程式內建的 Google OAuth 2.0 / OpenID Connect code flow
- Google Group 作為實際的管理平台授權邊界

也就是說：

- Google OAuth client 的 `Internal` 設定先確認「這個人是否屬於本組織」
- Google Group 只負責確認「這個人是否屬於允許操作管理平台的群組」

Google callback 成功後，應用程式會用登入者自己的 Google access token 呼叫 Cloud Identity Groups API，逐一檢查登入者是否為 `PORTAL_GOOGLE_ALLOWED_GROUP_KEYS` 指定群組的直接成員。只有通過群組驗證的帳號，才會建立 HttpOnly session cookie；後續 `/portal/dashboard` 與其子頁都會重新驗證這個 cookie。

目前只檢查直接成員，不處理巢狀群組。系統也不會先列出使用者所有群組，而是只查設定中的允許群組，降低不必要的 API 查詢與資料暴露。

Google OAuth client 必須維持 `Internal` 設定，作為排除非組織帳號的第一道邊界；Google Group 則作為組織內成員能否進入管理平台的第二道邊界。

若 Google OAuth callback 發生 `access_denied`、群組未授權，或其他登入失敗，應用程式會以一次性 flash cookie 將錯誤狀態帶回 `/portal`，再由登入頁顯示 alert；錯誤訊號不透過 URL query 傳遞。

## 設定流程

管理平台登入與授權採用下列組合：

- Google OAuth client
- 1 個或多個允許登入管理平台的 Google Group
- 在 OAuth client 所屬的 Google Cloud project 啟用 Cloud Identity API
- 調整目標群組的可見度，讓組織內使用者可查看群組與成員
- Azure CLI 或 Key Vault reference 寫入 production app settings

### 1. 建立 Google Cloud 專案與品牌

在 Google Cloud Console 建立專案後，先完成 Google Auth Platform 的品牌設定。

至少需設定：

- Project name：依實際專案命名
- Support email：依實際管理或支援信箱設定

### 2. 建立 Google OAuth client

建立 `Web application` 類型的 OAuth client，並設定為 Google Workspace `Internal`。

正式環境目前固定使用自訂網域 `cert.iplayground.io`：

- Authorized JavaScript Origins：`https://cert.iplayground.io`
- Authorized Redirect URI：`https://cert.iplayground.io/portal/auth/google/callback`

這組 Google OAuth client 是正式環境登入基線。

### 3. 建立允許登入管理平台的 Google Group

建立 1 個或多個專用群組，並將它們作為 portal allowlist 使用。

此群組應只用來表達「可進入本專案管理平台」這個授權語意，不要混用為一般郵件群組或其他系統權限群組。

### 4. 啟用 Cloud Identity API

在 OAuth client 所屬的 Google Cloud project 啟用 Cloud Identity API，供 callback 用登入者自己的 token 查詢 direct membership。

本專案 callback 目前會要求：

- `https://www.googleapis.com/auth/cloud-identity.groups.readonly`

如果登入時後端日誌出現 `SERVICE_DISABLED`，通常代表 Cloud Identity API 尚未在 OAuth client 所屬專案啟用，或啟用到了錯誤的 Google Cloud project。

1. 進入 Google Cloud Console。
2. 在專案選擇器切到 OAuth client 所屬的 project。
3. 若不確定是哪個 project，請到 `APIs & Services` -> `Credentials`，找到本專案使用的 OAuth client，確認它所在的 project。
4. 進入 `APIs & Services` -> `Library`。
5. 搜尋 `Cloud Identity API`。
6. 開啟該 API 頁面後按 `Enable`。
7. 回到 `APIs & Services` -> `Enabled APIs & services`，確認 `Cloud Identity API` 已列在啟用清單中。

### 5. 調整群組可見度

若你要讓一般登入者用自己的 token 檢查自己是否在群組內，目標群組必須允許組織內使用者查看群組與成員。

建議至少確認：

- 群組本身對組織內使用者可見
- 群組成員名單對組織內使用者可見

若這兩者其中之一不允許，callback 可能會在群組授權檢查階段收到 `403`。

若所有允許群組都無法被查詢，登入頁會顯示「群組驗證未完成」；若 API 可查詢但登入者不是任一允許群組的直接成員，才會顯示「沒有文件管理平台權限」。

## Azure App Settings

Function App 目前使用下列 app settings 控制 portal 登入與授權：

- `PORTAL_GOOGLE_CLIENT_ID`
  - Google OAuth client ID
- `PORTAL_GOOGLE_CLIENT_SECRET`
  - Google OAuth client secret
- `PORTAL_GOOGLE_REDIRECT_URI`
  - 建議明確設定，不留空
  - production 目前值：`https://cert.iplayground.io/portal/auth/google/callback`
- `PORTAL_GOOGLE_ALLOWED_GROUP_KEYS`
  - 允許登入管理平台的 Google Group allowlist
  - 使用逗號分隔
  - 若值未包含 `@`，會自動補成目前登入使用者所在網域的完整群組地址
  - 若需要指定其他完整 key，也可直接填帶 `@` 的值

若未完整設定上述值，則無法啟用標準的 portal Google OAuth + Group 授權流程。

上述設定已納入 `infra/bicep/main.bicep` 的參數定義，可在部署時由 Azure CLI 或其他 IaC 流程傳入。

營業稅繳稅證明公開下載 ticket 使用獨立 app settings，不屬於 Google OAuth 設定：

- `TAX_RECEIPT_DOWNLOAD_TICKET_SECRET`
  - 公開下載 ticket 與下載主體 key 的 HMAC secret
  - 必須使用專用隨機 secret，不得使用 `PORTAL_GOOGLE_CLIENT_SECRET`
- `TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS`
  - 公開下載 ticket 有效秒數
  - 預設值為 `600`

production 環境目前不要在 Azure Portal 手動輸入這些值，應改用 CLI 或 Key Vault reference：

```bash
az functionapp config appsettings set \
  --resource-group iplayground \
  --name ipg-certificate \
  --settings \
    PORTAL_GOOGLE_CLIENT_ID=<google-client-id> \
    PORTAL_GOOGLE_CLIENT_SECRET=<google-client-secret> \
    PORTAL_GOOGLE_REDIRECT_URI=https://cert.iplayground.io/portal/auth/google/callback \
    PORTAL_GOOGLE_ALLOWED_GROUP_KEYS=<allowed-group-name-1>,<allowed-group-name-2>
```

下載 ticket secret 可另外設定或輪替：

```bash
TAX_RECEIPT_DOWNLOAD_TICKET_SECRET="$(openssl rand -hex 32)"

az functionapp config appsettings set \
  --resource-group iplayground \
  --name ipg-certificate \
  --settings \
    TAX_RECEIPT_DOWNLOAD_TICKET_SECRET="${TAX_RECEIPT_DOWNLOAD_TICKET_SECRET}" \
    TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS=600

unset TAX_RECEIPT_DOWNLOAD_TICKET_SECRET
```

設定完成後，可用下列指令驗證非機密值：

```bash
az functionapp config appsettings list \
  --resource-group iplayground \
  --name ipg-certificate \
  --query "[?starts_with(name, 'PORTAL_') && name!='PORTAL_GOOGLE_CLIENT_SECRET'].{name:name,value:value}" \
  -o table
```

確認下載 ticket app settings 是否存在時，不要輸出 secret value：

```bash
az functionapp config appsettings list \
  --resource-group iplayground \
  --name ipg-certificate \
  --query "[?name=='TAX_RECEIPT_DOWNLOAD_TICKET_SECRET' || name=='TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS'].name" \
  -o tsv
```

## 本機開發

本機開發預設可使用 bypass 檢視 UI，不需要建立或維護長期使用的本機 OAuth client：

- `PORTAL_AUTH_BYPASS_ENABLED=true`
- `PORTAL_AUTH_BYPASS_DISPLAY_NAME=本機管理者`
- `PORTAL_AUTH_BYPASS_EMAIL=local-admin@iplayground.io`

若現階段需要在 localhost 端到端驗證 Google OAuth 與群組授權流程，才暫時填入與 Azure 相同命名的 app settings：

- `PORTAL_GOOGLE_CLIENT_ID=<local-google-client-id>`
- `PORTAL_GOOGLE_CLIENT_SECRET=<local-google-client-secret>`
- `PORTAL_GOOGLE_REDIRECT_URI=http://localhost:7075/portal/auth/google/callback`
- `PORTAL_GOOGLE_ALLOWED_GROUP_KEYS=<allowed-group-name-1>,<allowed-group-name-2>`
- `TAX_RECEIPT_DOWNLOAD_TICKET_SECRET=<local-tax-receipt-download-ticket-secret>`
- `TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS=600`

這組本機 OAuth 設定只用於現階段開發驗證；未來本機流程不應依賴它作為長期基線。

設定後，`/portal` 會走與 Azure 一致的下列路徑：

- `/portal/auth/google/login`
- `/portal/auth/google/callback`
- `/portal/auth/logout`

Google callback 成功後，應用程式會在 localhost 建立與 Azure 相同格式的 HttpOnly session cookie，後續 `/portal/dashboard` 與其子頁會沿用這個 cookie 判斷登入狀態。

若缺少 OAuth 或 Group 授權設定，localhost 的 `/portal` 會直接顯示設定未完成提示，不再提供登入入口。

只有 bypass 設定只限本機開發使用，不得部署到正式環境。

## Google Admin 補充

若 Google Workspace 有啟用 API controls，建立完 OAuth client 後，可能還需要到 Google Admin Console 確認對應 client 已被信任，且所需 scopes 已正確允許。

群組授權設計上也建議：

- 使用專用群組，不與其他產品授權語意混用
- 若群組成員有異動需求，應以修改群組成員作為主要操作，而不是修改程式設定
- 若日後不再需要 bare group key，仍建議直接填完整 group email，降低推導歧義

## 目前行為

- 未登入使用者進入 `/portal` 時，會看到 Google SSO 登入入口與 `返回首頁`
- 若使用者在 Google OAuth 畫面取消授權，會返回 `/portal`
- 若使用者未完成 Google 資料授權，會返回 `/portal` 並顯示資料授權未完成 alert
- 若群組驗證因 API 或可見度設定未完成而無法判斷，會返回 `/portal` 並顯示群組驗證未完成 alert
- 若 Cloud Identity API 可完成查詢，但登入帳號不在允許的 Google Group 直接成員內，會返回 `/portal` 並顯示未授權 alert
- portal 登入頁的登入錯誤 alert 目前不會自動關閉
- 若本機或 Azure 缺少 OAuth / Group 授權設定，`/portal` 會顯示設定未完成提示、停用中的登入按鈕與 `返回首頁`
- 已通過群組驗證的使用者，才會被導向 `/portal/dashboard`
- `/portal/dashboard` 及其子頁都會在伺服器端再次檢查 session cookie，不依賴前端狀態
- 若使用者停留在 `/portal/dashboard` 時 session cookie 過期或失效，iframe 子頁重新載入後若被伺服器導回 `/portal`，父層 dashboard 會同步把整個瀏覽器頁面導回 `/portal`
- 管理端前端呼叫 API 時，若收到 `401 unauthorized`，會將 top-level 視窗導回 `/portal`，避免只在 iframe 或局部畫面顯示登入失效錯誤
