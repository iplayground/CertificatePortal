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
- `source-uploads`
- `cert-templates`
- `issued-certs`
- 1 個 Log Analytics Workspace
- 1 個 Application Insights
- 1 個 GitHub Actions 專用 user-assigned managed identity
- 1 個綁定到 `main` 分支的 federated credential
- 4 個 Function App 執行所需的存取設定

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
6. 以 OIDC 登入 Azure
7. 透過 `Azure/functions-action` 對既有 Function App 做 remote build 與部署

## 目前的 Azure 設定基線

- Runtime：Python `3.13`
- Hosting plan：Flex Consumption
- Host storage：`AzureWebJobsStorage__accountName`，以 system-assigned managed identity 存取
- Deployment storage：Blob container `function-releases`，以 system-assigned managed identity 存取
- Function App `httpsOnly`：啟用，僅允許 HTTPS 存取

## 注意事項

- Flex Consumption 只支援 One Deploy 路徑，不應混用舊式 Zip Deploy 設定。
- `workflow_dispatch` 應從 `main` 分支觸發；目前 OIDC federated credential 明確綁定 `repo:iplayground/CertificatePortal:ref:refs/heads/main`。
- 目前 GitHub OIDC 身分只需要支援應用程式程式碼部署，不應為了日常 deploy 額外授與整個 resource group 的基礎設施管理權限。
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
