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
       c.completionCertDownloadStartsAt
FROM c
ORDER BY c.createdAt DESC
```

活動清單只投影管理端 UI 需要的欄位，並依建立時間由新到舊排序。

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

## 完訓證明 containers

完訓證明目前採用兩個 Cosmos DB container：

```text
container: completionCerts
partition key: /eventId

container: completionCertRequests
partition key: /eventId

container: publicLookupAttempts
partition key: /id
```

`completionCerts` 是完訓證明完整清單。名稱沿用活動管理的文件類型代碼 `completionCert`。CSV 匯入資料、簽到狀態、發證狀態、下載檔案 metadata、驗證 token hash 與驗證次數都記錄在同一筆資料中。CSV 上傳由 Python API 同步解析與寫入；目前預期單次約數百筆資料可在可接受時間內完成，因此不設計 DB 進度狀態或進度條。CSV 匯入當下尚未產生完訓證明檔案與驗證 token，因此 `issuedPdfBlobName`、`verificationTokenHash` 與 `issuedAt` 預設為 `null`，`verificationCount` 預設為 `0`；等會眾申請完訓證明且系統完成產生檔案後才回填發證檔案與 token 資料。

`completionCertRequests` 只記錄會眾是否申請資料調整、申請備註、審核狀態與通知狀態。這類資料不是完訓證明權威清單本身，因此獨立存放。

目前不保留原始 CSV 檔案。產生後 PDF 應存放於 Blob Storage `issued-certs` container。Cosmos DB 只儲存完訓證明清單資料、狀態與產生後檔案的 blob 名稱，不儲存 CSV 原文或 PDF 二進位。

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
| `issuedPdfBlobName` | string \| null | `issued-certs` 中的 PDF blob 名稱；CSV 匯入時為 null |
| `verificationTokenHash` | string \| null | 公開驗證 token 的雜湊值；CSV 匯入時為 null，且不得存明文 token |
| `verificationCount` | int | 公開驗證端點成功驗證此完訓證明的累計次數；CSV 匯入時為 0 |
| `issuedAt` | string \| null | 發證時間，UTC ISO 8601；CSV 匯入時為 null |
| `createdAt` | string | 建立時間，UTC ISO 8601 |

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

公開首頁查詢到 `changeRequested` 狀態時仍會進入「選擇證明顯示方式」，但不再顯示「提出修改申請」。頁面會提示修改申請正在處理中，並告知使用者若現在產生證書，將視為放棄本次修改申請。

目前 KKTIX CSV 白名單欄位：

| 正規化欄位 | CSV 表頭 |
| --- | --- |
| `number` | `報名序號` |
| `kktixId` | `Id` |
| `badgeName` | `你是誰，ID 或具有鑑識度的名稱 Name on Badge` |
| `name` | `姓名 Full Name` |
| `organization` | `服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)` |
| `email` | `Email` 或 `email` |
| `ticketName` | `票種` |

CSV 必要表頭欄位包含：

- `報名序號`
- `Id`
- `你是誰，ID 或具有鑑識度的名稱 Name on Badge`
- `Email` 或 `email`
- `票種`
- `服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)`

`報名序號` 必須是整數。

`姓名 Full Name` 與
`服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)`
欄位必須存在，但每列值可以空白；缺少值時分別以空字串儲存。

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

`publicLookupAttempts` 記錄公開文件查詢的連續失敗狀態，用於降低暴力嘗試。此 container 會儲存 Azure Functions 收到的 `X-Forwarded-For` 第一個 IP，並在寫入前移除常見的來源 port 格式，例如 `198.51.100.25:54321` 或 `[2001:db8::25]:54321`，供營運稽核與安全追蹤使用；`id` 使用由該 IP 穩定產生的 UUIDv5，讓後端仍可用 point read 取得單一 IP 的查詢限制狀態。若請求沒有 `X-Forwarded-For`，後端會照常查詢文件，但不會建立或更新 `publicLookupAttempts` 文件，避免把本機或特殊環境的請求共同寫成 `unknown`。

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
- 同一 IP 在 24 小時內連續查詢失敗 5 次後，`blockedUntil` 設為開始封鎖時間加 24 小時。
- 同一 IP 在 24 小時內查詢尚未開放的完訓證明 10 次後，`blockedUntil` 設為開始封鎖時間加 12 小時；此計數與一般查不到資料的 `failureCount` 分開記錄。
- 封鎖期間公開查詢 API 直接回覆封鎖錯誤，不查詢文件資料。
- 對使用者顯示的封鎖訊息不得提到 IP；若可取得 `blockedUntil`，滿 1 小時以上以小時計算並無條件進位，不足 1 小時以分鐘計算並無條件進位，不足 1 分鐘顯示 1 分鐘。
- 查詢成功時，將 `failureCount` 與 `notAvailableCount` 歸零，並清除對應時間欄位與 `blockedUntil`。
- 對使用者顯示的失敗訊息不得指出哪個欄位錯誤，也不得提示剩餘嘗試次數。
- 此 container 只供公開查詢限制使用；公開查詢流程對此 container 的 point read 與 upsert 最多等待 5 秒，若 Cosmos DB 提前回應就立即使用結果，避免 Cosmos DB 延遲讓首頁查詢長時間卡住。
- Functions worker 可在記憶體中快取已封鎖 attempt id 與 `blockedUntil`，讓封鎖期間的後續查詢不必每次讀取 Cosmos DB；此快取不得用於放行，只能用於提早拒絕，且即使 DB 文件異常帶有更遠的 `blockedUntil`，本機快取也不得超過 1 小時。
