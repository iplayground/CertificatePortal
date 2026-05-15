# Azure Functions GitHub 部署說明

本文件說明本專案目前採用的 Azure Functions Flex Consumption + GitHub Actions 部署流程。

## 流程總覽

1. `infra/bicep/main.bicep` 定義 Azure 資源應該長成什麼樣子。
2. Azure CLI 透過 `az deployment group create` 套用 `infra/` 內的 Bicep，實際建立或更新 Azure 資源。
3. 若要啟用 `/portal` 的 Google Workspace SSO + Google Group 授權，需另依 `docs/portal-authentication.md` 完成 Google OAuth client、Cloud Identity API、Google Group 授權設定與對應 app settings 設定。
4. Azure Portal 目前只保留給 GitHub 來源綁定流程使用。
5. `.github/workflows/deploy-function-app.yml` 假設上述資源已存在，並以 GitHub Actions OIDC + `Azure/functions-action@v1` 進行 remote build 與程式碼部署，不在每次 push 時重跑整份 Bicep。

## 相關檔案

- 基礎設施定義：`infra/bicep/main.bicep`
- 管理平台登入授權文件：`docs/portal-authentication.md`
- 程式碼部署 workflow：`.github/workflows/deploy-function-app.yml`

Resource Group、Region 與 Function App 名稱由 Bicep 參數或 GitHub Actions variables 提供。

`functionAppName` 必須保持 Azure 全域唯一，並會同時影響 Function App 名稱、預設公開網址，以及衍生出的 Storage Account、Application Insights、Log Analytics 與 GitHub 部署身分命名。

若未明確提供 `cosmosAccountName`，Bicep 會依 `functionAppName` 與 Resource Group 產生全域唯一的 Cosmos DB account 名稱。`cosmosDatabaseName` 預設為 `ipg-certificate`。目前已建立活動管理用的 `events` container，完訓證明用的 `completionCerts` 與 `completionCertRequests` containers，以及營業稅繳稅證明用的 `taxReceipts` container。資料模型與欄位規則請參考 [cosmos-data-model.md](cosmos-data-model.md)。

因為 Cosmos DB account 停用 local auth，Azure Portal 的 Data Explorer 也需要 Cosmos native RBAC。Azure RBAC 的 `Owner` 或 `Contributor` 可管理 account，但不會自動取得 Cosmos 資料面讀取權限。

若管理者需要在 Portal 檢視資料，應把 Cosmos DB Built-in Data Reader 授與既有的 Microsoft Entra 管理者安全群組，而不是直接授與個人帳號。Cosmos native RBAC 不接受 `Global Administrator` 這類 Entra directory role object ID 作為 principal；若需要讓全域系統管理員使用 Portal Data Explorer，應以安全群組承載這批管理者，再把群組 object ID 作為部署參數傳入。

建議的群組與部署方式如下：

1. 在 Microsoft Entra ID 建立專用 security group，例如 `<cosmos-portal-readers-group>`。
2. 將需要在 Azure Portal Data Explorer 檢視資料的管理者加入該群組。
3. 部署 Bicep 時傳入該群組的 object ID：

```bash
--parameters cosmosPortalDataReaderPrincipalIds='["<entra-security-group-object-id>"]'
```

這會授與 Cosmos DB Built-in Data Reader，scope 為 Cosmos account；應用程式本身仍使用 Function App system-assigned managed identity 的 database 範圍 Cosmos DB Built-in Data Contributor。實際群組 object ID 與成員名單屬於環境設定，不提交到儲存庫。

## 第一次手動佈署基礎設施

可直接用 CLI 覆寫參數：

```bash
az deployment group create \
  --name <deployment-name> \
  --resource-group <resource-group-name> \
  --template-file infra/bicep/main.bicep \
  --parameters location=<azure-region> \
               functionAppName=<function-app-name>
```

之後若有基礎設施變更，請另外以人工執行或獨立的高權限流程套用 Bicep，而不要直接放進日常程式碼部署 workflow。這樣可避免為一般 code deploy 身分開過大的 Azure 權限。

若要啟用管理平台 `/portal` 的 Google Workspace SSO + Google Group 授權，請另外依 `docs/portal-authentication.md` 完成 Google OAuth client、Cloud Identity API、Google Group 授權設定與對應 app settings 設定。Cloud Identity API 請依該文件使用 GCP Console 啟用。

production 的 portal 登入設定目前建議用 Azure CLI 寫入，不在 Azure Portal 手動輸入：

```bash
az functionapp config appsettings set \
  --resource-group <resource-group-name> \
  --name <function-app-name> \
  --settings \
    PORTAL_GOOGLE_CLIENT_ID=<google-client-id> \
    PORTAL_GOOGLE_CLIENT_SECRET=<google-client-secret> \
    PORTAL_GOOGLE_REDIRECT_URI=https://cert.iplayground.io/portal/auth/google/callback \
    PORTAL_GOOGLE_ALLOWED_GROUP_KEYS=<allowed-group-name-1>,<allowed-group-name-2>
```

## Azure Portal 與 GitHub 連線流程

在基礎設施已建立、GitHub OAuth 已可用後，於 Azure Portal 內完成以下設定：

1. 開啟目標 Function App 的 `部署中心`
2. `來源` 選擇 `GitHub`
3. 在 `登入身分` 完成 GitHub OAuth 授權
4. 選擇對應的 GitHub `組織`、`存放庫` 與 `分支`
5. `工作流程選項` 選擇 `使用可用的工作流程`
6. 按下 `儲存`

本專案目前採用的遠端 workflow 檔案為：

- `.github/workflows/deploy-function-app.yml`

若 Azure Portal 後續未正確辨識既有 workflow，而改為要求使用其他檔名，應先確認影響範圍後再調整 repo 內的 workflow 檔案。

## 這次 Bicep 會建立的資源

- 1 個 Flex Consumption Function App
- 1 個 Flex Consumption plan (`FC1`)
- 1 個 Storage Account
- 4 個 Blob containers
- `function-releases`
- `document-assets`
- `issued-certs`
- 1 個 Azure Cosmos DB for NoSQL serverless account，使用 Session consistency，並停用 local auth
- 1 個 Cosmos DB SQL database，預設名稱 `ipg-certificate`
- 5 個 Cosmos DB SQL containers
- `events`，partition key 為 `/id`
- `completionCerts`，partition key 為 `/eventId`
- `completionCertRequests`，partition key 為 `/eventId`
- `taxReceipts`，partition key 為 `/eventId`
- `publicLookupAttempts`，partition key 為 `/id`
- 1 個 Log Analytics Workspace
- 1 個 Application Insights
- 1 個 GitHub Actions 專用 user-assigned managed identity
- 1 個綁定到 `main` 分支的 federated credential
- Function App 執行所需的 Storage 與 Cosmos DB 存取設定

Blob container 用途：

- `function-releases`：Flex Consumption 部署套件
- `document-assets`：不進 git 的固定證明附件；目前已使用 `completion-cert/organization-seal.png` 存放單位印章圖，並使用 `completion-cert/previews/png/{locale}-{nameDisplay}-{org|no-org}.png` 存放首頁證明預覽圖，預覽 PDF 備份則存放於 `completion-cert/previews/pdf/{locale}-{nameDisplay}-{org|no-org}.pdf` 並使用 Archive tier
- `issued-certs`：產生後可再次下載的完訓證明 PDF；應以 Cool tier 儲存
- `tax-receipts`：管理端逐筆上傳的營業稅繳稅證明 PDF、PNG 或 JPG/JPEG 檔案

## 部署後需要設定的 GitHub Actions Secrets 與 Variables

目前 workflow 直接使用下列 GitHub Actions secrets，避免 Azure OIDC 識別資訊出現在公開 repository variables 或未遮罩的 workflow log：

- `AZURE_CLIENT_ID`
  說明：Bicep output `githubActionsIdentityClientId`
- `AZURE_TENANT_ID`
  說明：Bicep output `tenantId`
- `AZURE_SUBSCRIPTION_ID`
  說明：Bicep output `subscriptionId`

目前 workflow 直接使用下列 GitHub Actions variables：

- `AZURE_FUNCTIONAPP_NAME`
  說明：部署使用的 Function App 名稱

若希望把部署基本資訊一併保留在 GitHub repository variables，也可另外保存：

- `AZURE_RESOURCE_GROUP`
  說明：部署使用的 Resource Group 名稱
- `AZURE_LOCATION`
  說明：部署使用的 Azure region

若已完成 `gh auth login`，可直接用 GitHub CLI 設定：

```bash
gh secret set AZURE_CLIENT_ID --body "<github-actions-identity-client-id>" -R iplayground/CertificatePortal
gh secret set AZURE_TENANT_ID --body "<azure-tenant-id>" -R iplayground/CertificatePortal
gh secret set AZURE_SUBSCRIPTION_ID --body "<azure-subscription-id>" -R iplayground/CertificatePortal
gh variable set AZURE_RESOURCE_GROUP --body "<resource-group-name>" -R iplayground/CertificatePortal
gh variable set AZURE_LOCATION --body "<azure-region>" -R iplayground/CertificatePortal
gh variable set AZURE_FUNCTIONAPP_NAME --body "<function-app-name>" -R iplayground/CertificatePortal
```

設定完成後可用下列指令確認：

```bash
gh secret list -R iplayground/CertificatePortal
gh variable list -R iplayground/CertificatePortal
gh workflow list -R iplayground/CertificatePortal
```

## GitHub Actions workflow

目前 workflow 使用 GitHub Actions OIDC + `Azure/functions-action@v1`，只負責既有 Function App 的程式碼部署，不會重跑整份 Bicep。

### 觸發條件

- push 到 `main`
- 手動執行 `workflow_dispatch`

### 執行順序

1. checkout 原始碼
2. 設定 Python 3.13
3. 安裝 `requirements.txt` 內的 Python 依賴
4. 用 `compileall` 做語法檢查
5. 直接 import `function_app`，確認核心模組與依賴可載入
6. 查詢上一個 `ipg-certificate-production` GitHub deployment success 紀錄
7. 寫入 `build-info.json`，內容包含目前 commit SHA
8. 以 OIDC 登入 Azure
9. 透過 `Azure/functions-action` 對既有 Function App 做 remote build 與部署
10. 輪詢 `GET /api/health`，確認正式 endpoint 回傳目前 commit SHA
11. 健康檢查通過後建立 `ipg-certificate-production` GitHub deployment success 紀錄
12. 若部署或健康檢查失敗，且可取得 rollback ref，重新部署 rollback ref

### 健康檢查與 rollback

每次 workflow 部署前會在部署包寫入 `build-info.json`，內容包含該次 commit SHA。
正式站提供不需授權的 `GET /api/health`，回傳 `status` 與部署包內的 commit SHA。
部署完成後，workflow 會輪詢健康檢查，直到確認正式 endpoint 回傳目前 commit SHA。
健康檢查通過後，workflow 才會建立 `ipg-certificate-production` GitHub deployment
success 紀錄。此紀錄代表上一個已知健康部署版本，供後續自動 rollback 選擇 ref。

若部署或健康檢查未通過，workflow 會重新部署 rollback ref，優先順序如下：

1. 上一個 `ipg-certificate-production` GitHub deployment success 紀錄的 commit SHA。
2. 手動執行時填入的 `rollback_ref` input。
3. push 觸發時 GitHub push event 的 `before` SHA。

rollback 會重新 checkout rollback ref，並再次透過 `Azure/functions-action@v1`
上傳該版本。GitHub Deployments 只用來記錄健康版本與選擇 rollback ref；它不保存
部署包，也不提供 Azure 原生 rollback。

## 目前的 Azure 設定基線

- Runtime：Python `3.13`
- Hosting plan：Flex Consumption
- Host storage：`AzureWebJobsStorage__accountName`，以 system-assigned managed identity 存取
- Deployment storage：Blob container `function-releases`，以 system-assigned managed identity 存取
- Site update strategy：`RollingUpdate`
- Function App `httpsOnly`：啟用，僅允許 HTTPS 存取
- Cosmos DB：Azure Cosmos DB for NoSQL serverless account
- Cosmos DB local auth：停用，Function App 以 system-assigned managed identity 取得 database 範圍的 Cosmos DB Built-in Data Contributor 權限
- Cosmos Portal inspection：可透過 `cosmosPortalDataReaderPrincipalIds` 為管理者安全群組授與 account 範圍 Cosmos DB Built-in Data Reader
- Cosmos app settings：`COSMOS_ENDPOINT`、`COSMOS_DATABASE_NAME`、`COSMOS_EVENTS_CONTAINER`、`COSMOS_COMPLETION_CERTS_CONTAINER`、`COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER`、`COSMOS_TAX_RECEIPTS_CONTAINER` 與 `COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER` 由 Bicep 寫入 Function App
- Blob app settings：`BLOB_DOCUMENT_ASSETS_CONTAINER`、`BLOB_ISSUED_CERT_CONTAINER` 與 `BLOB_TAX_RECEIPTS_CONTAINER` 由 Bicep 寫入 Function App，預設分別指向 `document-assets`、`issued-certs` 與 `tax-receipts`
- Cosmos containers：`events` 使用 `/id` 作為 partition key，供活動管理資料使用；完訓證明與營業稅繳稅證明 containers 依 [cosmos-data-model.md](cosmos-data-model.md) 使用 `/eventId`

Bicep 只建立 Blob containers 與 Function App app settings，不會上傳不進 git 的固定素材。重新建立環境後，仍需將單位印章圖與首頁證明預覽圖上傳到 `document-assets`：

- `completion-cert/organization-seal.png`
- `completion-cert/previews/png/{locale}-{nameDisplay}-{org|no-org}.png`
- `completion-cert/previews/pdf/{locale}-{nameDisplay}-{org|no-org}.pdf`，上傳後應設定為 Archive tier

## 資料回填與維護腳本

當完訓證明下載統計或活動預聚合欄位 schema 變更後，需在已部署環境的 Cosmos DB 執行回填。下載統計目前使用：

- `completionCerts.downloadCount`：單張完訓證明累計下載次數，同一位重複下載會重複計次
- `completionCerts.firstDownloadAt`：第一次下載時間
- `completionCerts.lastDownloadAt`：最近一次下載時間
- `events.metrics.completionCert.downloadCount`：活動層完訓證明累計下載人次

回填腳本會讀取 `local.settings.json` 的 `Values` 作為本機環境設定，並使用 `DefaultAzureCredential` 連線 Cosmos DB；本機執行者需已透過 Azure CLI 或其他支援的 credential 登入，且具備 Cosmos DB SQL Data Contributor 權限。

先 dry-run：

```bash
python3 scripts/backfill_completion_cert_metrics.py
```

確認輸出的待更新數量後再寫入：

```bash
python3 scripts/backfill_completion_cert_metrics.py --apply
```

可用 `--event-id <event-id>` 限定單一活動。腳本可重複執行；回填完成後再次 dry-run 應顯示 `eventsUpdated: 0` 與 `completionCertsUpdated: 0`。

首頁發證流程會在產生完訓證明 PDF 後上傳到 `issued-certs`，並由程式指定為 Cool tier；若以手動方式補上或修正 `issued-certs` 內的已發證 PDF，也應同步設定為 Cool tier。

## 注意事項

- Flex Consumption 只支援 One Deploy 路徑，不應混用舊式 Zip Deploy 設定。
- `RollingUpdate` 是 Azure Function App 的站台設定，需先透過 `az deployment group create` 套用 `infra/bicep/main.bicep` 後才會在 Azure 生效；只修改 workflow 或只部署程式碼不會改變既有 Function App 的 site update strategy。
- `workflow_dispatch` 應從 `main` 分支觸發；目前 OIDC federated credential 明確綁定 `repo:iplayground/CertificatePortal:ref:refs/heads/main`。
- 目前 GitHub OIDC 身分只需要支援應用程式程式碼部署，不應為了日常 deploy 額外授與整個 resource group 的基礎設施管理權限。
- workflow 目前使用支援 Node.js 24 的 `actions/checkout@v6`、`actions/setup-python@v6` 與 `actions/github-script@v8`；若未來改用 self-hosted runner，runner 版本需維持在 GitHub 官方 action 要求的最低版本以上。
- 若變更 GitHub repo 名稱、組織或主要分支，必須同步更新 federated credential，否則 OIDC 會失效。
- `functionAppName` 一旦上線後就不建議任意變更，否則會影響 DNS、監控命名與既有部署設定。

## 自訂網域設定

目前規劃的公開自訂子網域為：

- `cert.iplayground.io`

若要把 `cert.iplayground.io` 指到目前的 Function App，DNS 供應商端至少需建立下列記錄：

- `CNAME`：`cert` -> `<azure-portal-shown-default-function-hostname>`
- `TXT`：`asuid.cert` -> `<app-service-domain-verification-id>`

說明：

- `TXT asuid.cert` 用於 App Service 驗證網域所有權。
- `CNAME cert` 用於把子網域流量導向 Azure 指定的預設 Function host。
- 若 DNS 供應商支援 proxy 或 CDN 模式，驗證期間應先維持純 DNS 模式，避免 Azure 看不到正確記錄。

DNS 完成並傳播後，可用下列指令完成 hostname binding：

```bash
az functionapp config hostname add \
  --resource-group <resource-group-name> \
  --name <function-app-name> \
  --hostname cert.iplayground.io
```

### 目前限制

截至 2026-04-23，Azure Functions Flex Consumption 在文件與實際產品行為之間仍有不一致：

- `az functionapp config ssl create` 這條舊 CLI 路徑目前會直接回覆不支援 Flex Consumption。
- Azure Portal 已可對符合條件的 hostname 顯示「可建立 App Service 受控憑證」。
- 實測可透過 `Microsoft.Web/sites/certificates` endpoint 建立站台範圍的 App Service Managed Certificate，並再把 thumbprint 綁回 hostname binding。

以 `cert.iplayground.io` 為例，實測可行流程如下：

1. 先建立 hostname binding。
2. 建立站台範圍受控憑證：

```bash
az resource create \
  --resource-group <resource-group-name> \
  --namespace Microsoft.Web \
  --resource-type certificates \
  --parent sites/<function-app-name> \
  --name <managed-certificate-resource-name> \
  --api-version <site-certificates-api-version> \
  --is-full-object \
  --properties '{
    "location": "<azure-region>",
    "properties": {
      "canonicalName": "cert.iplayground.io",
      "domainValidationMethod": "http-token",
      "hostNames": [
        "cert.iplayground.io"
      ]
    }
  }'
```

3. 再把受控憑證 thumbprint 綁到 hostname binding：

```bash
az rest \
  --method put \
  --url "https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Web/sites/<function-app-name>/hostNameBindings/cert.iplayground.io?api-version=<host-name-bindings-api-version>" \
  --body '{
    "properties": {
      "siteName": "<function-app-name>",
      "hostNameType": "Verified",
      "sslState": "SniEnabled",
      "thumbprint": "<certificate-thumbprint>"
    }
  }'
```

4. 可用下列指令驗證目前站台已綁定哪張憑證：

```bash
az rest \
  --method get \
  --url "https://management.azure.com/subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Web/sites/<function-app-name>?api-version=<sites-api-version>" \
  --query "properties.hostNameSslStates"
```

### ASMC 政策更新

依 2025-11 的 App Service Managed Certificates 政策更新，ASMC 驗證已改為由 App Service front end 回應 DigiCert 的 HTTP token 驗證請求。這表示：

- 即使站台有限制公開存取，只要其他條件符合，ASMC 仍可簽發與續期。
- 仍然需要 public DNS 記錄。
- 不需要另外 allowlist DigiCert IP。
- Traffic Manager `Nested` / `External` endpoint 與 `*.trafficmanager.net` 仍屬不支援情境。

參考文件：

- Microsoft Learn: `app-service-managed-certificate-changes-july-2025`
- Tech Community: `Follow-Up to 'Important Changes to App Service Managed Certificates': November 2025 Update`
