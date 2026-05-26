# CertificatePortal

iPlayground 證明與文件管理系統，執行於 Azure Functions v4 / Python 3.13。

本專案目前提供：

- 首頁文件查詢與申請流程
- 公開證明驗證頁
- 管理平台登入、活動管理、完訓證明、志工服務證明、修改審核與營業稅繳稅證明管理流程
- Cosmos DB metadata、Blob Storage 文件檔案與 GitHub Actions 部署基線

## 技術基線

- Python `3.13`
- Azure Functions `v4`
- Azure Functions Core Tools `v4`
- Azure Cosmos DB for NoSQL
- Azure Blob Storage
- GitHub Actions + Azure OIDC 部署

## 專案結構

```text
infra/
  bicep/        Azure 資源定義
src/
  functions/   Azure Functions HTTP 入口、HTML templates 與靜態資產
  shared/      共用領域邏輯、資料存取、PDF 產生與 i18n
tests/         單元測試與功能測試
docs/          架構、路徑、部署與維運文件
scripts/       回填、樣張產生與維運腳本
```

## 主要路徑

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/` | 首頁文件查詢與申請 |
| `GET` | `/portal` | 管理平台登入入口 |
| `GET` | `/portal/dashboard` | 管理平台工作區 |
| `GET` | `/verify/{certId}` | QRCode 公開驗證頁 |
| `GET` | `/api/v1/events` | 公開活動清單 |
| `POST` | `/api/v1/document-lookup` | 公開文件查詢 |
| `POST` | `/api/v1/completion-certs/issue` | 產生或下載參與證明 PDF |
| `POST` | `/api/v1/tax-receipts/download` | 下載營業稅繳稅證明檔案 |

完整頁面、API 與互動規則請看 [docs/page-paths.md](docs/page-paths.md)。

## 本機開發

安裝 runtime 與套件：

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e ".[dev]"
```

建立本機設定檔：

```bash
cp local.settings.json.example local.settings.json
```

啟動 Azure Functions：

```bash
func start --port 7075 --skip-azure-storage-check
```

啟動後可打開：

- [http://localhost:7075/](http://localhost:7075/)
- [http://localhost:7075/portal](http://localhost:7075/portal)
- [http://localhost:7075/verify/demo-cert](http://localhost:7075/verify/demo-cert)

管理平台本機開發預設可使用 bypass 檢視 UI：

```json
{
  "PORTAL_AUTH_BYPASS_ENABLED": "true",
  "PORTAL_AUTH_BYPASS_DISPLAY_NAME": "本機管理者",
  "PORTAL_AUTH_BYPASS_EMAIL": "local-admin@iplayground.io"
}
```

若需要端到端驗證 Google OAuth 與 Google Group 授權，請依 [docs/portal-authentication.md](docs/portal-authentication.md) 設定本機 OAuth app settings。

## 測試

```bash
python3 -m pytest
```

若直接執行 `pytest` 遇到 `ModuleNotFoundError: No module named 'src'`，可改用：

```bash
PYTHONPATH=. pytest
```

## 文件索引

- [AGENTS.md](AGENTS.md)：專案基準約定、架構原則、安全規則與 agent 工作規範
- [docs/page-paths.md](docs/page-paths.md)：頁面路徑、API、公開查詢與前端互動規則
- [docs/cosmos-data-model.md](docs/cosmos-data-model.md)：Cosmos DB containers、欄位模型、查詢模式與回填說明
- [docs/deployment-github-actions.md](docs/deployment-github-actions.md)：Azure Bicep、GitHub Actions OIDC、部署與 rollback 流程
- [docs/portal-authentication.md](docs/portal-authentication.md)：Google Workspace SSO、Google Group 授權與相關 app settings
- [docs/adr/](docs/adr/)：已接受的架構決策紀錄

## 本機與設定注意事項

- `local.settings.json.example` 是可提交的範本；實際 `local.settings.json` 不進 git。
- 本機預設使用 `7075` port。
- `local.settings.json` 內設定 `AzureWebJobsDisableHomepage=true`，避免根目錄顯示 Azure Functions 預設首頁。
- 目前本機啟動可使用 `--skip-azure-storage-check`；在未接 Azurite 或實體 Storage Account 時，Storage unhealthy 訊息不影響首頁、靜態資產與公開驗證頁的基本開發。
- 靜態資產以內容 hash 版本化，例如 `/assets/home.css?v=<content-hash>`；版本相符時使用長效快取，不符或未帶版本時回 `no-store`。
- PDF 中文動態文字需要可嵌入字體；本機字體放置方式請看 [src/shared/pdf_fonts/README.md](src/shared/pdf_fonts/README.md)。

## Azure 部署

基礎設施以 [infra/bicep/main.bicep](infra/bicep/main.bicep) 定義，程式碼部署由 GitHub Actions workflow 負責。實際 Azure 設定值、機密、publish profile 與環境匯出檔不得提交到 repository。

完整部署流程請看 [docs/deployment-github-actions.md](docs/deployment-github-actions.md)。
