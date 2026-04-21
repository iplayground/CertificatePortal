# ADR 0001: Azure Functions 採用 GitHub Actions OIDC 部署

- 狀態：Accepted
- 日期：2026-04-21

## 背景

本專案採用 Azure Functions Flex Consumption 作為正式執行環境，程式碼已託管於 GitHub。

若部署流程依賴 publish profile、長效 client secret 或手動 Portal 操作，會造成下列問題：

- 機密管理負擔提高
- 部署流程不可審查、不可重現
- 環境初始化容易與程式碼版本脫鉤

同時，AGENTS.md 已明確要求：

- 優先使用 Bicep 作為基礎設施即程式碼
- 只要 Azure 能乾淨支援，就優先使用 Managed Identity
- 正式部署以 Linux 上的 Flex Consumption 為基準

## 決策

本專案決定採用以下部署基線：

1. 以 `infra/bicep/main.bicep` 定義 Azure Functions Flex Consumption 所需的最小資源。
2. 以 GitHub Actions 作為正式 CI/CD 入口，工作流程檔案存放於 `.github/workflows/deploy-function-app.yml`。
3. GitHub Actions 與 Azure 的驗證採用 OIDC，並以 Azure user-assigned managed identity 搭配 federated credential 建立信任關係。
4. Function App 的應用程式程式碼部署採用 Flex Consumption 支援的 One Deploy 路徑，並由 `Azure/functions-action` 以 `remote-build: true` 進行遠端建置與部署。
5. Function App 的 host storage 優先採用 managed identity 連線，避免在 Function App 設定中保存 Storage account key 連線字串。
6. 例行 GitHub Actions workflow 僅負責程式碼部署，不在每次 push 時重跑整份基礎設施；Bicep 套用維持手動或獨立高權限流程，以避免對日常部署身分授與過大的 Azure 權限。

## 影響

正面影響：

- GitHub 不需要保存 Azure publish profile 或長效 client secret
- 基礎設施與部署流程可由 pull request 一併審查
- 基礎設施可透過 Bicep 重建
- 後續擴充 Cosmos DB、Blob 容器與監控設定時，可沿用同一條部署路徑

代價與限制：

- 首次部署後，仍需將 `AZURE_CLIENT_ID`、`AZURE_TENANT_ID`、`AZURE_SUBSCRIPTION_ID` 設定到 GitHub Actions secrets，並將 `AZURE_RESOURCE_GROUP`、`AZURE_LOCATION`、`AZURE_FUNCTIONAPP_NAME` 設定到 GitHub Actions variables
- Flex Consumption 的部署與執行行為依賴 deployment container，因此 Bicep 必須在 Function App 建立前先定義相對應的 Blob container
- 若未來要把 Bicep 套用也納入 GitHub Actions，必須另外設計較高權限的部署身分與審核機制，不能直接沿用日常 code deploy 身分

## 後續

- 依功能演進加入 Cosmos DB 與 Key Vault 的 IaC
- 若後續引入手動核准流程，可再補上部署保護機制
