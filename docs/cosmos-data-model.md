# Cosmos DB 資料模型

本文件記錄 Cosmos DB for NoSQL 的資料模型與欄位約定。基礎設施建立方式請參考 [deployment-github-actions.md](deployment-github-actions.md)。

## 共用規則

- 所有時間欄位一律使用 UTC ISO 8601 字串。
- 時間格式固定為 `yyyy-MM-dd'T'HH:mm:ss'Z'`。
- 不儲存本地時區格式，例如 `+08:00`。
- 不儲存自然語言日期。
- Cosmos DB 只儲存中繼資料與流程狀態；PDF、PNG、JPG 或其他二進位檔案應存放於 Blob Storage。

Python 產生時間字串時，應使用 timezone-aware datetime：

```python
from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

## `events` container

`events` container 用於活動管理資料。

```text
container: events
partition key: /id
```

### 活動文件

活動文件只存放活動管理需要的權威設定，不使用額外的 `tenantId` 或 `type` 欄位。

必要欄位：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | string | 後端自動產生的活動穩定識別碼 |
| `name` | string | 活動顯示名稱 |
| `status` | string | 活動狀態 |
| `documentTypes` | string[] | 此活動開放申請的文件類型；可為空陣列 |
| `eventStartDate` | string | 活動開始日期，純日期，格式 `yyyy-MM-dd` |
| `eventEndDate` | string | 活動結束日期，純日期，格式 `yyyy-MM-dd` |
| `completionHours` | int | 完訓總時數，單位小時，由管理者填入，不由系統計算 |
| `completionCertDownloadStartsAt` | string \| null | 完訓證明開放下載時間，UTC ISO 8601；未開放完訓證明時為 null |
| `metrics.completionCert.downloadableCount` | int | 此活動已可下載的完訓證明數量 |
| `metrics.completionCert.downloadCount` | int | 此活動完訓證明累計下載人次；同一位重複下載會重複計次 |
| `metrics.completionCert.verificationCount` | int | 此活動完訓證明公開驗證成功次數 |
| `metrics.completionCert.pendingCount` | int | 此活動尚未發行的完訓證明數量 |
| `createdAt` | string | 建立時間，UTC ISO 8601 |
| `createdBy` | string | 建立者識別 |
| `updatedAt` | string | 最後更新時間，UTC ISO 8601 |
| `updatedBy` | string | 最後更新者識別 |

`status` 目前允許值：

```text
open
unlisted
```

`documentTypes` 目前允許值：

```text
completionCert
taxReceipt
```

`documentTypes` 可為空陣列。空陣列表示活動本身可公開顯示，但目前沒有可申請文件；公開首頁應顯示該活動，並在文件類型欄位提示尚無可申請文件，而不是隱藏活動。

`eventStartDate` 與 `eventEndDate` 是活動日曆日期，不是時間點；後端與前端都不得把它們轉成 UTC datetime。UI 可顯示為 `yyyy / MM / dd`，但 API 與 DB 權威值固定使用 `yyyy-MM-dd`。`completionHours` 單位為小時，由管理者填入，不從活動日期自動計算。

`id` 產生規則：

- 由後端建立活動時自動產生。
- 前端不得提供、編輯或顯示 `id`。
- 活動名稱不是 `id`；活動名稱可修改，但 `id` 不可變。
- 使用管理者識別與 `Idempotency-Key` 產生穩定 UUIDv5，格式為 `evt_<uuid-v5>`。
- 同一管理者使用相同 `Idempotency-Key` 重試建立活動時，會得到同一個 `id`，避免因網路重送建立重複資料。

Python 產生方式：

```python
from uuid import NAMESPACE_URL, uuid5


EVENT_IDEMPOTENCY_NAMESPACE = "io.iplayground.ipg-certificate.admin.events"


def build_event_id(idempotency_key: str, *, actor: str) -> str:
    normalized_actor = actor.strip().lower() or "unknown"
    normalized_key = idempotency_key.strip()
    namespace_value = f"{EVENT_IDEMPOTENCY_NAMESPACE}:{normalized_actor}:{normalized_key}"
    return f"evt_{uuid5(NAMESPACE_URL, namespace_value)}"
```

範例：

```json
{
  "id": "evt_550e8400-e29b-41d4-a716-446655440000",
  "name": "iPlayground 2026",
  "status": "open",
  "documentTypes": [
    "completionCert"
  ],
  "eventStartDate": "2026-07-24",
  "eventEndDate": "2026-07-25",
  "completionHours": 16,
  "completionCertDownloadStartsAt": "2026-04-25T03:30:00Z",
  "metrics": {
    "completionCert": {
      "downloadableCount": 0,
      "downloadCount": 0,
      "verificationCount": 0,
      "pendingCount": 0
    }
  },
  "createdAt": "2026-04-25T03:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-04-25T03:30:00Z",
  "updatedBy": "admin@example.com"
}
```

### 查詢模式

活動清單：

```sql
SELECT c.id, c.name, c.status, c.documentTypes,
       c.eventStartDate, c.eventEndDate, c.completionHours,
       c.completionCertDownloadStartsAt, c.metrics
FROM c
ORDER BY c.createdAt DESC
```

活動清單只投影管理端 UI 需要的欄位，並依建立時間由新到舊排序。管理端歡迎頁的 HTML 首屏不查詢 Cosmos DB；畫面先以 `--` 指標顯示，再由 `GET /api/v1/admin/dashboard/welcome-metrics` 讀取狀態為 `open`、含對應文件類型且活動開始日期最新的活動。歡迎頁標題下方會顯示統計資料來源活動；若完訓證明與營業稅繳稅證明來源不同，會分別列出各文件類型的來源活動。完訓證明統計優先使用活動文件上的 `metrics.completionCert` 預聚合資料，避免每次載入歡迎頁都掃描該活動全部完訓證明文件。

公開首頁活動清單：

```sql
SELECT c.id, c.name, c.documentTypes,
       c.eventStartDate, c.eventEndDate, c.completionHours,
       c.completionCertDownloadStartsAt
FROM c
WHERE c.status = 'open'
ORDER BY c.createdAt DESC
```

公開首頁只讀取狀態為 `open` 的活動，並只投影會眾選擇活動與文件類型所需欄位；`documentTypes` 可以是空陣列，代表首頁應顯示活動但提示尚無可申請文件。不得在公開頁面輸出管理端稽核欄位或其他不必要的個人資料。

單筆活動讀取：

```text
id = <event-id>
partition key = <event-id>
```

雖然活動清單查詢會跨 partition，但活動數量與管理端使用頻率都很低，初期接受這個取捨。單筆讀取與更新應使用 point read / replace，並以 `id` 作為 partition key。

管理端進入 `/portal/dashboard` 後，伺服器會在背景預先初始化活動管理使用的 Cosmos DB container client；同一個 Functions worker 生命週期內會重用該 client，避免第一次進入活動管理時才承擔 SDK 與 credential chain 初始化成本。

### 完訓證明預聚合 metrics

活動文件的 `metrics.completionCert` 是管理端歡迎頁的權威統計快取。欄位語意如下：

- `downloadableCount`：該活動目前已發行且有 `issuedPdfBlobName` 的完訓證明數量。
- `downloadCount`：該活動完訓證明累計下載人次。首次產生證書並下載時計 1 次；已發行證書再次下載時，每次下載都再加 1。同一位重複下載會重複計次。
- `verificationCount`：公開驗證頁成功驗證該活動完訓證明的累計次數。
- `pendingCount`：該活動 `certStatus` 不是 `issued` 的完訓證明數量。

下列流程會更新 `metrics.completionCert`：

- CSV 匯入完成後，以該活動全部 `completionCerts` 文件重算並覆寫。
- 首次產生完訓證明 PDF 並下載後，增加 `downloadableCount` 與 `downloadCount`，並減少 `pendingCount`。
- 已發行證書再次下載後，增加 `downloadCount`。
- 公開驗證頁成功驗證後，增加 `verificationCount`。

若活動文件缺少目前 metrics 欄位，後端會在下次相關流程中以 `completionCerts` 文件重算並覆寫目前欄位。既有 DB 的一次性回填方式見下方「資料回填」。

## 完訓證明 containers

證明文件目前採用下列 Cosmos DB containers：

```text
container: completionCerts
partition key: /eventId

container: completionCertRequests
partition key: /eventId

container: taxReceipts
partition key: /eventId

container: publicLookupAttempts
partition key: /id
```

`completionCerts` 是完訓證明完整清單。名稱沿用活動管理的文件類型代碼 `completionCert`。CSV 匯入資料、簽到狀態、發證狀態、下載檔案 metadata、驗證 token、下載次數與驗證次數都記錄在同一筆資料中。CSV 上傳由 Python API 同步解析與寫入；目前預期單次約數百筆資料可在可接受時間內完成，因此不設計 DB 進度狀態或進度條。CSV 匯入當下尚未產生完訓證明檔案與驗證 token，因此 `issuedPdfBlobName`、`verificationTokenHash` 與 `issuedAt` 預設為 `null`，`downloadCount` 與 `verificationCount` 預設為 `0`，`firstDownloadAt` 與 `lastDownloadAt` 預設為 `null`；等會眾申請完訓證明且系統完成產生檔案後才回填發證檔案，並記錄當次使用的顯示名稱、單位與語系。

`completionCertRequests` 只記錄會眾是否申請資料調整、申請備註、審核狀態與通知狀態。這類資料不是完訓證明權威清單本身，因此獨立存放。

目前不保留原始 CSV 檔案。完訓證明 PDF 底圖模板跟隨 git 版控，因欄位座標需要與模板版本同步；固定印章圖存放於 Blob Storage `document-assets` container，預設 blob 名稱為 `completion-cert/organization-seal.png`；首頁證明預覽 PNG 也存放於 `document-assets`，blob 名稱格式為 `completion-cert/previews/png/{locale}-{nameDisplay}-{org|no-org}.png`，預覽 PDF 備份則使用 `completion-cert/previews/pdf/{locale}-{nameDisplay}-{org|no-org}.pdf` 並設定為 Archive tier。產生後 PDF 存放於 Blob Storage `issued-certs` container，並以 Cool tier 儲存。Cosmos DB 只儲存完訓證明清單資料、狀態、顯示選項與產生後檔案的 blob 名稱，不儲存 CSV 原文、印章圖、預覽圖或 PDF 二進位。

`taxReceipts` 是營業稅繳稅證明 metadata 的權威資料來源。管理端逐筆新增時，後端會先驗證活動已開放 `taxReceipt` 文件類型、統編、整數金額、UTC 產製時間與檔案格式，再將 PDF、PNG 或 JPG/JPEG 檔案寫入 Blob Storage `tax-receipts` container，並將 metadata 寫入 Cosmos DB。Cosmos DB 不儲存檔案二進位；`sourceBlobName` 指向對應 Blob。

管理端新增時，表格可能先顯示只存在瀏覽器端的新增中資料列，用於回饋檔案正在寫入。這不是 `taxReceipts` 文件，不會寫入 Cosmos DB，也沒有獨立後端狀態；只有 `POST /api/v1/admin/tax-receipts` 成功回應後，正式 metadata 才會成為 Cosmos DB 的權威資料。

### 營業稅繳稅證明文件

`taxReceipts` 以活動作為 partition key，支援管理端依活動列出、逐筆新增、修改、下載與刪除營業稅繳稅證明。這個 container 是營業稅繳稅證明的權威 metadata；管理端歡迎頁會依最近一期開放 `taxReceipt` 活動讀取同一個 container，計算收據張數、用戶 `downloadCount` 合計與 `amount` 合計。歡迎頁的 `已查詢公司數` 需要公開查詢流程的權威事件來源，目前不得以收據張數或建檔統編數替代。首頁公開查詢會以活動、8 碼統編與產製時間核對是否存在同統編收據，命中後依 `generatedAt` 由早到晚回傳同活動同統編的所有收據公開 metadata，但不暴露 `sourceBlobName` 或下載 URL。首頁公開下載讀取同一份 metadata，並使用共用 `POST /api/v1/tax-receipts/download` 下載端點直接串流單檔或 ZIP bytes，不回傳可分享的下載 URL。未登入首頁下載時，公開查詢成功後會回傳含 `subjectKey` 的 `downloadTicket`，並在下載 POST body 中送回；ticket 不作為持久化 metadata 存入 Cosmos DB，且只授權該次查詢可下載收據集合的非空子集合。首頁下載會以 ticket 內的下載主體與單筆收據逐檔檢查短時間重複下載；多選時若至少一筆收據未冷卻，會下載使用者選取的完整集合，只有選取的收據全數冷卻時才阻擋。首頁下載若送出無效 payload 或無效 `downloadTicket`，會寫入 `publicLookupAttempts` 並套用與完訓證明公開查詢相同的 5 次失敗封鎖規則。多筆收據下載時，HTTP `Content-Disposition` 的 ZIP 檔名固定為 `tax-receipts.zip`，避免將 `eventId` 等內部識別碼放進使用者下載檔名。

必要欄位：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | string | 繳稅證明資料識別碼，格式 `trec_<uuid-v5>` |
| `eventId` | string | 活動識別碼，同時作為 partition key |
| `taxId` | string | 8 碼統一編號 |
| `amount` | int | 繳稅金額；必須為大於 0 的整數 |
| `generatedAt` | string | 產製時間，UTC ISO 8601，格式 `yyyy-MM-dd'T'HH:mm:ss'Z'` |
| `sourceBlobName` | string | `tax-receipts` container 中的 blob 名稱，格式 `{eventId}/{receiptId}.pdf`、`.png` 或 `.jpg` |
| `fileName` | string | 後端產生的下載檔名，格式 `receipt-{taxId}-{fileSequence}.{ext}`；不使用上傳原始檔名 |
| `fileSequence` | int | 同一活動、同一統編下的檔案序號，從 `1` 開始 |
| `contentType` | string | 檔案 MIME type，只接受 `application/pdf`、`image/png` 或 `image/jpeg` |
| `fileSize` | int | 檔案大小，bytes |
| `downloadCount` | int | 用戶端累計下載次數；初始為 `0`，只統計公開查詢成功後以 `downloadTicket` 下載的次數 |
| `lastDownloadAt` | string \| null | 最後一次成功準備用戶端下載檔案的 UTC ISO 8601 時間；尚未下載時可不存在或為 `null` |
| `lastDownloadSubjectKey` | string \| null | 最近一次用戶端下載主體 key；由公開查詢核對資料產生，用於同主體同收據短時間重複下載限制 |
| `portalDownloadCount` | int | 管理端 portal 累計下載次數；初始為 `0`，只作為 DB 留底，不納入歡迎頁統計 |
| `lastPortalDownloadAt` | string \| null | 最後一次成功準備管理端下載檔案的 UTC ISO 8601 時間；尚未下載時可不存在或為 `null` |
| `createdBy` | string | 建立者管理端識別 |
| `createdAt` | string | 建立時間，UTC ISO 8601 |
| `updatedBy` | string | 最後更新者管理端識別 |
| `updatedAt` | string | 最後更新時間，UTC ISO 8601 |

`fileSequence` 由後端依同一活動、同一統編既有資料計算，搭配 `fileName` 避免同一統編多筆收據使用相同下載檔名。若管理者替換收據聯檔案，系統會沿用原本的 `fileSequence`。編輯營業稅繳稅證明時不可修改 `eventId` 與 `taxId`；若活動或統編需要更正，應刪除該筆資料後重新新增。

範例：

```json
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
  "createdBy": "admin@iplayground.io",
  "createdAt": "2026-05-13T15:01:00Z",
  "updatedBy": "admin@iplayground.io",
  "updatedAt": "2026-05-13T15:01:00Z"
}
```

### 完訓證明清單文件

`completionCerts` 是完訓資格、簽到狀態與發證狀態的權威資料來源。公開驗證與證書生成不得信任使用者端傳入的宣稱內容，必須讀取這個 container。

必要欄位：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | string | 完訓證明資料識別碼，格式 `ccert_<uuid-v5>` |
| `eventId` | string | 活動識別碼，同時作為 partition key |
| `number` | int | 報名序號 |
| `kktixId` | string | KKTIX `Id` |
| `badgeName` | string | Badge 顯示名稱 |
| `ticketName` | string | 票種 |
| `name` | string | 姓名 |
| `organization` | string | 公司名或服務單位，缺少時以空字串儲存 |
| `email` | string | Email |
| `attendanceStatus` | string | 簽到狀態 |
| `certStatus` | string | 證書狀態 |
| `issuedPdfBlobName` | string \| null | `issued-certs` 中的 PDF blob 名稱，格式為 `{eventId}/{certId}.pdf`；對應 blob 應使用 Cool tier；CSV 匯入時為 null |
| `certificateDisplayName` | string \| null | 發證時實際寫入 PDF 的姓名顯示文字；發證後回填 |
| `certificateDisplayOrganization` | string \| null | 發證時實際寫入 PDF 的任職單位文字；未顯示單位時為空字串 |
| `certificateLocale` | string \| null | 發證時使用的 PDF 語系，例如 `zh-TW` 或 `en-US` |
| `verificationTokenHash` | string \| null | 公開驗證 token；發證時產生 UUID 去除 dash 的 32 字元小寫十六進位字串，並用於 PDF 左下角 QRCode URL；CSV 匯入時為 null |
| `downloadCount` | int | 此完訓證明累計下載次數；同一位重複下載會重複計次 |
| `firstDownloadAt` | string \| null | 第一次下載時間，UTC ISO 8601；尚未下載時為 null |
| `lastDownloadAt` | string \| null | 最近一次下載時間，UTC ISO 8601；尚未下載時為 null |
| `verificationCount` | int | 公開驗證端點成功驗證此完訓證明的累計次數；CSV 匯入時為 0 |
| `issuedAt` | string \| null | 發證時間，UTC ISO 8601；CSV 匯入時為 null |
| `createdAt` | string | 建立時間，UTC ISO 8601 |

公開首頁下載完訓證明時，HTTP `Content-Disposition` 的檔名固定為 `certificate.pdf`。此檔名只影響使用者下載，不影響 `issuedPdfBlobName` 儲存的 Blob 名稱。

### 資料回填

既有 DB 若仍有舊欄位 `downloadedAt` 或 `downloadedCount`，或活動文件缺少目前的 `metrics.completionCert.downloadCount`，應以一次性回填腳本轉成目前欄位並移除舊欄位，同時重算活動文件的 `metrics.completionCert`：

```bash
python3 scripts/backfill_completion_cert_metrics.py
python3 scripts/backfill_completion_cert_metrics.py --apply
```

第一行為 dry-run，只輸出預計掃描與更新數量；第二行才寫入 Cosmos DB。可用 `--event-id <event-id>` 限定單一活動。此腳本可重複執行。

`attendanceStatus` 目前允許值：

```text
notCheckedIn
checkedIn
```

管理端完訓證明頁的單筆簽到狀態開關與目前活動全部資料批次設定，皆會透過 `PUT /api/v1/admin/completion-certs/{certid}` 更新 `attendanceStatus`。批次更新期間前端會鎖定清單互動，避免同時編輯造成畫面狀態與 DB 狀態分歧。

`attendanceStatus` 僅表示出席紀錄，不代表證書已發行，也不作為管理中心下載按鈕是否可用的判斷依據。

`certStatus` 目前允許值：

```text
notIssued
issued
failed
changeRequested
```

`changeRequested` 代表會眾已送出完訓證明資料修改申請，管理者尚未完成處理。

管理中心完訓證明清單中的下載按鈕依 `certStatus` 判斷是否可用；目前只有 `issued` 可下載。`notIssued`、`failed` 與 `changeRequested` 不可下載，即使 `attendanceStatus` 為 `checkedIn` 也一樣。

公開首頁在 `notIssued` 狀態的「選擇證明顯示方式」區塊提供「提出修改申請」入口，並會切換到首頁同卡片內的修改申請 view state。送出後會建立或更新 `completionCertRequests` 文件，並把對應 `completionCerts.certStatus` 改為 `changeRequested`；若同一張完訓證明已有 `approved` 或 `rejected` 修改申請，公開 API 不允許再次提出修改申請，且首頁會在「選擇證明顯示方式」顯示已通過或已駁回的審核結果。若已完成審核的申請有 `reviewNote`，首頁會在審核結果第二行顯示 `審核備註：...`。

公開首頁查詢到 `changeRequested` 狀態時仍會進入「選擇證明顯示方式」，但不再顯示「提出修改申請」。頁面會提示修改申請正在處理中，並告知使用者若現在確認產生證書，將視為放棄本次修改申請。

完訓證明 CSV 匯入會將 CSV 第一列視為表頭。管理端會讓使用者配對下列正規化欄位，並把配對結果以 `fieldMapping` 欄位索引送給後端；後端只會寫入這些白名單欄位。若前端未提供 `fieldMapping`，後端仍會以既有 KKTIX 表頭別名自動解析，供舊流程或測試資料相容。

| 正規化欄位 | 用途 | 既有自動配對表頭 |
| --- | --- | --- |
| `number` | 報名序號 | `報名序號` |
| `kktixId` | KKTIX 或外部報名 ID | `Id` |
| `badgeName` | Badge Name | `你是誰，ID 或具有鑑識度的名稱 Name on Badge` |
| `name` | 證明姓名 | `姓名 Full Name` |
| `organization` | 公司名或服務單位 | `服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)` |
| `email` | Email | `Email` 或 `email` |
| `ticketName` | 票種 | `票種` |

CSV 必要配對欄位包含：

- `number`
- `kktixId`
- `badgeName`
- `name`
- `organization`
- `email`
- `ticketName`

`number` 必須是整數。

`name` 與 `organization` 欄位必須完成配對，但每列值可以空白；缺少值時分別以空字串儲存。

其他 CSV 欄位不得寫入完訓證明文件，除非後續文件明確擴充白名單。

CSV 匯入若有格式或欄位錯誤，API 應以機器可讀錯誤回應告知，不把 UI 進度或失敗列狀態寫入 Cosmos DB。若未來需要保留錯誤報告，可將去敏後的錯誤報告檔存入 Blob Storage，再於稽核文件中記錄其 blob 名稱。

管理端查詢活動下的完訓證明清單：

```sql
SELECT c.id, c.number, c.kktixId, c.badgeName, c.name,
       c.organization, c.email, c.ticketName, c.attendanceStatus, c.certStatus
FROM c
WHERE c.eventId = @eventId
ORDER BY c.number ASC
```

### 資料調整申請文件

`completionCertRequests` 記錄會眾是否申請完訓證明資料調整、申請備註、管理者審核結果與審核完畢通知時間。公開首頁送出修改申請時會寫入此 container；同一張完訓證明使用相同申請備註重送時，會使用穩定 id upsert 同一筆申請文件。管理端審核通過或駁回後會寫入審核欄位，並將對應 `completionCerts.certStatus` 從 `changeRequested` 恢復為 `notIssued`，讓後續發證流程可重新處理權威清單資料；同一張完訓證明已有 `approved` 或 `rejected` 申請後，不可再由公開首頁建立新的修改申請。

必要欄位：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | string | 申請識別碼，格式 `ccreq_<uuid-v5>` |
| `completionCertId` | string | 對應的完訓證明清單資料 |
| `eventId` | string | 活動識別碼，同時作為 partition key |
| `status` | string | 申請狀態 |
| `requesterEmail` | string | 申請者 email |
| `requesterNote` | string | 申請者備註 |
| `reviewedBy` | string \| null | 審核管理者 |
| `reviewedAt` | string \| null | 審核時間，UTC ISO 8601 |
| `reviewCompletedNotifiedAt` | string \| null | 審核完畢通知時間，UTC ISO 8601 |
| `reviewNote` | string \| null | 審核備註 |
| `createdAt` | string | 建立時間，UTC ISO 8601 |
| `updatedAt` | string | 最後更新時間，UTC ISO 8601 |

`status` 目前允許值：

```text
pending
approved
rejected
cancelled
```

管理端查詢活動下待審核申請：

```sql
SELECT c.id, c.completionCertId, c.status, c.requesterEmail,
       c.requesterNote, c.createdAt
FROM c
WHERE c.eventId = @eventId AND c.status = 'pending'
ORDER BY c.createdAt ASC
```

## 公開查詢限制 container

`publicLookupAttempts` 記錄公開文件查詢與首頁收據下載的連續失敗狀態，用於降低暴力嘗試。此 container 會儲存 Azure Functions 收到的 `X-Forwarded-For` 第一個 IP，並在寫入前移除常見的來源 port 格式，例如 `198.51.100.25:54321` 或 `[2001:db8::25]:54321`，供營運稽核與安全追蹤使用；`id` 使用由該 IP 穩定產生的 UUIDv5，讓後端仍可用 point read 取得單一 IP 的查詢限制狀態。若請求沒有 `X-Forwarded-For`，後端會照常處理請求，但不會建立或更新 `publicLookupAttempts` 文件，避免把本機或特殊環境的請求共同寫成 `unknown`。

```text
container: publicLookupAttempts
partition key: /id
```

必要欄位：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | string | `lookup_<uuid-v5>`；由 IP 穩定產生，同時作為 partition key |
| `ipAddress` | string | 原始 IP 位址 |
| `failureCount` | int | 目前 24 小時失敗視窗內的連續失敗次數 |
| `firstFailedAt` | string \| null | 目前失敗視窗的第一次失敗時間，UTC ISO 8601 |
| `lastFailedAt` | string \| null | 最近一次失敗時間，UTC ISO 8601 |
| `notAvailableCount` | int | 目前 24 小時內查詢尚未開放完訓證明的次數 |
| `firstNotAvailableAt` | string \| null | 目前未開放查詢視窗的第一次查詢時間，UTC ISO 8601 |
| `lastNotAvailableAt` | string \| null | 最近一次未開放查詢時間，UTC ISO 8601 |
| `blockedUntil` | string \| null | 封鎖到期時間，UTC ISO 8601；未封鎖時為 null |
| `updatedAt` | string | 最後更新時間，UTC ISO 8601 |

規則：

- IP 來源只使用 `X-Forwarded-For` 的第一個值，並移除 IPv4 `host:port` 與 bracketed IPv6 `[host]:port` 的 port；本機 `func start` 直連通常不會自動帶此 header，需由測試請求自行明確提供。
- 同一 IP 在 24 小時內連續公開查詢失敗，或首頁收據下載送出無效 payload / 無效下載資格累計 5 次後，`blockedUntil` 設為開始封鎖時間加 24 小時。
- 同一 IP 在 24 小時內查詢尚未開放的完訓證明 10 次後，`blockedUntil` 設為開始封鎖時間加 12 小時；此計數與一般查不到資料的 `failureCount` 分開記錄。
- 封鎖期間公開查詢 API 與首頁收據下載 API 直接回覆封鎖錯誤，不查詢文件 metadata 或 Blob。
- 對使用者顯示的封鎖訊息不得提到 IP；若可取得 `blockedUntil`，滿 1 小時以上以小時計算並無條件進位，不足 1 小時以分鐘計算並無條件進位，不足 1 分鐘顯示 1 分鐘。
- 公開查詢成功時，將 `failureCount` 與 `notAvailableCount` 歸零，並清除對應時間欄位與 `blockedUntil`；首頁收據下載成功時也會清除一般失敗計數與封鎖狀態。
- 對使用者顯示的失敗訊息不得指出哪個欄位錯誤，也不得提示剩餘嘗試次數。
- 此 container 只供公開查詢與首頁收據下載限制使用；公開查詢流程對此 container 的 point read 與 upsert 最多等待 5 秒，若 Cosmos DB 提前回應就立即使用結果，避免 Cosmos DB 延遲讓首頁查詢長時間卡住。
- Functions worker 可在記憶體中快取已封鎖 attempt id 與 `blockedUntil`，讓封鎖期間的後續查詢不必每次讀取 Cosmos DB；此快取不得用於放行，只能用於提早拒絕，且即使 DB 文件異常帶有更遠的 `blockedUntil`，本機快取也不得超過 1 小時。
