# CertificatePortal

iPlayground 完訓證明系統。

目前專案只保留最小可運作頁面，用於先確認 Azure Functions 路由與本機啟動流程。

## 目前範圍

- 首頁 `/`
- 公開驗證頁面 `/verify/{certId}`

兩個頁面目前都只回傳純文字，不包含任何業務邏輯、資料庫存取或檔案處理。

## 技術基線

- Python `3.13`
- Azure Functions `v4`
- Azure Functions Core Tools `v4`

## 目前路由

| Method | Path | 說明 | Content-Type |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾生成或下載完訓證明 | `text/plain; charset=utf-8` |
| `GET` | `/verify/{certId}` | 公開驗證頁面 | `text/plain; charset=utf-8` |

詳細定義可參考 [docs/page-paths.md](docs/page-paths.md)。

## 頁面輸出

### `/`

```text
iPlayground 完訓證明首頁

用途: 供會眾生成或下載完訓證明
status: 尚未串接實際功能
```

### `/verify/{certId}`

當 `certId` 為 `demo-cert` 時：

```text
iPlayground 完訓證明驗證頁面

certId: demo-cert
status: 尚未串接實際驗證資料
```

## 本機開發

### 需求

- `Python 3.13`
- `Azure Functions Core Tools v4`

### 安裝套件

```bash
python3 -m pip install -r requirements.txt
```

### 建立本機設定檔

```bash
cp local.settings.json.example local.settings.json
```

接著依本機或 Azure 環境需求，自行填入 `local.settings.json` 內的實際值。

### 啟動

```bash
func start --port 7075 --skip-azure-storage-check
```

啟動後可打開：

- [http://localhost:7075/](http://localhost:7075/)
- [http://localhost:7075/verify/demo-cert](http://localhost:7075/verify/demo-cert)

## 注意事項

- `local.settings.json.example` 是可提交的模板；Azure 資源相關欄位預設留空，需由開發者自行填入。實際使用的 `local.settings.json` 仍維持忽略，不進 git。
- `local.settings.json` 內已設定 `AzureWebJobsDisableHomepage=true`，避免根目錄顯示 Azure Functions 預設首頁。
- 目前未接 Azurite 或實體 Storage Account，因此本機啟動時可能看到 `AzureWebJobsStorage` 的 unhealthy 訊息；在 `--skip-azure-storage-check` 下，這不影響目前兩個純文字頁面。
- 目前不保留其他 API、管理路由與下載流程。

## Azure 部署

目前已建立以 GitHub Actions + OIDC 部署 Azure Functions Flex Consumption 的基線檔案：

- [infra/bicep/main.bicep](infra/bicep/main.bicep)
- [.github/workflows/deploy-function-app.yml](.github/workflows/deploy-function-app.yml)
- [docs/deployment-github-actions.md](docs/deployment-github-actions.md)

目前基線已收斂為單一 production 環境，但實際 Azure 設定值不提交到 git。`infra/bicep/` 負責定義 Azure 資源，Azure CLI 負責套用這些定義，GitHub Actions 則負責既有 Function App 的程式碼部署。完整流程請參考 [docs/deployment-github-actions.md](docs/deployment-github-actions.md)。
