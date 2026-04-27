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
| `documentTypes` | string[] | 此活動開放申請的文件類型 |
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
SELECT c.id, c.name, c.status, c.documentTypes, c.completionCertDownloadStartsAt
FROM c
ORDER BY c.updatedAt DESC
```

活動清單只投影管理端 UI 需要的欄位，並依最後更新時間由新到舊排序。

單筆活動讀取：

```text
id = <event-id>
partition key = <event-id>
```

雖然活動清單查詢會跨 partition，但活動數量與管理端使用頻率都很低，初期接受這個取捨。單筆讀取與更新應使用 point read / replace，並以 `id` 作為 partition key。

管理端進入 `/portal/dashboard` 後，伺服器會在背景預先初始化活動管理使用的 Cosmos DB container client；同一個 Functions worker 生命週期內會重用該 client，避免第一次進入活動管理時才承擔 SDK 與 credential chain 初始化成本。
