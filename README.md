# CertificatePortal

iPlayground 完訓證明系統。

目前專案先提供最小可運作頁面，用於確認 Azure Functions 路由、本機啟動流程，以及首頁 GUI 基線。

## 目前範圍

- 首頁 `/`
- 管理平台登入入口 `/portal`
- 公開驗證頁面 `/verify/{certId}`

首頁與管理平台目前為 HTML 頁面，公開驗證頁面仍為純文字；三者都尚未包含實際業務資料、資料庫存取或檔案處理。

管理平台目前已建立 Google Workspace Internal SSO 基線：

- `/portal` 會依應用程式內建的 Google OAuth 流程與 session cookie 判斷目前狀態
- 未登入時顯示 Google SSO 登入入口與返回首頁連結
- 已登入但缺少可用 email claim 時顯示權限不足畫面
- 已登入且具有可用 email 的帳號可進入 `/portal/dashboard`
- `/portal/dashboard` 與其子頁都會在伺服器端再次檢查 session cookie 與 email claim，不依賴前端暫存

## 目前頁面基線

- 首頁與公開驗證頁支援 `zh-TW` 與 `en-US`，並以 `ipg_locale` cookie 搭配 `Accept-Language` 決定語系
- 語系切換器只出現在首頁 `/`，切換時由前端直接更新文案，不會整頁重新整理
- 管理平台固定使用繁體中文，入口與子路徑統一收斂在 `/portal...`，不納入 i18n 範圍
- 首頁與管理平台共用 `/assets/theme.css` 主題 token，並依 `prefers-color-scheme` 切換日夜模式
- 所有 HTML 頁面都載入共用 favicon 與標題格式，`/portal/dashboard` 會同步 iframe 內容頁 title
- 首頁只保留 `twitter:card`，其餘社群分享資訊以 Open Graph metadata 為主
- locale JSON 字典檔集中於 `src/shared/locales/`，並由測試驗證結構一致性

## 技術基線

- Python `3.13`
- Azure Functions `v4`
- Azure Functions Core Tools `v4`

## 主要入口路由

| Method | Path | 說明 | Content-Type |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾填寫基本資料並進入完訓證明流程 | `text/html; charset=utf-8` |
| `GET` | `/portal` | 管理平台登入入口 | `text/html; charset=utf-8` |
| `GET` | `/assets/{assetName}` | 目前頁面所需的靜態樣式、互動腳本與品牌素材 | 依資產而定 |
| `GET` | `/verify/{certId}` | 公開驗證頁面 | `text/plain; charset=utf-8` |

完整頁面路徑、共用規則與各頁面內容請參考 [docs/page-paths.md](docs/page-paths.md)。

## 本機開發

### 需求

- `Python 3.13`
- `Azure Functions Core Tools v4`

### 安裝套件

```bash
python3 -m pip install -r requirements.txt
```

若需要執行測試，另外安裝開發相依：

```bash
python3 -m pip install -e ".[dev]"
```

### 建立本機設定檔

```bash
cp local.settings.json.example local.settings.json
```

接著依本機或 Azure 環境需求，自行填入 `local.settings.json` 內的實際值。

若要在本機直接驗證 Google 登入，請設定與 Azure 相同命名的 portal Google OAuth app settings。本機與 production 應各自使用分開的 OAuth client 實際值：

```json
{
  "PORTAL_GOOGLE_CLIENT_ID": "<local-google-client-id>",
  "PORTAL_GOOGLE_CLIENT_SECRET": "<local-google-client-secret>",
  "PORTAL_GOOGLE_REDIRECT_URI": "http://localhost:7075/portal/auth/google/callback"
}
```

若只想快速查看管理平台 UI、不經過真正的 Google OAuth，可暫時開啟：

```json
{
  "PORTAL_AUTH_BYPASS_ENABLED": "true"
}
```

其中 `PORTAL_GOOGLE_*` 代表 local 與 Azure 共用的登入流程參數名稱，但本機與 production 應各自填入對應的 client 值；只有 bypass 設定只限本機開發，不得部署到正式環境。

### 啟動

```bash
func start --port 7075 --skip-azure-storage-check
```

啟動後可打開：

- [http://localhost:7075/](http://localhost:7075/)
- [http://localhost:7075/portal](http://localhost:7075/portal)
- [http://localhost:7075/verify/demo-cert](http://localhost:7075/verify/demo-cert)

### 測試

```bash
python3 -m pytest
```

若本機直接執行 `pytest` 時發生 `ModuleNotFoundError: No module named 'src'`，可改用：

```bash
PYTHONPATH=. pytest
```

其中 `tests/shared/test_i18n_catalog.py` 會獨立檢查所有 locale JSON 檔是否與 `SUPPORTED_LOCALES` 一致、結構完全對齊，且可被 i18n catalog 載入。

## 注意事項

- `local.settings.json.example` 是可提交的模板；Azure 資源相關欄位預設留空，需由開發者自行填入。實際使用的 `local.settings.json` 仍維持忽略，不進 git。
- `local.settings.json` 內已設定 `AzureWebJobsDisableHomepage=true`，避免根目錄顯示 Azure Functions 預設首頁。
- 目前未接 Azurite 或實體 Storage Account，因此本機啟動時可能看到 `AzureWebJobsStorage` 的 unhealthy 訊息；在 `--skip-azure-storage-check` 下，這不影響目前首頁、靜態資產路由與公開驗證頁面。
- 管理平台入口現已統一使用 `/portal`，避免與 Azure Functions runtime 內建保留的 `/admin` 路徑衝突。
- `/portal` 正式環境目前應明確設定 `PORTAL_GOOGLE_CLIENT_ID`、`PORTAL_GOOGLE_CLIENT_SECRET` 與 `PORTAL_GOOGLE_REDIRECT_URI`；建議以 Azure CLI 寫入 app settings，詳細流程請參考 [docs/portal-authentication.md](docs/portal-authentication.md)。
- 目前尚未保留其他管理子路由、下載流程與實際業務邏輯。

## Azure 部署

目前已建立以 GitHub Actions + OIDC 部署 Azure Functions Flex Consumption 的基線檔案：

- [infra/bicep/main.bicep](infra/bicep/main.bicep)
- [.github/workflows/deploy-function-app.yml](.github/workflows/deploy-function-app.yml)
- [docs/deployment-github-actions.md](docs/deployment-github-actions.md)
- [docs/portal-authentication.md](docs/portal-authentication.md)

目前部署基線已固定，但實際 Azure 設定值不提交到 git。`infra/bicep/` 負責定義 Azure 資源，Azure CLI 負責套用這些定義，GitHub Actions 則負責既有 Function App 的程式碼部署。完整流程請參考 [docs/deployment-github-actions.md](docs/deployment-github-actions.md)。
