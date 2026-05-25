# CertificatePortal

iPlayground 完訓證明系統。

目前專案提供首頁文件查詢、管理平台登入與公開驗證頁的 Azure Functions 基線。

## 目前範圍

- 首頁 `/` 與公開文件查詢 API
- 管理平台登入入口 `/portal`
- 公開驗證頁面 `/verify/{certId}`

首頁、公開驗證頁與管理平台目前為 HTML 頁面；首頁活動清單、完訓證明查詢、公開查詢限制與完訓證明 QRCode 驗證已串接 Cosmos DB。

管理平台目前已建立 Google Workspace SSO + Google Group 授權基線：

- `/portal` 會依應用程式內建的 Google OAuth 流程、Google Group 驗證結果與 session cookie 判斷目前狀態
- 未登入時顯示 Google SSO 登入入口與返回首頁連結
- 只有已加入允許 Google Group 直接成員的帳號可進入 `/portal/dashboard`
- `/portal/dashboard` 與其子頁都會在伺服器端再次檢查 session cookie，不依賴前端暫存

## 目前頁面基線

- 首頁與公開驗證頁支援 `zh-TW` 與 `en-US`，並以 `ipg_locale` cookie 搭配 `Accept-Language` 決定語系
- 語系切換器共用 `/assets/locale-switcher.js` 與 `/assets/theme.css` 內的共用樣式；首頁 `/` 切換時由前端直接更新文案，不會整頁重新整理，公開驗證頁 `/verify/{certId}` 切換時會寫入 `ipg_locale` cookie 並重新載入同一個 QRCode URL
- 首頁文件查詢期間會顯示全 window 黑色半透明遮罩，中央使用純白 loading panel 顯示查詢中狀態，並阻擋語系切換與表單操作
- 公開驗證頁會依 QRCode 內的驗證 token 查詢已發證完訓證明，只顯示驗證狀態、證明編號、活動、證明姓名、依證書顯示設定決定是否顯示任職單位，以及本地化發證時間；發證時間以可讀 UTC fallback 輸出，瀏覽器端再依使用者語系與時區本地化
- 完訓證明查詢成功且 `certStatus` 為 `notIssued` 或 `changeRequested` 時，首頁會顯示「選擇證明顯示方式」UI；`notIssued` 可進入「修改申請」並寫入 Cosmos DB，`changeRequested` 會顯示處理中提示並隱藏「提出修改申請」；若已有已完成審核的修改申請，首頁會顯示通過或駁回結果，並在有審核備註時以第二行顯示 `審核備註`
- 管理平台固定使用繁體中文，入口與子路徑統一收斂在 `/portal...`，不納入 i18n 範圍
- 共用 alert 元件已支援 i18n；若頁面本身未接入 i18n，alert 文案預設使用 `zh-TW`
- 首頁與管理平台共用 `/assets/theme.css` 主題 token，並依 `prefers-color-scheme` 切換日夜模式
- 所有 HTML 頁面都載入共用 favicon 與標題格式，`/portal/dashboard` 會同步 iframe 內容頁 title
- 管理平台歡迎頁會先回傳可立即顯示的 HTML；最近一期完訓證明與營業稅繳稅證明活動統計以 `--` 作為不改變字體高度的暫存值，再由前端呼叫 `GET /api/v1/admin/dashboard/welcome-metrics` 非同步補上資料，避免 Cosmos DB 查詢阻塞首屏；統計標題下方會顯示資料來源活動，若兩種文件類型來源不同則分別列出
- 首頁只保留 `twitter:card`，其餘社群分享資訊以 Open Graph metadata 為主
- locale JSON 字典檔集中於 `src/shared/locales/`，並由測試驗證結構一致性

## 技術基線

- Python `3.13`
- Azure Functions `v4`
- Azure Functions Core Tools `v4`

## 主要入口路由

| Method | Path | 說明 | Content-Type |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾填寫基本資料、選擇文件類型並進入文件申請流程 | `text/html; charset=utf-8` |
| `GET` | `/api/v1/events` | 公開首頁可申請活動清單 | `application/json` |
| `POST` | `/api/v1/document-lookup` | 公開首頁文件查詢 | `application/json` |
| `GET` | `/portal` | 管理平台登入入口 | `text/html; charset=utf-8` |
| `GET` | `/api/v1/admin/dashboard/welcome-metrics` | 管理平台歡迎頁最近一期活動統計 | `application/json` |
| `GET` | `/api/v1/admin/volunteer-service-certs` | 查詢單一活動的志工服務證明清單 | `application/json` |
| `PUT` | `/api/v1/admin/volunteer-service-certs/{certid}` | 更新志工服務證明管理欄位 | `application/json` |
| `POST` | `/api/v1/admin/volunteer-service-certs/transfers` | 從完訓證明轉移建立志工服務證明資料 | `application/json` |
| `GET` | `/assets/{assetName}` | 目前頁面所需的靜態樣式、互動腳本與品牌素材；頁面會以 `?v=<content-hash>` 載入版本化資產 | 依資產而定 |
| `GET` | `/verify/{certId}` | QRCode 入口的公開完訓證明驗證頁面 | `text/html; charset=utf-8` |

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

本機開發若只需要檢視管理平台 UI，建議使用 bypass。若現階段需要在 localhost 端到端驗證 Google 登入與群組授權，才暫時設定與 Azure 相同命名的 portal Google OAuth app settings：

```json
{
  "PORTAL_GOOGLE_CLIENT_ID": "<local-google-client-id>",
  "PORTAL_GOOGLE_CLIENT_SECRET": "<local-google-client-secret>",
  "PORTAL_GOOGLE_REDIRECT_URI": "http://localhost:7075/portal/auth/google/callback",
  "PORTAL_GOOGLE_ALLOWED_GROUP_KEYS": "<allowed-group-name-1>,<allowed-group-name-2>"
}
```

`PORTAL_GOOGLE_ALLOWED_GROUP_KEYS` 應使用逗號分隔的 allowlist；若值未包含 `@`，程式會自動補成目前登入使用者所在網域的完整群組地址。若你要指定其他完整 key，也可直接填帶 `@` 的值。

Google Group 授權依賴 OAuth client 所屬 Google Cloud project 的 Cloud Identity API。若要直接驗證 Google 登入，請先依 [docs/portal-authentication.md](docs/portal-authentication.md) 啟用 Cloud Identity API，並確認目標群組允許組織內使用者查看群組與成員。本機 OAuth 設定只作為現階段開發驗證用途，不是長期本機開發基線。

若只想快速查看管理平台 UI、不經過真正的 Google OAuth，可暫時開啟：

```json
{
  "PORTAL_AUTH_BYPASS_ENABLED": "true"
}
```

其中 `PORTAL_GOOGLE_CLIENT_*` 與 `PORTAL_GOOGLE_REDIRECT_URI` 代表 OAuth client 設定，`PORTAL_GOOGLE_ALLOWED_GROUP_KEYS` 代表群組授權設定。只有 bypass 設定只限本機開發，不得部署到正式環境。

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

其中 `tests/shared/test_i18n_catalog.py` 會獨立檢查所有 locale JSON 檔是否與 `SUPPORTED_LOCALES` 一致、結構完全對齊，且可被 i18n catalog 載入；`tests/shared/test_page_alerts.py` 則會驗證 shared alert 的預設 `zh-TW` fallback 與 i18n 文案切換。

## 注意事項

- `local.settings.json.example` 是可提交的模板；Azure 資源相關欄位預設留空，需由開發者自行填入。實際使用的 `local.settings.json` 仍維持忽略，不進 git。
- `local.settings.json` 內已設定 `AzureWebJobsDisableHomepage=true`，避免根目錄顯示 Azure Functions 預設首頁。
- 目前未接 Azurite 或實體 Storage Account，因此本機啟動時可能看到 `AzureWebJobsStorage` 的 unhealthy 訊息；在 `--skip-azure-storage-check` 下，這不影響目前首頁、靜態資產路由與公開驗證頁面。
- HTML 頁面會使用內容 hash 產生版本化靜態資產 URL，例如 `/assets/home.css?v=<content-hash>`。版本相符的資產回應 `Cache-Control: public, max-age=31536000, immutable` 與 `ETag`；未帶版本或版本不符的舊資產 URL 仍回 `Cache-Control: no-store`，避免部署切換期間把未版本化內容長期快取。更新資產內容後 hash 會改變，因此新的 HTML 會引用新的 URL。
- `COSMOS_ENDPOINT`、`COSMOS_DATABASE_NAME`、`COSMOS_EVENTS_CONTAINER`、`COSMOS_COMPLETION_CERTS_CONTAINER`、`COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER`、`COSMOS_VOLUNTEER_SERVICE_CERTS_CONTAINER`、`COSMOS_TAX_RECEIPTS_CONTAINER` 與 `COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER` 是 Cosmos DB 連線設定；目前 IaC 建立 serverless account、database、活動管理用的 `events` container、完訓證明用的 `completionCerts` 與 `completionCertRequests` containers、志工服務證明用的 `volunteerServiceCerts` container、營業稅繳稅證明用的 `taxReceipts` container，以及公開查詢限制用的 `publicLookupAttempts` container。
- `BLOB_DOCUMENT_ASSETS_CONTAINER`、`BLOB_ISSUED_CERT_CONTAINER` 與 `BLOB_TAX_RECEIPTS_CONTAINER` 是 Blob Storage container 設定；目前 Azure 環境使用 `document-assets`、`issued-certs` 與 `tax-receipts`。完訓證明 PDF 底圖模板跟隨 git 版控，固定印章圖預設讀取 `document-assets/shared/organization-seal.png`，可用 `CERTIFICATE_ORGANIZATION_SEAL_BLOB_NAME` 覆寫；完訓證明預覽 PNG 從 `document-assets/completion-cert/previews/png/{locale}-{nameDisplay}-{org|no-org}.png` 讀取，志工服務證明預覽 PNG 從 `document-assets/volunteer-service-cert/previews/png/{locale}-{nameDisplay}-{org|no-org}.png` 讀取；預覽 PDF 備份分別存放於 `document-assets/completion-cert/previews/pdf/{locale}-{nameDisplay}-{org|no-org}.pdf` 與 `document-assets/volunteer-service-cert/previews/pdf/{locale}-{nameDisplay}-{org|no-org}.pdf` 並使用 Archive tier；產生後 PDF 會寫入 `issued-certs/completionCert/{eventId}/{certId}.pdf` 並指定為 Cool tier；營業稅繳稅證明原始檔會寫入 `tax-receipts`。若執行環境沒有 `AzureWebJobsStorage__accountName`，可用 `BLOB_STORAGE_ACCOUNT_NAME` 指定 Blob Storage account。
- 完訓證明 PDF 動態欄位若要跨平台穩定顯示，英文與 ASCII 字元固定使用 PDF 標準 Helvetica 系列字體，中文等非 ASCII 字元應提供可嵌入的 TrueType/TTC 繁中文字體。本機可自行將 regular 與 bold 字體檔放入 `src/shared/pdf_fonts/`，`.gitignore` 會避免誤提交。正式部署由 GitHub Actions 從 private `document-assets` Blob container 的共用字體素材路徑下載字體後放進部署包；若字體由其他路徑提供，需同時設定 `COMPLETION_CERTIFICATE_REGULAR_FONT_PATH` 與 `COMPLETION_CERTIFICATE_BOLD_FONT_PATH`。正式環境缺少可嵌入字體時會拒絕產生 PDF；僅開發時可設定 `COMPLETION_CERTIFICATE_ALLOW_UNEMBEDDED_FONT_FALLBACK=true` 明確允許退回 CID/platform 字體。
- 管理平台入口現已統一使用 `/portal`，避免與 Azure Functions runtime 內建保留的 `/admin` 路徑衝突。
- `/portal` 正式環境目前應明確設定 `PORTAL_GOOGLE_CLIENT_ID`、`PORTAL_GOOGLE_CLIENT_SECRET`、`PORTAL_GOOGLE_REDIRECT_URI` 與 `PORTAL_GOOGLE_ALLOWED_GROUP_KEYS`；建議以 Azure CLI 或 Key Vault reference 寫入 app settings，詳細流程請參考 [docs/portal-authentication.md](docs/portal-authentication.md)。
- 會異動資料的管理 API 會檢查同源請求與 CSRF token；可選擇設定 `PORTAL_CSRF_SECRET` 作為 CSRF 簽章密鑰，未設定時會優先沿用 `PORTAL_GOOGLE_CLIENT_SECRET`。
- 目前活動管理已串接 Cosmos DB 的新增、查詢與修改；完訓證明頁已串接活動篩選、CSV 匯入、清單查詢、單筆資料修改，以及將尚未發行完訓證明轉移建立獨立志工服務證明資料；志工服務證明頁已串接活動篩選與真實資料清單查詢。修改審核頁已串接首頁完訓證明修改申請查詢與審核，並可切換列出已完成審核的通過、駁回、轉移與因用戶發證而取消案例；待審核清單顯示申請時間，已完成清單顯示審核時間與狀態，審核視窗會顯示活動名稱，且查看已完成審核結果時會以唯讀文字顯示申請時間。首頁完訓證明申請會依使用者選定顯示方式合成 PDF、以 Cool tier 上傳至 `issued-certs`，並在已發證後從既有 blob 重新下載；若用戶在修改審核完成前完成發證，系統會將該筆 pending 修改申請改為 `cancelledByIssue` 並保留稽核紀錄。營業稅繳稅證明已串接管理端新增、拖曳上傳、清單、修改、下載與刪除流程，metadata 寫入 `taxReceipts`，原始檔寫入 `tax-receipts`；新增送出等待後端回應期間，表格會以瀏覽器端新增中資料列顯示進度，成功後替換為正式資料列，失敗則移除。編輯既有營業稅繳稅證明時活動與統編會鎖定，若未變更金額、產製時間或檔案就取消，不會提示尚未存檔。營業稅繳稅證明下載不是管理端專屬能力，目前檔案下載已使用共用 `POST /api/v1/tax-receipts/download` 端點直接串流回單檔或 ZIP bytes，不暴露可分享的下載 URL；管理端以 session 與 CSRF 授權，首頁公開查詢成功後則以 POST body 內的 `downloadTicket` 授權，且無效首頁下載請求會與公開查詢共用 `publicLookupAttempts` 鎖定規則。

## Azure 部署

目前已建立以 GitHub Actions + OIDC 部署 Azure Functions Flex Consumption 的基線檔案：

- [infra/bicep/main.bicep](infra/bicep/main.bicep)
- [.github/workflows/deploy-function-app.yml](.github/workflows/deploy-function-app.yml)
- [docs/deployment-github-actions.md](docs/deployment-github-actions.md)
- [docs/portal-authentication.md](docs/portal-authentication.md)

目前部署基線已固定，但實際 Azure 設定值不提交到 git。`infra/bicep/` 負責定義 Azure 資源，Azure CLI 負責套用這些定義，GitHub Actions 則負責既有 Function App 的程式碼部署。完整流程請參考 [docs/deployment-github-actions.md](docs/deployment-github-actions.md)。
