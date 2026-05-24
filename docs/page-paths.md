# 頁面路徑定義

本文件作為目前瀏覽器頁面路徑與畫面行為的主文件。

## 目前保留頁面

| Method | Path | 說明 | 輸出格式 |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾選擇活動、文件類型並依文件類型填寫申請資料 | `text/html` |
| `GET` | `/portal` | 管理平台登入入口 | `text/html` |
| `GET` | `/portal/dashboard` | 管理者登入後的內部工作區頁面 | `text/html` |
| `GET` | `/portal/dashboard/welcome` | dashboard iframe 預設載入的歡迎頁 | `text/html` |
| `GET` | `/portal/dashboard/completion-certs` | dashboard iframe 的完訓證明頁 | `text/html` |
| `GET` | `/portal/dashboard/completion-reviews` | dashboard iframe 的完訓證明修改審核頁 | `text/html` |
| `GET` | `/portal/dashboard/tax-receipts` | dashboard iframe 的營業稅繳稅證明頁 | `text/html` |
| `GET` | `/portal/dashboard/events` | dashboard iframe 的活動管理頁 | `text/html` |
| `GET` | `/api/v1/events` | 公開首頁可申請活動清單 | `application/json` |
| `POST` | `/api/v1/document-lookup` | 公開首頁文件查詢 | `application/json` |
| `POST` | `/api/v1/completion-cert-change-requests` | 公開首頁完訓證明修改申請 | `application/json` |
| `GET` | `/api/v1/admin/events` | 查詢活動管理資料 | `application/json` |
| `POST` | `/api/v1/admin/events` | 建立活動管理資料 | `application/json` |
| `PUT` | `/api/v1/admin/events/{eventId}` | 更新單筆活動管理資料 | `application/json` |
| `GET` | `/api/v1/admin/completion-certs` | 查詢單一活動的完訓證明清單 | `application/json` |
| `POST` | `/api/v1/admin/completion-certs/import` | 匯入單一活動的 KKTIX 完訓證明 CSV | `application/json` |
| `PUT` | `/api/v1/admin/completion-certs/{certid}` | 修改單筆完訓證明資料 | `application/json` |
| `GET` | `/api/v1/admin/completion-cert-change-requests` | 查詢完訓證明修改申請 | `application/json` |
| `PUT` | `/api/v1/admin/completion-cert-change-requests/{requestid}` | 審核完訓證明修改申請 | `application/json` |
| `GET` | `/api/v1/admin/tax-receipts` | 查詢單一活動的營業稅繳稅證明清單 | `application/json` |
| `POST` | `/api/v1/admin/tax-receipts` | 新增單筆營業稅繳稅證明 | `application/json` |
| `PUT` | `/api/v1/admin/tax-receipts/{receiptid}` | 修改單筆營業稅繳稅證明 | `application/json` |
| `DELETE` | `/api/v1/admin/tax-receipts/{receiptid}` | 刪除單筆營業稅繳稅證明 | `application/json` |
| `POST` | `/api/v1/tax-receipts/download` | 串流下載單筆或多筆營業稅繳稅證明檔案 | `application/pdf`、`image/png`、`image/jpeg` 或 `application/zip` |
| `GET` | `/verify/{certId}` | QRCode 入口的公開完訓證明驗證頁面 | `text/html` |

## 內部導向端點

下列路徑屬於登入流程或狀態切換用途，不視為一般瀏覽導覽頁面，也不應和主要頁面案例混在一起討論。

| Method | Path | 說明 | 輸出格式 |
| --- | --- | --- | --- |
| `GET` | `/portal/auth/google/login` | 管理平台 Google 登入導向端點 | `302 redirect` |
| `GET` | `/portal/auth/google/callback` | 管理平台 Google callback 端點 | `302 redirect` |
| `GET` | `/portal/auth/logout` | 管理平台登出端點 | `302 redirect` |

## 共用規則

### 呈現方式

目前首頁、公開驗證頁與管理平台都先以 HTML 頁面呈現。管理平台目前已接入 Google Workspace SSO、Google Group 授權檢查與 session cookie；活動管理、首頁公開活動清單、完訓證明 CSV 匯入與營業稅繳稅證明新增流程已串接 Cosmos DB。

- 首頁 HTML 不同步查詢 Cosmos DB；頁面先載入後由前端呼叫 `GET /api/v1/events`，再依狀態為 `open` 的活動顯示活動清單。管理平台的活動管理、完訓證明清單與營業稅繳稅證明清單已串接 Cosmos DB
- 公開驗證頁面為 QRCode 掃描後的公開入口，會以 QRCode 內的驗證 token 查詢已發證的完訓證明紀錄，並只顯示驗證所需的最低限度資料
- 活動管理已提供 Cosmos DB 的活動新增、查詢與修改；完訓證明 CSV 由後端解析、驗證並寫入 Cosmos DB；營業稅繳稅證明由後端驗證 metadata、將檔案寫入 Blob Storage，並將權威 metadata 寫入 Cosmos DB
- 完訓證明頁目前已有後端 CSV 匯入、活動篩選、清單載入與單筆資料修改流程
- 完訓證明 PDF 合成邏輯已建立於 `src/shared/completion_certificate_pdf.py`，模板檔跟隨 git 版控，單位印章圖預設位於 Azure Storage `document-assets/completion-cert/organization-seal.png`；跨平台嵌入字體由部署 workflow 從 private `document-assets/completion-cert/fonts/` 下載後放進 Function App 部署包；首頁確認後會發證、以 Cool tier 上傳 PDF 至 `issued-certs`，已發證資料再次查詢時會下載既有 PDF
- 營業稅繳稅證明頁目前支援單筆 PDF、PNG 或 JPG/JPEG 新增、拖曳上傳、清單讀取、修改、下載與刪除；目前不支援 WebP
- 首頁完訓證明查詢成功且 `certStatus` 為 `notIssued`、`changeRequested` 或 `issued` 時，會顯示「選擇證明顯示方式」區塊；`notIssued` 時「提出修改申請」會切換到首頁同卡片內的修改申請流程，送出後會寫入 Cosmos DB `completionCertRequests` 並將對應完訓證明狀態改為 `changeRequested`；同一張完訓證明已有 `approved` 或 `rejected` 修改申請時，公開 API 會拒絕再次提出，首頁並顯示已通過或已駁回的審核結果；`changeRequested` 時不再顯示「提出修改申請」，改顯示修改申請處理中提示；`issued` 時再次按下產生按鈕會下載既有 PDF，不重新合成

### 表單輸入規則

- 首頁依文件類型顯示的申請資料欄位、管理平台的活動名稱欄位，以及營業稅繳稅證明的統編、金額、產製時間欄位不是登入憑證欄位，應在初始 HTML 標記為不使用瀏覽器自動完成與常見密碼管理器 autofill
- 目前採用 `autocomplete="off"`，並搭配常見密碼管理器的忽略屬性：`data-1p-ignore`、`data-op-ignore`、`data-lpignore`、`data-bwignore`、`data-protonpass-ignore` 與 `data-form-type="other"`
- 不以 CSS 隱藏密碼管理器注入的 DOM 作為基線做法；若日後新增同類型非憑證文字輸入欄位，應沿用同一組 HTML 屬性
- 管理端新增原生 checkbox 時應使用 `form-checkbox-option` 共用樣式，讓夜間模式沿用固定的 checkbox color scheme 與 accent color；特定情境可再疊加語意 class，例如 `document-type-option` 或 `document-upload-continue-option`
- 若 checkbox 是內嵌於動作列的輔助選項，例如繳稅證明上傳視窗的連續上傳選項，應保留 `form-checkbox-option` 的 checkbox 色彩規則，但可移除外框、背景與卡片式留白，且文字不可被拖曳選取
- 管理端日期時間輸入應使用 `form-datetime-input` 共用樣式與 24 小時制文字格式 `yyyy / MM / dd HH:mm`，避免原生日期輸入在夜間模式落回黑底；未填寫時 placeholder 使用 `---- / -- / -- --:--`
- 共用日期時間選擇器預設不顯示秒數；首頁營業稅繳稅證明的 `產製時間` 會以 `includeSeconds` 模式顯示秒數，格式為 `yyyy / MM / dd HH:mm:ss`，placeholder 使用 `---- / -- / -- --:--:--`。管理平台建立活動的日期選擇器不得因首頁需求而顯示秒數

### 公開首頁 API 規則

- 首頁使用 `GET /api/v1/events` 非同步讀取公開活動清單，避免初次進入首頁時被 Cosmos DB client 初始化或查詢延遲阻塞
- 此 API 為公開唯讀端點，不要求 API Key、管理者 session、同源請求或 CSRF token
- 第三方若得知此 API path 並直接呼叫，可以接受；因此回應必須維持最小揭露
- 回應包含狀態為 `open` 的活動；即使活動目前沒有可申請文件類型，也應回傳該活動並以空陣列表示，讓首頁可告知使用者有活動但尚無可申請文件
- 回應不得包含管理端稽核欄位、管理者識別、上架狀態以外的內部狀態，或不必要的個人資料

### `GET /api/v1/events`

- 查詢 Cosmos DB `events` container 中公開顯示的活動清單
- 不要求 API Key、管理者 session、同源請求或 CSRF token
- 只回傳狀態為 `open` 的活動，並依 `updatedAt` 由新到舊排序
- `documentTypes` 可為空陣列；首頁會顯示活動，並在文件類型欄位顯示 `尚無可申請文件`
- 後端只會回傳支援的文件類型代碼，目前為 `completionCert` 與 `taxReceipt`
- Response JSON 範例：

```json
{
  "events": [
    {
      "id": "evt_550e8400-e29b-41d4-a716-446655440000",
      "name": "iPlayground 2026",
      "documentTypes": [
        "completionCert",
        "taxReceipt"
      ]
    },
    {
      "id": "evt_9fdd26f7-1a37-4e59-bb30-6ac2fe0a22a8",
      "name": "iPlayground 2027",
      "documentTypes": []
    }
  ]
}
```

### `POST /api/v1/document-lookup`

- 首頁按下 `查詢文件` 時呼叫，用於查詢目前選取活動與文件類型下是否有符合條件的文件。
- 查詢送出後，首頁會顯示覆蓋整個 window viewport 的黑色半透明 loading 遮罩；遮罩中央以純白區塊包住 loading 指示與查詢中文字，並阻擋語系切換、表單操作與頁面捲動，直到查詢完成。
- 此 API 為公開查詢端點，不要求 API Key、管理者 session、同源請求或 CSRF token。
- 查不到文件時只回覆通用錯誤，不指出哪個欄位不符，也不提示剩餘嘗試次數。
- 若完訓證明活動存在、狀態為 `open`、支援 `completionCert`，但 `completionCertDownloadStartsAt` 尚未到達，回覆 `403` 與 `document_not_available_yet`；此情境不查詢完訓證明資料。
- IP 限制只使用 `X-Forwarded-For` 的第一個值；正式 Azure Functions 環境預期由 Azure 前端提供此 header，本機 `func start` 直連不會自動產生。若第一個值包含來源 port，例如 `198.51.100.25:54321` 或 `[2001:db8::25]:54321`，後端會先移除 port 再寫入 `publicLookupAttempts`。
- 若請求沒有 `X-Forwarded-For`，API 仍會查詢文件，但不讀寫 `publicLookupAttempts`，避免將所有無來源 IP 的請求寫成同一筆 `unknown` 紀錄。
- 同一 IP 在 24 小時內連續查詢失敗 5 次後封鎖查詢 24 小時；封鎖時間從開始封鎖時計算。
- 同一 IP 在 24 小時內查詢尚未開放的完訓證明 10 次後封鎖查詢 12 小時；此計數與一般查不到文件的失敗計數分開記錄。
- 封鎖期間回覆 `429` 與通用封鎖訊息，訊息不得提到 IP；若後端可取得封鎖到期時間，滿 1 小時以上以小時計算並無條件進位，不足 1 小時以分鐘計算並無條件進位，不足 1 分鐘顯示 1 分鐘，且不查詢文件資料。
- 查詢 IP 是否被封鎖與寫入失敗計次時，Cosmos DB 最多等待 5 秒；若提前回應就立即使用結果，若逾時則不得讓首頁無限卡住。
- 後端可用 Functions worker 本機記憶體快取已封鎖 IP 的 attempt id，用於封鎖期間快速短路 Cosmos DB；此快取只能作為額外封鎖捷徑，不能取代 Cosmos DB 的權威紀錄，且本機快取期限不得超過 1 小時。
- 首頁可用 `localStorage` 快取「已被封鎖」狀態與伺服器回傳的封鎖訊息，以減少重整後的等待感並保留 12 小時或 24 小時封鎖文案；此快取只作為使用者體驗提示，不得作為後端安全判斷依據，期限不得超過 1 小時，且必須在到期、格式不合法或查詢成功時清除，避免永久性上鎖。
- `taxReceipt` 公開查詢使用活動、統編與產製時間核對。若該活動中同一統編至少有一筆收據的 `generatedAt` 與查詢值完全相同，API 會回傳該活動與該統編相同的所有收據 metadata，依 `generatedAt` 由早到晚排序，供首頁列出；回應不包含 `sourceBlobName` 或下載 URL。
- 營業稅繳稅證明的下載能力不是管理端專屬，管理端與首頁查詢成功後都應以 `POST /api/v1/tax-receipts/download` 取得單檔或 ZIP bytes，再由前端以 browser object URL 觸發下載，不回傳可分享的下載 URL。管理端下載以 session 與 CSRF 授權；首頁下載由公開查詢成功後取得的 `downloadTicket` 授權，並在 POST body 中送回，不放在 URL。首頁會將收據列為可勾選清單，預設只勾選查詢時命中的產製時間那一筆，至少勾選一筆才可下載；勾選多筆時下載 ZIP，勾選單筆時下載原始 PDF 或圖檔。首頁收據下載若發生無效 payload 或無效下載資格，應與公開查詢失敗共用同一套 IP 鎖定規則：同一 IP 在 24 小時內連續失敗 5 次後封鎖 24 小時；封鎖期間應回覆 `429` 與 `lookup_blocked`，且不得讀取收據 metadata 或 Blob。
- 完訓證明查詢成功時，回應會包含 `badgeName`、`name`、`organization`、`certStatus` 與 `canRequestChanges`，供首頁決定是否顯示「選擇證明顯示方式」及修改申請狀態提示。
- `certStatus` 為 `notIssued`、`changeRequested` 或 `issued` 時，首頁會顯示「選擇證明顯示方式」。`issued` 進入下載模式，姓名與公司顯示選項會鎖定，說明文字會合併提示「一旦確認後，將無法更改」，不顯示證書預覽區塊，按鈕文案改為「下載證書」並下載既有 PDF；公開下載回應的檔名固定為 `certificate.pdf`，不包含報名序號、KKTIX ID 或其他個人資料。
- 「選擇證明顯示方式」區塊會依實際 `name` 與 `badgeName` 產生姓名顯示選項：`姓名`、`Badge Name`、`姓名 (Badge Name)`；若其中一個值為空，或兩者相同，只顯示單一有效選項。
- 若查詢結果有 `organization`，首頁會顯示是否顯示公司名的 checkbox。
- 顯示「選擇證明顯示方式」時，首頁會隱藏「查詢文件」按鈕，並鎖定活動、文件類型、報名序號與 email，避免使用者在確認顯示方式時修改查詢條件。
- 「返回查詢」會回到查詢表單並解除上述鎖定；`notIssued` 時「提出修改申請」會使用同一張首頁卡片切換到修改申請 view state，顯示本次查詢的活動、報名序號與 email，並要求使用者填寫需要修改的內容。送出時會呼叫 `POST /api/v1/completion-cert-change-requests`，後端重新以活動、報名序號與 email 查詢權威完訓證明資料；若同一張證明尚未有已完成審核的修改申請，會寫入 `completionCertRequests` 並將 `completionCerts.certStatus` 改為 `changeRequested`。送出成功後，修改申請 textarea 與送出按鈕會保持停用。
- `changeRequested` 時「選擇證明顯示方式」不顯示「提出修改申請」，並顯示「修改申請正在處理中，管理者確認後會再處理發證。若現在確認產生證書，將視為放棄本次修改申請。」提示。
- 若同一張完訓證明已有 `approved` 或 `rejected` 修改申請，首頁查詢回應會附上 `changeRequestReview.status`、`changeRequestReview.reviewedAt` 與 `changeRequestReview.reviewNote`，並在「選擇證明顯示方式」顯示「修改申請已通過」或「修改申請已駁回」提示；若 `reviewNote` 有值，會在提示第二行顯示 `審核備註：...`。

Request JSON 範例：

```json
{
  "documentType": "completionCert",
  "eventId": "evt_550e8400-e29b-41d4-a716-446655440000",
  "registrationNumber": "100",
  "email": "attendee@example.com"
}
```

營業稅繳稅證明查詢 Request JSON 範例：

```json
{
  "documentType": "taxReceipt",
  "eventId": "evt_550e8400-e29b-41d4-a716-446655440000",
  "businessTaxId": "12345678",
  "generatedAt": "2026-05-01T02:00:00Z"
}
```

營業稅繳稅證明查詢成功 Response JSON 範例：

```json
{
  "document": {
    "status": "found",
    "documentType": "taxReceipt",
    "eventId": "evt_550e8400-e29b-41d4-a716-446655440000",
    "taxId": "12345678",
    "generatedAt": "2026-05-01T02:00:00Z",
    "downloadTicket": "eyJldmVudElkIjoiZXZ0Xy4uLiJ9.signature",
    "taxReceipts": [
      {
        "id": "trec_550e8400-e29b-41d4-a716-446655440000",
        "amount": 1200,
        "contentType": "application/pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "fileSize": 4096,
        "generatedAt": "2026-05-01T02:00:00Z"
      }
    ]
  }
}
```

查詢成功且已有已駁回修改申請的 Response JSON 範例：

```json
{
  "document": {
    "status": "found",
    "documentType": "completionCert",
    "badgeName": "Ming",
    "canRequestChanges": false,
    "certStatus": "notIssued",
    "name": "王小明",
    "organization": "iPlayground",
    "changeRequestReview": {
      "status": "rejected",
      "reviewedAt": "2026-04-30T08:30:00Z",
      "reviewNote": "資料不符"
    }
  }
}
```

查不到文件的 Response JSON 範例：

```json
{
  "error": {
    "code": "document_not_found",
    "message": "查不到符合條件的文件，請確認資料後再試。"
  }
}
```

### `POST /api/v1/completion-cert-change-requests`

- 首頁在完訓證明查詢成功且使用者點選「提出修改申請」後呼叫，用於建立完訓證明資料調整申請。
- 此 API 為公開寫入端點，不要求管理者 session；但若 request 帶有 `Origin`，必須與目前網站同源，避免第三方網站直接跨站送出修改申請。
- 後端不信任前端傳入的姓名、公司名或證明狀態，只使用 `eventId`、`registrationNumber` 與 `email` 重新查詢 `completionCerts` 權威資料。
- 只有 `certStatus` 為 `notIssued` 或 `changeRequested`，且同一張證明尚未有 `approved` 或 `rejected` 修改申請的完訓證明可建立或重送修改申請；`issued`、`failed` 等狀態，或已完成審核的修改申請，會回覆 `409`。
- 申請 id 由 `completionCertId` 與 `requesterNote` 穩定產生；同一筆證明用相同備註重送會 upsert 同一筆 `completionCertRequests` 文件。
- 寫入 `completionCertRequests` 成功後，後端會把對應 `completionCerts.certStatus` 更新為 `changeRequested`。

Request JSON 範例：

```json
{
  "documentType": "completionCert",
  "eventId": "evt_550e8400-e29b-41d4-a716-446655440000",
  "registrationNumber": "100",
  "email": "attendee@example.com",
  "requesterNote": "想改成本名，或公司名需要調整。"
}
```

成功 Response JSON 範例：

```json
{
  "changeRequest": {
    "id": "ccreq_550e8400-e29b-41d4-a716-446655440000",
    "status": "pending",
    "completionCertId": "ccert_550e8400-e29b-41d4-a716-446655440000",
    "eventId": "evt_550e8400-e29b-41d4-a716-446655440000",
    "createdAt": "2026-04-30T08:00:00Z",
    "updatedAt": "2026-04-30T08:00:00Z"
  }
}
```

完訓證明尚未開放的 Response JSON 範例：

```json
{
  "error": {
    "code": "document_not_available_yet",
    "message": "完訓證明尚未開放下載，請於開放時間後再查詢。"
  }
}
```

封鎖時的 Response JSON 範例：

```json
{
  "error": {
    "code": "lookup_blocked",
    "message": "查詢失敗次數過多，已暫停查詢 24 小時。"
  }
}
```

### 語系規則

- 首頁與公開驗證頁支援 `zh-TW` 與 `en-US`
- 若存在使用者先前在首頁選擇的 `ipg_locale` cookie，公開頁面優先使用該語系
- 若不存在語系 cookie，才依瀏覽器 `Accept-Language` 決定初始語系
- 首頁 `/` 與公開驗證頁 `/verify/{certId}` 都提供語系切換器，並共用 `/assets/locale-switcher.js` 與 `/assets/theme.css` 內的 `.locale-*` 樣式
- 首頁切換語系時，由前端直接更新頁面文案，不會整頁重新整理
- 公開驗證頁切換語系時，會寫入 `ipg_locale` cookie，並由前端局部更新目前畫面的語系內容
- 管理平台固定使用繁體中文，不納入 i18n 範圍
- 共用 alert 元件支援 `zh-TW` 與 `en-US`
- 若頁面本身未接入 i18n，alert 文案預設使用 `zh-TW`

### 管理平台規則

- 入口路徑固定為 `/portal`
- 登入後內容頁使用 `/portal/...` 子路徑
- 首頁 `/` 不提供管理平台按鈕入口
- `/portal` 目前採 Google 單一登入入口，不再接受本地帳號密碼表單
- Google 登入與登出統一走 `/portal/auth/google/login`、`/portal/auth/google/callback`、`/portal/auth/logout`
- 管理平台授權採雙層邊界：OAuth client 的 `Internal` 設定先排除非組織帳號，再由 Google Group 直接成員檢查與伺服器端 session cookie 控制 portal 存取
- 登入後的文件管理平台目前位於 `/portal/dashboard`
- 文件管理平台以 iframe 載入歡迎頁、`活動管理`、`完訓證明`、`修改審核` 與 `營業稅繳稅證明` 五個獨立頁面
- 進入 `/portal/dashboard` 後，伺服器會在背景預先初始化活動管理使用的 Cosmos DB container client，降低第一次進入活動管理時才初始化 SDK 與 credential chain 的延遲
- 進入 `/portal/dashboard` 後，前端會透過 `portal-event-cache.js` 預載 `GET /api/v1/admin/events`，並將活動清單暫存在同一瀏覽器分頁的 `sessionStorage`；各 iframe 子頁進入時可先用快取渲染，再直接呼叫 `GET /api/v1/admin/events` 取得最新活動清單並回寫快取
- 左側功能清單固定依序顯示 `活動管理`、`完訓證明`、`修改審核` 與 `營業稅繳稅證明`
- 左側功能清單說明文字：`活動與文件設定`、`清單與資料上傳`、`完訓證明申請處理`、`PDF/PNG/JPG 上傳與管理`

### 主題與 head 規則

- 依使用者 `prefers-color-scheme` 自動切換日間與夜間模式
- 日間模式沿用首頁既有淺色視覺，夜間模式沿用管理平台既有深色視覺
- `/assets/theme.css` 提供首頁、公開驗證頁與管理平台共用主題 token；語系切換器樣式也集中於此檔
- 個別頁面 CSS 只負責版面與元件樣式
- 所有 HTML 頁面都載入 `/assets/favicon.png`
- 首頁 title 依語系文案輸出
- 管理平台登入頁、dashboard 與歡迎頁 title 使用 `文件管理平台 - iPlayground`
- 管理平台功能子頁 title 使用 `頁面名稱 - 文件管理平台 - iPlayground`
- `/portal/dashboard` 會在 iframe 載入後，將父頁 title 同步成目前內容頁 title
- 首頁只保留 `twitter:card`，其餘社群分享資訊以 Open Graph metadata 為主

### 管理平台命名空間

- 管理平台入口固定為 `/portal`
- 登入後頁面使用 `/portal/...` 子路徑
- 首頁 `/` 不提供管理平台按鈕入口
- 文件管理平台目前位於 `/portal/dashboard`
- dashboard 以 iframe 載入 `welcome`、`events`、`completion-certs`、`completion-reviews`、`tax-receipts` 五個獨立頁面
- 左側功能清單固定依序顯示 `活動管理`、`完訓證明`、`修改審核` 與 `營業稅繳稅證明`
- 左側功能清單說明文字：`活動與文件設定`、`清單與資料上傳`、`完訓證明申請處理`、`PDF/PNG/JPG 上傳與管理`

## 各頁面定義

### `/`

- 置中單卡式首頁版型
- 顯示 iPlayground logo 與品牌色
- logo 置中顯示
- 提供共用語系切換器，目前支援 `zh-TW` 與 `en-US`
- 活動在載入中顯示 `活動載入中`；沒有活動或只有一個活動時以靜態欄位顯示，只有多個活動可選時才使用下拉選單
- 活動清單會顯示所有狀態為 `open` 的活動；若選取的活動沒有可申請文件，文件類型欄位顯示 `尚無可申請文件`，不顯示申請資料欄位，查詢按鈕維持停用
- 文件類型在活動載入完成前隱藏；活動載入完成且有活動時，依所選活動的 `documentTypes` 顯示可申請文件
- 文件類型只有一個時以靜態欄位顯示，不顯示下拉三角；多個文件類型時使用自訂下拉元件
- 首頁文件類型顯示文字納入 i18n，表單值使用穩定文件類型代碼：`completionCert`、`taxReceipt`
- 首頁依文件類型顯示申請資料欄位：`完訓證明` 需要報名序號與 `email`；`營業稅繳稅證明` 需要統編與產製時間
- `營業稅繳稅證明` 的產製時間使用共用日期時間選擇器的秒數模式，顯示年、月、日、時、分、秒
- `營業稅繳稅證明` 的統編必須為完整 8 碼數字；查詢文件按鈕在目前可見申請資料欄位未完整填寫前維持停用
- `營業稅繳稅證明` 的產製時間秒數欄位按下 return 時，日期時間輸入會退出焦點；若統編與產製時間皆已完整，會直接送出查詢
- 查詢文件送出後使用滿版 loading 遮罩鎖住整個 window，避免等待期間切換語系或調整表單資料
- 營業稅繳稅證明查詢成功後，首頁會改顯示可下載收據 view state，並鎖住活動、文件類型、統編與產製時間；活動與統編摘要同列顯示。收據清單依產製時間由早到晚排序，列上只突出使用者需要比對的產製時間與金額，不以檔名作為主要辨識資訊
- 可下載收據清單使用表格呈現，左上角表頭提供全選 checkbox，資料列提供每筆 checkbox；預設只勾選查詢命中的那筆。表頭 checkbox 應支援未選、半選與全選狀態，半選代表目前只選取部分收據；全選控制不放在底部返回與下載操作旁，避免與提交下載行為混淆。手機版應保留足夠點擊範圍，並持續顯示 `已選取 {selected} / {total} 筆` 狀態
- 可下載收據 view state 底部提供 `返回查詢` 與 `下載收據`；按下下載後按鈕文案改為 `收據下載準備中，請稍候。`，並暫時停用下載、全選與各筆勾選，直到下載完成或失敗後還原。若因短時間連續下載被擋，錯誤訊息顯示在下載按鈕上方，文案不得揭露實際冷卻秒數
- 完訓證明查詢成功且 `certStatus` 為 `notIssued` 或 `changeRequested` 時，首頁顯示「選擇證明顯示方式」，讓使用者選擇姓名顯示方式與是否顯示公司名；準備生成模式會即時顯示對應語系與顯示選項的 PNG 預覽，並在確認按鈕旁提示確認後將無法更改
- 「選擇證明顯示方式」目前包含 `返回查詢`、`確認產生證書`，並依 `canRequestChanges` 顯示 `提出修改申請`；其中 `返回查詢` 已可回到查詢表單，`提出修改申請` 已可切換到首頁內修改申請 view state 並寫入後端修改申請資料，`確認產生證書` 會呼叫發證 API 產生並下載 PDF；`issued` 下載模式不顯示 PNG 預覽，會鎖定顯示選項，並把按鈕文案改為 `下載證書`；下載檔名固定為 `certificate.pdf`
- `changeRequested` 時，首頁會在「選擇證明顯示方式」顯示處理中提示，並說明若現在確認產生證書會視為放棄本次修改申請
- 已完成審核的修改申請會在「選擇證明顯示方式」顯示通過或駁回結果；若 `reviewNote` 有值，提示會保留換行並在第二行顯示 `審核備註：...`
- 顯示頁尾版權聲明

### `/verify/{certId}`

- 作為完訓證明 PDF 內 QRCode 掃描後的公開驗證入口
- 以 `{certId}` 作為驗證 token 查詢 `completionCerts.verificationTokenHash`，且只將 `certStatus = issued` 的紀錄視為有效
- 有效時顯示醒目的成功狀態，詳細資料列順序為驗證狀態、證明編號、活動、證明姓名、任職單位與發證時間
- 任職單位只在該證書發證時實際選擇顯示公司名，且 `certificateDisplayOrganization` 有值時才顯示
- 無效時顯示醒目的失敗狀態，仍保留證明編號、活動、證明姓名與發證時間欄位，但值顯示為 `未顯示`，且不顯示任職單位
- 服務暫時不可用時顯示醒目的不可用狀態，不顯示證明編號、活動、證明姓名、任職單位或發證時間等細節
- 頁面只顯示驗證所需的最低限度資料，不顯示驗證 token，也不顯示 email、報名序號或其他申請查詢欄位
- 發證時間後端以非 ISO 的 UTC fallback 顯示，例如 `2026 / 05 / 01 08:00 UTC`；前端 `/assets/verify.js` 會使用瀏覽器 `Intl.DateTimeFormat`、目前頁面語系與使用者裝置時區顯示本地化日期時間
- 提供共用語系切換器，切換時寫入 `ipg_locale` cookie 並局部更新目前驗證頁文案
- 提供返回首頁入口，按鈕樣式與首頁 `返回查詢` 一致並滿版顯示
- 隱私提示會附上聯絡信箱 `support@iplayground.io`

### `/portal`

- 作為管理平台登入入口
- 顯示 `文件管理平台` 標題與 `管理者登入` 小標
- 套用與首頁相同的日夜主題切換規則
- 未登入時顯示 Google 登入按鈕與 `返回首頁` 連結
- 若使用者在 Google OAuth 流程中取消授權，會返回 `/portal`
- 若使用者未完成資料授權，會顯示資料授權未完成 alert
- 若群組驗證因 Cloud Identity API 或群組可見度設定未完成而無法判斷，會顯示群組驗證未完成 alert
- 若登入帳號不是允許群組的直接成員，會顯示沒有文件管理平台權限 alert
- OAuth callback 會以一次性 flash cookie 傳遞錯誤狀態，不使用 URL query
- `/portal` 讀取這個一次性 flash cookie 後，會顯示浮動錯誤 alert，並立即清除 cookie
- 共用 alert 元件預設 6 秒後自動關閉，並支援依頁面或情境覆寫；目前 `/portal` 登入錯誤 alert 不會自動關閉
- 若缺少 Google OAuth 或 Google Group 授權設定，顯示設定未完成提示、停用中的登入按鈕與 `返回首頁` 連結
- 已登入時，伺服器端直接導向 `/portal/dashboard`
- 不提供語系切換器

### `/portal/dashboard`

- 作為文件管理平台登入後的桌面版工作區頁面
- 以電腦版作業為前提，不特別提供 dashboard 的 RWD 版面切換
- 左側保留固定導覽列
- 左側品牌區塊下方、功能清單上方顯示目前登入管理者與登出按鈕
- 右側工作區固定使用 iframe 呈現
- 點擊左上方 `文件管理平台` 品牌按鈕時，右側 iframe 載入 `/portal/dashboard/welcome`
- 點擊功能項目時，右側 iframe 會切換到對應的獨立頁面
- 父頁 title 會同步成目前 iframe 顯示頁面的 title
- `/portal/dashboard` 與其 iframe 子頁都會在伺服器端重新檢查 session cookie 與授權狀態
- 若 iframe 子頁因 session cookie 過期或失效而被伺服器重新導向 `/portal`，父層 dashboard 會偵測 iframe 實際路徑並將 top-level 視窗導回 `/portal`
- 若管理端 API 回傳 `401 unauthorized`，dashboard 與各 iframe 子頁的前端腳本會將 top-level 視窗導回 `/portal`
- 點擊 `登出` 會導向 `/portal/auth/logout`，再回到 `/portal`
- 管理端會對資料庫造成異動的 API 需要通過伺服器端 session 授權、同源 `Origin` 或 `Referer` 檢查，以及頁面注入的 CSRF token 檢查；第三方網頁即使知道 API 路徑，也不能直接操作

### `/portal/dashboard/welcome`

- 作為 dashboard 右側 iframe 預設載入的歡迎頁
- 顯示與首頁頂部一致的品牌 logo、平台標題、登入帳號歡迎訊息與文件類型統計資訊
- 歡迎頁 HTML 不同步查詢 Cosmos DB；首屏先顯示頁面與 `--` 指標，再由前端呼叫 `GET /api/v1/admin/dashboard/welcome-metrics` 補上統計資料；`--` 與最後數字使用相同字體樣式，避免載入完成時造成卡片高度變化
- 統計區使用單一 `最近一期活動資料` 標題，避免在各文件類型區段重複顯示
- `最近一期活動資料` 標題下方會顯示資料來源；若完訓證明與營業稅繳稅證明使用同一場活動，只顯示單一活動名稱，若來源不同則分別列出各文件類型對應活動
- 文件類型統計區段使用類似完訓證明頁工作區的大外框樣式包覆，內部為四格指標
- `完訓證明` 區段顯示最近一期開放完訓證明活動的 `完訓總人數`、`下載人次`、`驗證次數`、`待審核修改申請`
- 最近一期活動以活動清單中 `status = open`、含對應文件類型且 `eventStartDate` 最新的活動為準，不使用建立時間排序決定；完訓證明與營業稅繳稅證明會各自選擇最近一期對應活動
- 完訓證明統計優先讀取活動文件的 `metrics.completionCert` 預聚合資料；若活動文件缺少目前欄位，後端會以該活動的 `completionCerts` 文件重算並寫回活動文件
- `完訓總人數` 讀取 `metrics.completionCert.totalCount`，口徑為最近一期活動完訓名單總人數，包含尚未申請完訓證明的人數
- `下載人次` 讀取 `metrics.completionCert.downloadCount`；公開首頁第一次產生證書並下載時計 1 次，已產生證書再次下載時每次都加 1，同一位重複下載會重複計次
- `驗證次數` 讀取 `metrics.completionCert.verificationCount`；公開驗證頁成功驗證一次就加 1
- `待審核修改申請` 讀取 `completionCertRequests` 中 `status = pending` 的完訓證明修改申請數，口徑應與修改審核頁的待審核清單一致
- CSV 匯入、首次下載、再次下載與公開驗證流程都會更新活動文件的 `metrics.completionCert`，避免歡迎頁每次載入時掃描該活動全部完訓證明文件
- `營業稅繳稅證明` 區段顯示最近一期開放營業稅繳稅證明活動的 `收據張數`、`已查詢公司數`、`已下載次數`、`收據總金額`
- `收據張數` 為該活動 `taxReceipts` 文件數，`已下載次數` 為各收據用戶端 `downloadCount` 合計，`收據總金額` 為各收據 `amount` 合計
- 管理端 portal 下載應另外寫入 `portalDownloadCount` 與 `lastPortalDownloadAt` 作為 DB 留底，不納入歡迎頁 `已下載次數`
- `已查詢公司數` 目前尚未有公開查詢流程的權威事件來源，因此 API 回傳 `queriedCompanyCount: null`，前端維持顯示 `--`；不得以收據張數或建檔統編數替代
- `營業稅繳稅證明` 的 `收據總金額` 使用 `$` 與完整金額格式，例如 `$186,000`，不使用 `NT$` 或 `K` 縮寫

### `GET /api/v1/admin/dashboard/welcome-metrics`

- 查詢歡迎頁需要的管理端統計資料
- 只接受已登入且通過授權的管理者 session，並要求同源 `Origin` 或 `Referer`
- 回傳完訓證明與營業稅繳稅證明最近一期開放活動統計；若活動文件缺少完訓證明預聚合欄位，後端會重算該活動完訓證明文件並回寫活動文件
- Response JSON 範例：

```json
{
  "completionCertMetrics": {
    "eventName": "iPlayground 2026",
    "totalCount": 3,
    "downloadableCount": 2,
    "downloadCount": 3,
    "verificationCount": 15,
    "pendingCount": 1
  },
  "taxReceiptMetrics": {
    "eventName": "iPlayground 2026",
    "receiptCount": 24,
    "queriedCompanyCount": null,
    "downloadCount": 31,
    "totalAmount": 186000
  }
}
```

### `/portal/dashboard/completion-certs`

- 作為 dashboard 右側 iframe 的完訓證明頁
- 頁面標題不顯示額外的左上角小字
- 主畫面提供完訓證明資料的清單檢視區
- 完訓證明資料依活動 `eventId` 從 `GET /api/v1/admin/completion-certs?eventId=<eventId>` 載入
- CSV 匯入會先讀取 CSV 第一列作為表頭，讓管理者在上傳視窗配對報名序號、ID、Badge Name、姓名、公司名、Email 與票種欄位；前端會將配對結果送至 `POST /api/v1/admin/completion-certs/import`，後端依配對索引解析 CSV、過濾非白名單欄位，並寫入 Cosmos DB `completionCerts`
- CSV 匯入後的清單列預設為 `未簽到` 且 `certStatus` 為 `notIssued`；`issuedPdfBlobName`、`verificationTokenHash` 與 `issuedAt` 在會眾申請並完成產生檔案前為 `null`，`downloadCount` 與 `verificationCount` 預設為 `0`，`firstDownloadAt` 與 `lastDownloadAt` 預設為 `null`
- CSV 匯入完成後會以該活動目前所有 `completionCerts` 文件重算活動文件的 `metrics.completionCert`
- 同一活動再次匯入 CSV 時，會以穩定的 `eventId + number + kktixId` 產生文件 ID 並 upsert 到同一批 Cosmos DB 資料
- 清單欄位包含報名序號、ID、Badge Name、姓名、公司名、Email、票種、簽到狀態與操作
- 每列在操作欄提供 `下載` 與狀態相依的資料動作；`certStatus` 非 `issued` 時顯示 `修改`，`issued` 時改顯示 `撤銷`，不提供修改資料入口；`撤銷` 按鈕以紅底白字呈現，讓管理者一眼辨識為危險操作；`下載` 按鈕是否可用依 `certStatus` 判斷，只有 `issued` 可下載，不能用 `attendanceStatus` 或簽到狀態判斷
- 修改視窗可更新姓名、公司名與 Email；報名序號、KKTIX ID、Badge Name 與票種不直接修改
- 修改視窗將報名序號、ID 與票種放在同一排，且 Badge Name 與票種為唯讀顯示
- 修改成功後顯示共用 page alert 成功提示；共用 alert 預設 6 秒後自動關閉
- 清單表格標題列置中，標題與資料列皆維持單行
- 完訓證明表格使用固定欄寬避免換頁時欄寬跳動，過長內容以 `…` 截斷
- 完訓證明清單每頁最多顯示 10 筆；超過 10 筆時顯示上一頁、目前頁碼與下一頁控制
- 清單上方提供目前活動全部資料的批次設定，可設為 `已簽到` 或 `未簽到`，並逐筆呼叫 `PUT /api/v1/admin/completion-certs/{certid}` 將 `attendanceStatus` 寫回 Cosmos DB
- 完訓證明清單不提供選取列功能，批次設定一律套用至目前活動全部資料
- 批次簽到狀態更新進行中時，完訓證明表格會進入 `aria-busy` 狀態並顯示停用樣式；列內簽到開關、下載、修改、分頁與批次按鈕皆停用，避免管理者同時編輯資料
- 每列提供可雙向切換的簽到狀態開關，切換後會呼叫 `PUT /api/v1/admin/completion-certs/{certid}` 將 `attendanceStatus` 寫回 Cosmos DB；簽到狀態更新成功或失敗 alert 會在 3 秒後自動關閉。簽到狀態只代表出席紀錄，不控制下載按鈕是否可用
- 清單上方提供活動篩選欄位；沒有活動或只有一個活動時以靜態欄位顯示，只有多個活動可選時才使用下拉選單並直接套用篩選
- 活動篩選與上傳視窗活動選擇會先使用 portal 分頁內的活動清單快取渲染，再直接呼叫 `GET /api/v1/admin/events` 更新畫面與快取；快取只作為先顯示用途，不作為權威資料來源
- 標題列右上方提供 `上傳完訓證明資料` 按鈕
- 點擊 `上傳完訓證明資料` 後開啟中央上傳視窗
- 上傳視窗可選擇匯入資料所屬活動，預設帶入目前清單篩選活動
- 上傳視窗僅接受 CSV 檔，並使用管理平台風格的檔案選取區
- 若直接開啟完訓證明子頁，點擊上傳按鈕後會使用頁內中央上傳視窗作為 fallback

### `/portal/dashboard/completion-reviews`

- 作為 dashboard 右側 iframe 的完訓證明修改申請審核頁
- 頁面載入後呼叫 `GET /api/v1/admin/completion-cert-change-requests?status=pending` 查詢待審核申請
- 頁面提供 `待審核` 與 `已完成` 篩選；切到已完成時呼叫 `GET /api/v1/admin/completion-cert-change-requests?status=completed`，列出已通過、已駁回與因用戶發證而取消的案例
- 清單欄位包含申請時間、審核時間、狀態、報名序號、目前姓名、Email、申請內容與操作
- 待審核每列操作欄提供 `審核` 按鈕，已完成每列操作欄提供 `查看` 按鈕，開啟中央視窗
- 審核視窗顯示報名序號、KKTIX ID、票種、Email 與使用者填寫的申請內容；Email 位於申請內容上方且不可編輯
- 已完成案例的中央視窗欄位會以 disabled 樣式顯示，顯示審核狀態、審核時間、審核者與審核備註，不提供再次通過或駁回；因用戶發證而取消的狀態顯示為 `已取消`，右下角按鈕文字顯示為 `關閉`
- 管理者審核通過時可直接修改姓名與公司名，送出後呼叫 `PUT /api/v1/admin/completion-cert-change-requests/{requestid}`，將申請狀態改為 `approved`，並把對應完訓證明資料更新後恢復為 `notIssued`
- 管理者駁回時會將申請狀態改為 `rejected`，並把對應完訓證明恢復為 `notIssued`
- 若用戶在審核完成前進行發證，發證流程會將同張證明的 pending 修改申請改為 `cancelledByIssue`，寫入系統審核者與取消備註，並繼續完成發證
- 審核完成後該筆資料會從待審核清單移除，並顯示共用 page alert 成功提示

### `/portal/dashboard/tax-receipts`

- 作為 dashboard 右側 iframe 的營業稅繳稅證明頁
- 路徑名稱採用簡化的 407 收據相關語意：`tax-receipts`
- 頁面標題不顯示額外的左上角小字
- 主畫面提供營業稅繳稅證明的清單檢視區
- 清單欄位包含統編、產製時間、金額與操作；不顯示收據聯檔案名稱，若有檔案則以下載按鈕內的檔案 icon 表示
- 營業稅繳稅證明沒有停用狀態，只要完成上傳即具備下載資格；管理端清單可立即下載，首頁公開查詢成功後可透過 `downloadTicket` 下載
- 管理端每列在操作欄提供 `下載`、`修改` 與 `刪除` 按鈕
- 清單上方提供活動篩選欄位；沒有活動或只有一個活動時以靜態欄位顯示，只有多個活動可選時才使用下拉選單並直接套用篩選
- 活動篩選與上傳視窗活動選擇會先使用 portal 分頁內的活動清單快取渲染，再直接呼叫 `GET /api/v1/admin/events` 更新畫面與快取；快取只作為先顯示用途，不作為權威資料來源
- 標題列右上方提供 `新增繳稅證明` 按鈕
- 點擊 `新增繳稅證明` 後開啟中央上傳視窗
- 上傳視窗可選擇資料所屬活動，預設帶入目前清單篩選活動；修改既有資料時活動欄位會鎖定，不提供切換
- 上傳視窗逐筆輸入統編、金額、產製時間，並選擇或拖曳一個 PDF、PNG 或 JPG/JPEG 檔；修改既有資料時統編會鎖定且可不重新選檔
- 上傳視窗支援 PDF、PNG 與 JPG/JPEG 檔，並沿用完訓證明 CSV 上傳頁的管理平台風格檔案選取區與拖曳高亮狀態；目前不支援 WebP
- 修改既有繳稅證明時，取消提示只在管理者變更金額、產製時間或檔案後出現；單純開啟修改視窗後直接取消不提示
- 新增繳稅證明送出後，前端會先在目前活動表格插入一筆只存在瀏覽器端的新增中資料列，資料列以停用樣式呈現且下載、修改、刪除按鈕皆不可操作；後端成功回應後以正式資料列取代，若失敗則移除該新增中資料列並顯示錯誤
- 新增模式的上傳視窗在送出按鈕右側提供 `還有其他檔案要上傳` 勾選項，勾選後新增成功會保留視窗並清空欄位以便連續新增
- `還有其他檔案要上傳` 使用管理端共用 checkbox 色彩樣式，但不顯示外框線或背景，文字不可被滑鼠拖曳選取
- 若直接開啟營業稅繳稅證明子頁，點擊新增或修改按鈕後會使用頁內中央上傳視窗作為 fallback
- 管理端清單、上傳、修改與刪除透過 `/api/v1/admin/tax-receipts` 系列 API；下載一律使用共用 `POST /api/v1/tax-receipts/download` API。metadata 寫入 Cosmos DB `taxReceipts` container，檔案寫入 Blob Storage `tax-receipts` container

### `/portal/dashboard/events`

- 作為 dashboard 右側 iframe 的活動管理頁
- 預設顯示目前活動清單、活動狀態與各活動可申請文件類型；資料由 `GET /api/v1/admin/events` 從 Cosmos DB 非同步載入
- 活動狀態固定為 `下架`、`開放`
- 活動狀態在建立與編輯活動子畫面的右上角使用 switch，開啟代表 `開放`，關閉代表 `下架`
- 活動管理畫面不顯示也不編輯活動代碼
- 活動清單列可點擊，並可用鍵盤 Enter 或 Space 進入編輯活動子畫面
- 活動管理標題列右上方提供 `建立活動` 按鈕
- 活動清單表格直接顯示於活動管理主內容層，不另包一層清單區塊
- 活動清單表格中，活動名稱與狀態欄依內容收斂，可申請文件欄保留延展空間
- 在 dashboard iframe 內點擊 `建立活動` 後，父層 dashboard 顯示全頁中央建立活動子畫面，並讓左側功能清單暫時不可操作
- 在 dashboard iframe 內點擊活動清單列後，父層 dashboard 顯示全頁中央編輯活動子畫面，並帶入該活動資料
- 建立與編輯活動子畫面開啟時，背後頁面不可捲動，且視窗不顯示右上角關閉按鈕或左上角狀態小字
- 建立與編輯活動子畫面使用不透明白色對話框背景，避免背後畫面穿透
- 建立活動時點擊 `取消` 會提示資料尚未存檔；編輯活動時若有變更才提示資料尚未存檔
- 若直接開啟活動管理子頁，點擊 `建立活動` 後會使用頁內中央建立活動子畫面作為 fallback
- 若直接開啟活動管理子頁，點擊活動清單列後會使用頁內中央編輯活動子畫面作為 fallback
- 中央活動子畫面提供活動名稱輸入欄、右上角活動狀態 switch，以及可申請文件類型的開通勾選版型
- 可申請文件類型目前固定為 `完訓證明`、`營業稅繳稅證明`
- `完訓證明` 的文件類型代碼為 `completionCert`
- 只有勾選 `完訓證明` 時，才顯示 `完訓證明開放下載時間` 欄位；此欄位僅設定開放下載時間，不設定截止日期
- `營業稅繳稅證明` 的文件類型代碼為 `taxReceipt`，管理端說明文字為 `開放協會 407 收據聯影本供下載`
- 活動管理頁進入時會先使用 portal 分頁內的活動清單快取渲染，接著直接呼叫 `GET /api/v1/admin/events` 取得最新資料；API 成功後會更新畫面並回寫快取
- 活動清單載入會呼叫 `GET /api/v1/admin/events`，由後端驗證管理者 session 後查詢 Cosmos DB，並依 `updatedAt` 由新到舊排序
- 建立活動會呼叫 `POST /api/v1/admin/events`，由後端驗證管理者 session、同源請求與 CSRF token 後寫入 Cosmos DB
- 建立活動請求必須帶 `Idempotency-Key` header；同一管理者使用相同 key 重試時會對應同一筆活動 id，避免因網路重送建立重複資料
- 編輯活動會呼叫 `PUT /api/v1/admin/events/{eventId}`，由後端驗證管理者 session、同源請求與 CSRF token 後更新同一筆 Cosmos DB 文件，不會建立第二筆活動
- 建立與編輯活動送出後，活動清單不整表刷新；建立時先插入 disabled 暫存列，編輯時鎖定該列，待 DB 回應後以共用 alert 顯示成功或失敗並恢復列狀態
- `活動開始日期` 與 `活動結束日期` 以純日期 `yyyy-MM-dd` 寫入 API/DB；管理端 UI 顯示為 `yyyy / MM / dd`，不得轉成 UTC datetime
- `完訓總時數` 單位為小時，由管理者填入，不由系統依活動日期計算
- `完訓證明開放下載時間` 從管理端台灣時間顯示格式送出前會轉成 UTC ISO 8601，例如 `2026 / 04 / 27 20:38` 送出為 `2026-04-27T12:38:00Z`

### `GET /api/v1/admin/events`

- 查詢 Cosmos DB `events` container 中的活動清單
- 只接受已登入且通過授權的管理者 session
- 回傳資料依 `updatedAt` 由新到舊排序
- Response JSON 範例：

```json
{
  "events": [
    {
      "id": "evt_550e8400-e29b-41d4-a716-446655440000",
      "name": "iPlayground 2026",
      "status": "unlisted",
      "documentTypes": [
        "completionCert"
      ],
      "eventStartDate": "2026-07-24",
      "eventEndDate": "2026-07-25",
      "completionHours": 16,
      "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z"
    }
  ]
}
```

### `POST /api/v1/admin/events`

- 建立活動資料並寫入 Cosmos DB `events` container
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求；後端會檢查 `Origin`，若缺少則檢查 `Referer`
- 必須帶 `X-Portal-CSRF-Token` header，token 由管理平台頁面伺服器端注入
- 必須帶 `Idempotency-Key` header，避免重試時重複建立活動
- Request JSON 範例：

```json
{
  "name": "iPlayground 2026",
  "status": "unlisted",
  "documentTypes": [
    "completionCert"
  ],
  "eventStartDate": "2026-07-24",
  "eventEndDate": "2026-07-25",
  "completionHours": 16,
  "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z"
}
```

- Response JSON 範例：

```json
{
  "event": {
    "id": "evt_550e8400-e29b-41d4-a716-446655440000",
    "name": "iPlayground 2026",
    "status": "unlisted",
    "documentTypes": [
      "completionCert"
    ],
    "eventStartDate": "2026-07-24",
    "eventEndDate": "2026-07-25",
    "completionHours": 16,
    "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z",
    "createdAt": "2026-04-27T12:00:00Z",
    "createdBy": "admin@example.com",
    "updatedAt": "2026-04-27T12:00:00Z",
    "updatedBy": "admin@example.com"
  }
}
```

### `PUT /api/v1/admin/events/{eventId}`

- 更新既有活動資料並寫回 Cosmos DB `events` container
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求；後端會檢查 `Origin`，若缺少則檢查 `Referer`
- 必須帶 `X-Portal-CSRF-Token` header，token 由管理平台頁面伺服器端注入
- 不使用 `Idempotency-Key`；活動識別碼由路徑中的 `{eventId}` 指定
- Request JSON 格式與建立活動相同
- Response JSON 格式與建立活動相同，`createdAt` 與 `createdBy` 保持原值，`updatedAt` 與 `updatedBy` 會更新

### `GET /api/v1/admin/completion-certs`

- 查詢單一活動的完訓證明清單，query string 必須提供 `eventId`
- 只接受已登入且通過授權的管理者 session，並檢查同源 `Origin` 或 `Referer`
- 讀取 Cosmos DB `completionCerts` container，partition key 為 `/eventId`

Request example:

```text
GET /api/v1/admin/completion-certs?eventId=evt_20260425_ipg
```

Response example:

```json
{
  "completionCerts": [
    {
      "id": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
      "eventId": "evt_20260425_ipg",
      "number": 1,
      "kktixId": "KKTIX-001",
      "badgeName": "Ming",
      "ticketName": "一般票",
      "name": "王小明",
      "organization": "iPlayground",
      "email": "ming@example.com",
      "attendanceStatus": "notCheckedIn",
      "certStatus": "notIssued",
      "issuedPdfBlobName": null,
      "verificationTokenHash": null,
      "downloadCount": 0,
      "firstDownloadAt": null,
      "lastDownloadAt": null,
      "verificationCount": 0,
      "issuedAt": null,
      "createdAt": "2026-04-28T06:02:00Z"
    }
  ]
}
```

### `POST /api/v1/admin/completion-certs/import`

- 匯入單一活動的完訓證明 CSV。管理端會先讀取 CSV 表頭並送出欄位配對；後端依 `fieldMapping` 解析資料，且只寫入白名單欄位。欄位規則由 [cosmos-data-model.md](cosmos-data-model.md) 定義
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 不保留原始 CSV 檔案；匯入後直接 upsert 到 Cosmos DB `completionCerts`
- 匯入完成後會重算並寫回該活動文件的 `metrics.completionCert`

Request JSON example:

```json
{
  "eventId": "evt_20260425_ipg",
  "csvText": "序號,信箱,暱稱,姓名,公司,KKTIX代碼,票券\n1,ming@example.com,Ming,王小明,iPlayground,KKTIX-001,一般票",
  "fieldMapping": {
    "number": 0,
    "email": 1,
    "badgeName": 2,
    "name": 3,
    "organization": 4,
    "kktixId": 5,
    "ticketName": 6
  }
}
```

Response JSON example:

```json
{
  "completionCerts": [
    {
      "id": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
      "eventId": "evt_20260425_ipg",
      "number": 1,
      "kktixId": "KKTIX-001",
      "badgeName": "Ming",
      "ticketName": "一般票",
      "name": "王小明",
      "organization": "iPlayground",
      "email": "ming@example.com",
      "attendanceStatus": "notCheckedIn",
      "certStatus": "notIssued",
      "issuedPdfBlobName": null,
      "verificationTokenHash": null,
      "downloadCount": 0,
      "firstDownloadAt": null,
      "lastDownloadAt": null,
      "verificationCount": 0,
      "issuedAt": null,
      "createdAt": "2026-04-28T06:02:00Z"
    }
  ],
  "summary": {
    "imported": 1
  }
}
```

新匯入資料的活動預聚合會被更新為：

```json
{
  "metrics": {
    "completionCert": {
      "totalCount": 1,
      "downloadableCount": 0,
      "downloadCount": 0,
      "verificationCount": 0
    }
  }
}
```

### `PUT /api/v1/admin/completion-certs/{certid}`

- 修改單筆完訓證明清單資料
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 目前可修改欄位為 `name`、`organization`、`email`、`attendanceStatus`；已發行資料不可修改 `name`、`organization` 或 `email`
- `attendanceStatus` 只接受 `checkedIn` 或 `notCheckedIn`
- 已發行資料可送出 `{"eventId":"...","certStatus":"notIssued"}` 撤銷發行狀態；後端會將 `certStatus` 退回 `notIssued`，並清空 `issuedPdfBlobName`、`verificationTokenHash`、`issuedAt` 與證書顯示設定
- `number`、`kktixId`、`badgeName` 與 `ticketName` 不在此端點直接修改

Request JSON example:

```json
{
  "eventId": "evt_20260425_ipg",
  "name": "王小明",
  "organization": "iPlayground",
  "email": "ming@example.com",
  "attendanceStatus": "checkedIn"
}
```

Response JSON example:

```json
{
  "completionCert": {
    "id": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
    "eventId": "evt_20260425_ipg",
    "number": 1,
    "kktixId": "KKTIX-001",
    "badgeName": "Ming",
    "ticketName": "一般票",
    "name": "王小明",
    "organization": "iPlayground",
    "email": "ming@example.com",
    "attendanceStatus": "checkedIn",
    "certStatus": "notIssued",
    "issuedPdfBlobName": null,
    "verificationTokenHash": null,
    "downloadCount": 0,
    "firstDownloadAt": null,
    "lastDownloadAt": null,
    "verificationCount": 0,
    "issuedAt": null,
    "createdAt": "2026-04-28T06:02:00Z"
  }
}
```

### `GET /api/v1/admin/tax-receipts`

- 查詢單一活動的營業稅繳稅證明清單，query string 必須提供 `eventId`
- 只接受已登入且通過授權的管理者 session，並檢查同源 `Origin` 或 `Referer`
- 讀取 Cosmos DB `taxReceipts` container，partition key 為 `/eventId`
- Response 不包含下載 URL；管理平台下載時會以 `POST /api/v1/tax-receipts/download` 串流取得檔案 bytes，並以管理端 session 與 CSRF 授權，避免暴露可重用連結

Request example:

```text
GET /api/v1/admin/tax-receipts?eventId=evt_20260425_ipg
```

Response JSON example:

```json
{
  "taxReceipts": [
    {
      "id": "trec_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
      "eventId": "evt_20260425_ipg",
      "taxId": "12345678",
      "amount": 186000,
      "generatedAt": "2026-05-13T15:00:44Z",
      "sourceBlobName": "evt_20260425_ipg/trec_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001.pdf",
      "fileName": "receipt-12345678-1.pdf",
      "fileSequence": 1,
      "contentType": "application/pdf",
      "fileSize": 204800,
      "downloadCount": 0,
      "portalDownloadCount": 0,
      "lastDownloadAt": null,
      "lastPortalDownloadAt": null,
      "createdAt": "2026-05-13T15:01:00Z",
      "updatedAt": "2026-05-13T15:01:00Z"
    }
  ]
}
```

### `POST /api/v1/admin/tax-receipts`

- 新增單筆營業稅繳稅證明
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 必須帶 `Idempotency-Key` header；後端會以活動、操作者與 idempotency key 產生穩定 `trec_<uuid-v5>` 文件 ID
- `eventId` 必須指向已開放 `taxReceipt` 文件類型的活動
- `taxId` 必須為 8 碼數字；`amount` 必須是大於 0 的整數；`generatedAt` 必須是 UTC ISO 8601，格式 `yyyy-MM-dd'T'HH:mm:ss'Z'`
- `fileBase64` 會解碼後寫入 Blob Storage `tax-receipts` container，Cosmos DB 只儲存 metadata 與 blob 名稱
- `fileName` 為上傳來源檔名，只作為請求驗證；後端會重新產生 `receipt-{taxId}-{fileSequence}` 格式的下載檔名，`fileSequence` 是同一活動、同一統編下第幾份，避免同一統編多筆資料混淆
- 檔案格式只接受 PDF、PNG、JPG/JPEG，大小上限 10 MB；目前不支援 WebP
- 管理端前端會在等待此 API 回應時先顯示新增中資料列；該資料列不是 Cosmos DB 文件，也不應被視為後端流程狀態。API 成功回應後才會以 `taxReceipt` response 取代為正式資料列

Request JSON example:

```json
{
  "eventId": "evt_20260425_ipg",
  "taxId": "12345678",
  "amount": 186000,
  "generatedAt": "2026-05-13T15:00:44Z",
  "fileName": "receipt.pdf",
  "contentType": "application/pdf",
  "fileBase64": "JVBERi0xLjQK..."
}
```

Response JSON example:

```json
{
  "taxReceipt": {
    "id": "trec_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
    "eventId": "evt_20260425_ipg",
    "taxId": "12345678",
    "amount": 186000,
    "generatedAt": "2026-05-13T15:00:44Z",
    "sourceBlobName": "evt_20260425_ipg/trec_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001.pdf",
    "fileName": "receipt-12345678-1.pdf",
    "fileSequence": 1,
    "contentType": "application/pdf",
    "fileSize": 204800,
    "downloadCount": 0,
    "portalDownloadCount": 0,
    "lastDownloadAt": null,
    "lastPortalDownloadAt": null,
    "createdAt": "2026-05-13T15:01:00Z",
    "updatedAt": "2026-05-13T15:01:00Z"
  }
}
```

### `PUT /api/v1/admin/tax-receipts/{receiptid}`

- 修改單筆營業稅繳稅證明 metadata；若 request 含 `fileBase64`，會同步替換 Blob 檔案
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 編輯時不可修改 `eventId` 與 `taxId`。管理端修改視窗會鎖定活動與統編；若活動或統編需要更正，管理者必須刪除該筆繳稅證明後重新新增，以維持同一活動、同一統編下的 `fileSequence` 與下載檔名規則一致
- Request JSON 格式與新增相同；修改既有資料時可不帶 `fileBase64`、`fileName` 與 `contentType`
- Response JSON 格式與新增相同，`createdAt` 與 `createdBy` 保持原值，`updatedAt` 與 `updatedBy` 會更新

### `DELETE /api/v1/admin/tax-receipts/{receiptid}`

- 刪除單筆營業稅繳稅證明，query string 必須提供 `eventId`
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 後端會先刪除 Cosmos DB `taxReceipts` 文件，再刪除對應 Blob 檔案

Response JSON example:

```json
{
  "deleted": true
}
```

### `POST /api/v1/tax-receipts/download`

- 串流下載單筆或多筆營業稅繳稅證明檔案，request body 必須提供 `eventId` 與 `receiptIds`
- 不回傳、不要求下載 URL token；前端應使用 `fetch()` 讀取 response blob，並以 browser object URL 觸發下載
- 所有呼叫都必須通過同源 `Origin` 或 `Referer` 檢查
- 管理端呼叫時必須通過管理者 session，並帶 `X-Portal-CSRF-Token` header
- 未登入首頁呼叫時必須在 POST body 帶公開查詢成功後取得的 `downloadTicket`；ticket 由後端簽發，綁定可下載的 `receiptIds` 集合、`eventId`、下載主體 `subjectKey` 與過期時間，且不放在 URL。下載時的 `receiptIds` 可為 ticket 內可下載集合的非空子集合
- `downloadTicket` 使用專用 `TAX_RECEIPT_DOWNLOAD_TICKET_SECRET` HMAC 簽章，不得共用 Google OAuth client secret；有效時間由 `TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS` 控制，預設 `600` 秒
- 後端讀取 Cosmos DB `taxReceipts` metadata 後，依 `sourceBlobName` 從 Blob Storage `tax-receipts` 下載檔案
- Blob 讀取成功後，後端會依下載來源分開計數：用戶端下載將每筆收據的 `downloadCount` 加 1，更新 `lastDownloadAt` 與 `lastDownloadSubjectKey`；管理端 portal 下載將每筆收據的 `portalDownloadCount` 加 1 並更新 `lastPortalDownloadAt`
- 未登入首頁下載會以 `subjectKey + receiptId` 逐檔套用短時間重複下載限制；單筆若仍在冷卻期間會回覆 `429 tax_receipt_download_cooldown`，多選時若至少一筆收據未冷卻，會下載使用者選取的完整集合，只有選取收據全數冷卻時才回覆 `429 tax_receipt_download_cooldown`
- 歡迎頁的 `已下載次數` 只讀取用戶端 `downloadCount` 累計值，不包含 portal 下載
- 單筆下載會使用資料中保存的 `contentType` 與 `fileName` 作為下載格式與檔名；多筆下載會回傳 ZIP，公開檔名固定為 `tax-receipts.zip`，不得帶入 `eventId` 或其他內部識別碼
- 首頁下載營業稅繳稅證明時，會先在公開查詢流程中以最小揭露方式核對活動、統編與產製時間，再回傳 `downloadTicket` 供前端依使用者勾選的收據直接下載回應

### `GET /api/v1/admin/completion-cert-change-requests`

- 查詢完訓證明修改申請，預設查詢 `pending` 狀態；`status=completed` 會回傳 `approved`、`rejected` 與 `cancelledByIssue` 終態案例，依 `reviewedAt` 由新到舊排序
- `status` 也可指定單一狀態 `pending`、`approved`、`rejected` 或 `cancelledByIssue`
- 只接受已登入且通過授權的管理者 session，並檢查同源 `Origin` 或 `Referer`
- 讀取 Cosmos DB `completionCertRequests` container，並依申請內的 `completionCertId` 與 `eventId` 讀取對應 `completionCerts` 權威資料

Request example:

```text
GET /api/v1/admin/completion-cert-change-requests?status=pending
```

Response JSON example:

```json
{
  "changeRequests": [
    {
      "id": "ccreq_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
      "completionCertId": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
      "eventId": "evt_20260425_ipg",
      "status": "pending",
      "requesterEmail": "ming@example.com",
      "requesterNote": "公司名需要調整",
      "reviewedBy": null,
      "reviewedAt": null,
      "reviewCompletedNotifiedAt": null,
      "reviewNote": null,
      "createdAt": "2026-04-30T08:00:00Z",
      "updatedAt": "2026-04-30T08:00:00Z",
      "completionCert": {
        "id": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
        "eventId": "evt_20260425_ipg",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "舊公司",
        "email": "ming@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "changeRequested",
        "issuedPdfBlobName": null,
        "verificationTokenHash": null,
        "downloadCount": 0,
        "firstDownloadAt": null,
        "lastDownloadAt": null,
        "verificationCount": 0,
        "issuedAt": null,
        "createdAt": "2026-04-28T06:02:00Z"
      }
    }
  ]
}
```

### `PUT /api/v1/admin/completion-cert-change-requests/{requestid}`

- 審核單筆完訓證明修改申請
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- `status` 只接受 `approved` 或 `rejected`
- `approved` 可同時更新 `name`、`organization` 與 `email`；`email` 不可空白
- 審核完成後，申請文件會寫入 `reviewedBy`、`reviewedAt`、`reviewNote` 與 `updatedAt`
- 審核完成後，對應完訓證明的 `certStatus` 會恢復為 `notIssued`

Request JSON example:

```json
{
  "eventId": "evt_20260425_ipg",
  "status": "approved",
  "name": "王小明",
  "organization": "新公司",
  "email": "ming@example.com",
  "reviewNote": "已依申請調整公司名"
}
```

Response JSON example:

```json
{
  "changeRequest": {
    "id": "ccreq_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
    "completionCertId": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
    "eventId": "evt_20260425_ipg",
    "status": "approved",
    "requesterEmail": "ming@example.com",
    "requesterNote": "公司名需要調整",
    "reviewedBy": "admin@iplayground.io",
    "reviewedAt": "2026-04-30T08:30:00Z",
    "reviewCompletedNotifiedAt": null,
    "reviewNote": "已依申請調整公司名",
    "createdAt": "2026-04-30T08:00:00Z",
    "updatedAt": "2026-04-30T08:30:00Z",
    "completionCert": {
      "id": "ccert_8f2f0a3b-3e4f-5a21-9c0b-1d9f7f8a0001",
      "eventId": "evt_20260425_ipg",
      "number": 1,
      "kktixId": "KKTIX-001",
      "badgeName": "Ming",
      "ticketName": "一般票",
      "name": "王小明",
      "organization": "新公司",
      "email": "ming@example.com",
      "attendanceStatus": "checkedIn",
      "certStatus": "notIssued",
      "issuedPdfBlobName": null,
      "verificationTokenHash": null,
      "downloadCount": 0,
      "firstDownloadAt": null,
      "lastDownloadAt": null,
      "verificationCount": 0,
      "issuedAt": null,
      "createdAt": "2026-04-28T06:02:00Z"
    }
  }
}
```

## 靜態資產

目前頁面透過下列路徑載入樣式、互動與品牌素材：

HTML 頁面會以 `?v=<content-hash>` 參數引用靜態資產，例如 `/assets/theme.css?v=<content-hash>`。`content-hash` 由回應內容計算；若 CSS 內引用其他 `/assets/...` 圖示，後端會在回應時同步改寫為帶 hash 的版本化 URL。版本參數符合目前內容時，資產回應 `Cache-Control: public, max-age=31536000, immutable` 與 `ETag`，讓瀏覽器可長期快取。未帶版本參數或版本不符的資產 URL 仍回 `Cache-Control: no-store`，避免舊頁面或手動輸入的未版本化路徑被長期快取。部署更新後，只要資產內容改變，新的 HTML 會輸出新的 hash URL，瀏覽器會重新下載新資產。

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/assets/portal.css` | 管理平台登入頁與管理中心共用樣式 |
| `GET` | `/assets/portal-login.js` | 管理平台登入入口的連結互動腳本 |
| `GET` | `/assets/portal-event-cache.js` | 管理平台活動清單分頁快取與跨頁更新事件腳本 |
| `GET` | `/assets/portal-dashboard.js` | 管理中心頁面互動腳本 |
| `GET` | `/assets/portal-dashboard-welcome.js` | 管理中心歡迎頁互動腳本 |
| `GET` | `/assets/portal-dashboard-completion-certs.js` | 完訓證明頁清單與 CSV 匯入腳本 |
| `GET` | `/assets/portal-dashboard-completion-reviews.js` | 完訓證明修改審核頁互動腳本 |
| `GET` | `/assets/portal-dashboard-tax-receipts.js` | 營業稅繳稅證明頁清單與單筆 PDF、PNG 或 JPG/JPEG 新增、修改、刪除腳本 |
| `GET` | `/assets/portal-dashboard-events.js` | 活動管理頁清單列點擊、建立/編輯活動子畫面與 fallback modal 互動腳本 |
| `GET` | `/assets/page-alert.js` | 共用 alert 元件的關閉與自動消失腳本 |
| `GET` | `/assets/favicon.png` | 所有 HTML 頁面共用 favicon |
| `GET` | `/assets/home.css` | 首頁樣式 |
| `GET` | `/assets/home.js` | 首頁互動腳本 |
| `GET` | `/assets/locale-switcher.js` | 首頁與公開驗證頁共用的語系切換器互動腳本 |
| `GET` | `/assets/theme.css` | 首頁、公開驗證頁與管理平台共用的日夜主題 token、語系切換器樣式與 shared alert 樣式 |
| `GET` | `/assets/verify.css` | 公開驗證頁樣式 |
| `GET` | `/assets/verify.js` | 公開驗證頁互動腳本，包含本地化發證時間顯示 |
| `GET` | `/assets/google-g-icon.svg` | 管理平台 Google 登入按鈕使用的本地 SVG icon |
| `GET` | `/assets/language_icon.svg` | 共用語系切換器使用的本地 SVG icon |
| `GET` | `/assets/logo_b_alpha.png` | iPlayground 品牌 logo |
| `GET` | `/assets/logo_sq_b.png` | dashboard 左上角品牌方形 logo |

## 暫時不保留

目前只保留下列頁面與路徑：

- `/`
- `/portal`
- `/portal/dashboard`
- `/portal/dashboard/welcome`
- `/portal/dashboard/completion-certs`
- `/portal/dashboard/completion-reviews`
- `/portal/dashboard/tax-receipts`
- `/portal/dashboard/events`
- `/verify/{certId}`

其餘 API、管理子路由與相關實作暫時不保留。
