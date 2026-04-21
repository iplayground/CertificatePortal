# Azure Functions GitHub 部署說明

本文件說明本專案目前採用的 Azure Functions Flex Consumption + GitHub Actions 部署流程。

## 目前部署方式

- 基礎設施：`infra/bicep/main.bicep`
- CI/CD：`.github/workflows/deploy-function-app.yml`
- Azure 驗證：GitHub Actions OIDC + Azure user-assigned managed identity
- 程式碼部署：`Azure/functions-action@v1` + `remote-build: true`
- 例行 workflow 只部署 Function App 程式碼，不在每次 push 時重跑整份 Bicep

## 目前 production 基線

- 目前只維護 production，一切 IaC 與 workflow 都以這套設定為準
- Resource Group、Region 與 Function App 名稱由 GitHub Actions variables 或部署命令參數提供

實際的 Function App 名稱必須保持 Azure 全域唯一，並會同時影響：

- Azure Function App 名稱
- 預設公開網址 `https://<functionAppName>.azurewebsites.net`
- 由 Bicep 衍生出的 Storage Account、Application Insights、Log Analytics 與 GitHub 部署身分命名

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
- 4 個必要 RBAC role assignments

## 部署後需要設定的 GitHub Actions Secrets 與 Variables

目前 workflow 直接使用下列 GitHub Actions secrets，避免 Azure OIDC 識別資訊出現在公開 repository variables 或未遮罩的 workflow log：

- `AZURE_CLIENT_ID`
  說明：Bicep output `githubActionsIdentityClientId`
- `AZURE_TENANT_ID`
  說明：Bicep output `tenantId`
- `AZURE_SUBSCRIPTION_ID`
  說明：Bicep output `subscriptionId`

目前 workflow 直接使用下列 GitHub Actions variables：

- `AZURE_RESOURCE_GROUP`
  說明：production 使用的 Resource Group 名稱
- `AZURE_LOCATION`
  說明：production 使用的 Azure region
- `AZURE_FUNCTIONAPP_NAME`
  說明：production 使用的 Function App 名稱

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

## GitHub Actions 觸發條件

- push 到 `main`
- 手動執行 `workflow_dispatch`
- 目前 workflow 不綁定 GitHub Actions `environment`

流程順序如下：

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

## 注意事項

- Flex Consumption 只支援 One Deploy 路徑，不應混用舊式 Zip Deploy 設定。
- 目前 workflow 與 IaC 已收斂為單一 production 基線。
- `workflow_dispatch` 應從 `main` 分支觸發；目前 OIDC federated credential 明確綁定 `repo:iplayground/CertificatePortal:ref:refs/heads/main`。
- 若在 workflow 內加入 GitHub Actions `environment`，OIDC subject 會改成 `repo:iplayground/CertificatePortal:environment:<name>`；除非同步調整 Azure federated credential，否則 `azure/login` 會失敗。
- 目前 GitHub OIDC 身分只需要支援應用程式程式碼部署，不應為了日常 deploy 額外授與整個 resource group 的基礎設施管理權限。
- 若變更 GitHub repo 名稱、組織或主要分支，必須同步更新 federated credential，否則 OIDC 會失效。
- `functionAppName` 一旦上線後就不建議任意變更，否則會影響 DNS、監控命名與既有部署設定。
