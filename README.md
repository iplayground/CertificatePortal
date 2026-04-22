# CertificatePortal

iPlayground 完訓證明系統。

目前專案先提供最小可運作頁面，用於確認 Azure Functions 路由、本機啟動流程，以及首頁 GUI 基線。

## 目前範圍

- 首頁 `/`
- 管理平台登入入口 `/portal`
- 公開驗證頁面 `/verify/{certId}`

首頁與管理平台目前為靜態 HTML GUI，公開驗證頁面仍為純文字；三者都尚未包含業務邏輯、資料庫存取或檔案處理。

目前頁面已建立最小 i18n 基線：

- 支援 `zh-TW` 與 `en-US`
- 若使用者曾在首頁切換語系，後續頁面優先使用 `ipg_locale` cookie
- 只有在沒有語系 cookie 時，才會依瀏覽器 `Accept-Language` 決定初始語系
- 語系切換器目前只出現在首頁 `/`
- 首頁切換語系時，會由前端直接更新文案，不會整頁重新整理
- locale JSON 字典檔集中於 `src/shared/locales/`，並由獨立測試驗證結構一致性

目前首頁與管理平台已建立共用主題基線：

- 預設依使用者 `prefers-color-scheme` 自動切換日間與夜間模式
- 日間模式沿用首頁既有的淺色品牌視覺
- 夜間模式沿用管理平台既有的深色品牌視覺
- 首頁與管理平台共用 `/assets/theme.css` 主題 token，個別頁面樣式只處理版面與元件配置
- 日間模式的主要 CTA 按鈕目前收斂為單一藍色系

管理平台目前不納入 i18n：

- 入口固定為 `/portal`
- 首頁 `/` 不提供管理平台入口按鈕
- 文案固定使用繁體中文
- 目前先只完成登入頁 GUI 與前端欄位檢查

目前 HTML 頁面已建立共用 head 基線：

- 所有 HTML 頁面都載入 `/assets/favicon.png`
- 頁面 title 統一使用 `頁面名稱 - iPlayground`
- `/portal/dashboard` 會在 iframe 載入後，將父頁 title 同步成目前內容頁 title
- 首頁只保留 `twitter:card`，其餘社群分享資訊以 Open Graph metadata 為主

## 技術基線

- Python `3.13`
- Azure Functions `v4`
- Azure Functions Core Tools `v4`

## 目前路由

| Method | Path | 說明 | Content-Type |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾填寫基本資料並進入完訓證明流程 | `text/html; charset=utf-8` |
| `GET` | `/portal` | 管理平台登入入口 | `text/html; charset=utf-8` |
| `GET` | `/assets/{assetName}` | 目前頁面所需的靜態樣式、互動腳本與品牌素材 | 依資產而定 |
| `GET` | `/verify/{certId}` | 公開驗證頁面 | `text/plain; charset=utf-8` |

詳細定義可參考 [docs/page-paths.md](docs/page-paths.md)。

## 頁面輸出

### `/`

首頁目前提供：

- 置中單卡式首頁版型
- 套用 iPlayground 官方 logo 與品牌色
- logo 置中顯示
- 首頁語系切換器，支援 `zh-TW` 與 `en-US`
- 活動名自訂下拉元件，固定為 `iPlayground 2026`
- 報名人姓名輸入欄位
- `email` 輸入欄位
- 前端提示訊息，明確說明目前尚未串接資料庫與證明生成流程
- 頁尾版權聲明

### `/portal`

管理平台登入頁目前提供：

- 置中單卡式登入版型
- 固定以 `/portal` 作為管理入口
- `完訓證明管理平台` 標題與 `管理者登入` 小標
- 延用與首頁相同的日夜主題切換規則
- 管理者帳號欄位，使用 `email` 輸入格式
- 密碼欄位與顯示或隱藏密碼互動
- 登入按鈕預設為 disabled，只有在帳號與密碼都已輸入且帳號符合 `email` 格式時才可點擊
- 前端欄位檢查與尚未串接實際驗證流程的提示
- 固定使用繁體中文，不提供 i18n 切換

### `/verify/{certId}`

當 `certId` 為 `demo-cert` 時：

```text
iPlayground 完訓證明驗證頁面

certId: demo-cert
status: 尚未串接實際驗證資料
```

若首頁已切換語系，公開驗證頁面會沿用相同 cookie 語系；否則才回退到瀏覽器 `Accept-Language`。

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
- 目前尚未保留其他管理子路由、下載流程與實際登入驗證邏輯。

## Azure 部署

目前已建立以 GitHub Actions + OIDC 部署 Azure Functions Flex Consumption 的基線檔案：

- [infra/bicep/main.bicep](infra/bicep/main.bicep)
- [.github/workflows/deploy-function-app.yml](.github/workflows/deploy-function-app.yml)
- [docs/deployment-github-actions.md](docs/deployment-github-actions.md)

目前基線已收斂為單一 production 環境，但實際 Azure 設定值不提交到 git。`infra/bicep/` 負責定義 Azure 資源，Azure CLI 負責套用這些定義，GitHub Actions 則負責既有 Function App 的程式碼部署。完整流程請參考 [docs/deployment-github-actions.md](docs/deployment-github-actions.md)。
