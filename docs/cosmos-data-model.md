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
| `createdAt` | string | 建立時間，UTC ISO 8601 |
| `createdBy` | string | 建立者識別 |
| `updatedAt` | string | 最後更新時間，UTC ISO 8601 |
| `updatedBy` | string | 最後更新者識別 |

`status` 目前允許值：

```text
open
closed
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
- 使用 UUID v4，格式為 `evt_<uuid-v4>`。

Python 產生方式：

```python
from uuid import uuid4


def new_event_id() -> str:
    return f"evt_{uuid4()}"
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
  "createdAt": "2026-04-25T03:30:00Z",
  "createdBy": "admin@example.com",
  "updatedAt": "2026-04-25T03:30:00Z",
  "updatedBy": "admin@example.com"
}
```

### 查詢模式

活動清單：

```sql
SELECT * FROM c
ORDER BY c.createdAt DESC
```

單筆活動讀取：

```text
id = <event-id>
partition key = <event-id>
```

雖然活動清單查詢會跨 partition，但活動數量與管理端使用頻率都很低，初期接受這個取捨。單筆讀取與更新應使用 point read / replace，並以 `id` 作為 partition key。
