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
| `GET` | `/portal/dashboard/tax-receipts` | dashboard iframe 的營業稅繳稅證明頁 | `text/html` |
| `GET` | `/portal/dashboard/events` | dashboard iframe 的活動管理頁 | `text/html` |
| `GET` | `/api/v1/events` | 公開首頁可申請活動清單 | `application/json` |
| `POST` | `/api/v1/document-lookup` | 公開首頁文件查詢 | `application/json` |
| `GET` | `/api/v1/admin/events` | 查詢活動管理資料 | `application/json` |
| `POST` | `/api/v1/admin/events` | 建立活動管理資料 | `application/json` |
| `PUT` | `/api/v1/admin/events/{eventId}` | 更新單筆活動管理資料 | `application/json` |
| `GET` | `/api/v1/admin/completion-certs` | 查詢單一活動的完訓證明清單 | `application/json` |
| `POST` | `/api/v1/admin/completion-certs/import` | 匯入單一活動的 KKTIX 完訓證明 CSV | `application/json` |
| `PUT` | `/api/v1/admin/completion-certs/{certid}` | 修改單筆完訓證明資料 | `application/json` |
| `GET` | `/verify/{certId}` | 公開驗證頁面 | `text/plain` |

## 內部導向端點

下列路徑屬於登入流程或狀態切換用途，不視為一般瀏覽導覽頁面，也不應和主要頁面案例混在一起討論。

| Method | Path | 說明 | 輸出格式 |
| --- | --- | --- | --- |
| `GET` | `/portal/auth/google/login` | 管理平台 Google 登入導向端點 | `302 redirect` |
| `GET` | `/portal/auth/google/callback` | 管理平台 Google callback 端點 | `302 redirect` |
| `GET` | `/portal/auth/logout` | 管理平台登出端點 | `302 redirect` |

## 共用規則

### 呈現方式

目前首頁與管理平台都先以 HTML 頁面呈現；公開驗證頁面仍維持靜態純文字顯示。管理平台目前已接入 Google Workspace SSO、Google Group 授權檢查與 session cookie；活動管理、首頁公開活動清單與完訓證明 CSV 匯入已串接 Cosmos DB，其餘文件資料流程仍逐步實作中。

- 首頁 HTML 不同步查詢 Cosmos DB；頁面先載入後由前端呼叫 `GET /api/v1/events`，再依狀態為 `open` 的活動顯示活動清單。管理平台的活動管理與完訓證明清單已串接 Cosmos DB，營業稅繳稅證明頁仍為前端暫存互動
- 公開驗證頁面目前為靜態純文字輸出
- 活動管理已提供 Cosmos DB 的活動新增、查詢與修改；完訓證明 CSV 由後端解析、驗證並寫入 Cosmos DB；營業稅繳稅證明的後端上傳處理與持久化流程尚未串接
- 完訓證明頁目前已有後端 CSV 匯入、活動篩選、清單載入與單筆資料修改流程
- 營業稅繳稅證明頁目前已有前端單筆 PDF、PNG 或 JPG/JPEG 新增與頁面暫存清單，用於管理介面流程示意；目前不支援 WebP

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
- 目前只串接 `completionCert` 的查詢判斷；`taxReceipt` 後端持久化尚未完成前會視為查不到。

Request JSON 範例：

```json
{
  "documentType": "completionCert",
  "eventId": "evt_550e8400-e29b-41d4-a716-446655440000",
  "registrationNumber": "100",
  "email": "attendee@example.com"
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
- 語系切換器只出現在首頁 `/`
- 首頁切換語系時，由前端直接更新頁面文案，不會整頁重新整理
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
- 文件管理平台以 iframe 載入歡迎頁、`活動管理`、`完訓證明` 與 `營業稅繳稅證明` 四個獨立頁面
- 進入 `/portal/dashboard` 後，伺服器會在背景預先初始化活動管理使用的 Cosmos DB container client，降低第一次進入活動管理時才初始化 SDK 與 credential chain 的延遲
- 進入 `/portal/dashboard` 後，前端會透過 `portal-event-cache.js` 預載 `GET /api/v1/admin/events`，並將活動清單暫存在同一瀏覽器分頁的 `sessionStorage`；各 iframe 子頁進入時可先用快取渲染，再直接呼叫 `GET /api/v1/admin/events` 取得最新活動清單並回寫快取
- 左側功能清單固定依序顯示 `活動管理`、`完訓證明` 與 `營業稅繳稅證明`
- 左側功能清單說明文字：`活動與文件設定`、`清單與資料上傳`、`PDF/PNG/JPG 上傳與管理`

### 主題與 head 規則

- 依使用者 `prefers-color-scheme` 自動切換日間與夜間模式
- 日間模式沿用首頁既有淺色視覺，夜間模式沿用管理平台既有深色視覺
- `/assets/theme.css` 提供首頁與管理平台共用主題 token
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
- dashboard 以 iframe 載入 `welcome`、`events`、`completion-certs`、`tax-receipts` 四個獨立頁面
- 左側功能清單固定依序顯示 `活動管理`、`完訓證明` 與 `營業稅繳稅證明`
- 左側功能清單說明文字：`活動與文件設定`、`清單與資料上傳`、`PDF/PNG/JPG 上傳與管理`

## 各頁面定義

### `/`

- 置中單卡式首頁版型
- 顯示 iPlayground logo 與品牌色
- logo 置中顯示
- 提供語系切換器，目前支援 `zh-TW` 與 `en-US`
- 活動在載入中顯示 `活動載入中`；沒有活動或只有一個活動時以靜態欄位顯示，只有多個活動可選時才使用下拉選單
- 活動清單會顯示所有狀態為 `open` 的活動；若選取的活動沒有可申請文件，文件類型欄位顯示 `尚無可申請文件`，不顯示申請資料欄位，查詢按鈕維持停用
- 文件類型在活動載入完成前隱藏；活動載入完成且有活動時，依所選活動的 `documentTypes` 顯示可申請文件
- 文件類型只有一個時以靜態欄位顯示，不顯示下拉三角；多個文件類型時使用自訂下拉元件
- 首頁文件類型顯示文字納入 i18n，表單值使用穩定文件類型代碼：`completionCert`、`taxReceipt`
- 首頁依文件類型顯示申請資料欄位：`完訓證明` 需要報名序號與 `email`；`營業稅繳稅證明` 需要統編與產製時間
- `營業稅繳稅證明` 的產製時間使用共用日期時間選擇器的秒數模式，顯示年、月、日、時、分、秒
- 查詢文件按鈕在目前可見申請資料欄位未完整填寫前維持停用
- 查詢文件送出後使用滿版 loading 遮罩鎖住整個 window，避免等待期間切換語系或調整表單資料
- 顯示頁尾版權聲明

### `/verify/{certId}`

- 顯示頁面名稱、`certId` 與目前尚未串接實際驗證資料的狀態
- 不提供語系切換器，但會沿用首頁選擇的語系 cookie
- 當 `certId` 為 `demo-cert` 時，會輸出：

```text
iPlayground 完訓證明驗證頁面

certId: demo-cert
status: 尚未串接實際驗證資料
```

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
- 點擊 `登出` 會導向 `/portal/auth/logout`，再回到 `/portal`
- 管理端會對資料庫造成異動的 API 需要通過伺服器端 session 授權、同源 `Origin` 或 `Referer` 檢查，以及頁面注入的 CSRF token 檢查；第三方網頁即使知道 API 路徑，也不能直接操作

### `/portal/dashboard/welcome`

- 作為 dashboard 右側 iframe 預設載入的歡迎頁
- 顯示與首頁頂部一致的品牌 logo、平台標題、登入帳號歡迎訊息與文件類型統計資訊
- 統計區使用單一 `最近一期活動資料` 標題，避免在各文件類型區段重複顯示
- 文件類型統計區段使用類似完訓證明頁工作區的大外框樣式包覆，內部為四格指標
- `完訓證明` 區段顯示最近一期活動的 `系統可下載數`、`下載人數`、`驗證次數`、`待處理案件數量`
- `營業稅繳稅證明` 區段顯示 `收據張數`、`已查詢公司數`、`已下載次數`、`收據總金額`
- `營業稅繳稅證明` 的 `收據總金額` 使用 `$` 與完整金額格式，例如 `$186,000`，不使用 `NT$` 或 `K` 縮寫

### `/portal/dashboard/completion-certs`

- 作為 dashboard 右側 iframe 的完訓證明頁
- 頁面標題不顯示額外的左上角小字
- 主畫面提供完訓證明資料的清單檢視區
- 完訓證明資料依活動 `eventId` 從 `GET /api/v1/admin/completion-certs?eventId=<eventId>` 載入
- CSV 匯入會呼叫 `POST /api/v1/admin/completion-certs/import`，由後端解析 KKTIX CSV、過濾非白名單欄位，並寫入 Cosmos DB `completionCerts`
- CSV 匯入後的清單列預設為 `未簽到`，下載按鈕停用；`issuedPdfBlobName`、`verificationTokenHash` 與 `issuedAt` 在會眾申請並完成產生檔案前為 `null`
- 同一活動再次匯入 CSV 時，會以穩定的 `eventId + number + kktixId` 產生文件 ID 並 upsert 到同一批 Cosmos DB 資料
- 清單欄位包含報名序號、ID、Badge Name、姓名、公司名、Email、票種、簽到狀態與操作
- 每列在操作欄提供 `下載` 與 `修改` 按鈕
- 修改視窗可更新姓名、公司名與 Email；報名序號、KKTIX ID、Badge Name 與票種不直接修改
- 修改視窗將報名序號、ID 與票種放在同一排，且 Badge Name 與票種為唯讀顯示
- 修改成功後顯示共用 page alert 成功提示；共用 alert 預設 6 秒後自動關閉
- 清單表格標題列置中，標題與資料列皆維持單行
- 完訓證明表格使用固定欄寬避免換頁時欄寬跳動，過長內容以 `…` 截斷
- 完訓證明清單每頁最多顯示 10 筆；超過 10 筆時顯示上一頁、目前頁碼與下一頁控制
- 清單上方提供目前活動全部資料的批次設定，可設為 `已簽到` 或 `未簽到`，並逐筆呼叫 `PUT /api/v1/admin/completion-certs/{certid}` 將 `attendanceStatus` 寫回 Cosmos DB
- 完訓證明清單不提供選取列功能，批次設定一律套用至目前活動全部資料
- 批次簽到狀態更新進行中時，完訓證明表格會進入 `aria-busy` 狀態並顯示停用樣式；列內簽到開關、下載、修改、分頁與批次按鈕皆停用，避免管理者同時編輯資料
- 每列提供可雙向切換的簽到狀態開關，切換後會呼叫 `PUT /api/v1/admin/completion-certs/{certid}` 將 `attendanceStatus` 寫回 Cosmos DB；簽到狀態更新成功或失敗 alert 會在 3 秒後自動關閉
- 清單上方提供活動篩選欄位；沒有活動或只有一個活動時以靜態欄位顯示，只有多個活動可選時才使用下拉選單並直接套用篩選
- 活動篩選與上傳視窗活動選擇會先使用 portal 分頁內的活動清單快取渲染，再直接呼叫 `GET /api/v1/admin/events` 更新畫面與快取；快取只作為先顯示用途，不作為權威資料來源
- 標題列右上方提供 `上傳完訓證明資料` 按鈕
- 點擊 `上傳完訓證明資料` 後開啟中央上傳視窗
- 上傳視窗可選擇匯入資料所屬活動，預設帶入目前清單篩選活動
- 上傳視窗僅接受 CSV 檔，並使用管理平台風格的檔案選取區
- 若直接開啟完訓證明子頁，點擊上傳按鈕後會使用頁內中央上傳視窗作為 fallback

### `/portal/dashboard/tax-receipts`

- 作為 dashboard 右側 iframe 的營業稅繳稅證明頁
- 路徑名稱採用簡化的 407 收據相關語意：`tax-receipts`
- 頁面標題不顯示額外的左上角小字
- 主畫面提供營業稅繳稅證明的清單檢視區
- 清單欄位包含統編、產製時間、金額、收據聯檔案與操作
- 營業稅繳稅證明沒有停用狀態，只要完成上傳即一律可下載
- 每列在操作欄提供 `下載`、`修改` 與 `刪除` 按鈕
- 清單上方提供活動篩選欄位；沒有活動或只有一個活動時以靜態欄位顯示，只有多個活動可選時才使用下拉選單並直接套用篩選
- 活動篩選與上傳視窗活動選擇會先使用 portal 分頁內的活動清單快取渲染，再直接呼叫 `GET /api/v1/admin/events` 更新畫面與快取；快取只作為先顯示用途，不作為權威資料來源
- 標題列右上方提供 `新增繳稅證明` 按鈕
- 點擊 `新增繳稅證明` 後開啟中央上傳視窗
- 上傳視窗可選擇資料所屬活動，預設帶入目前清單篩選活動
- 上傳視窗逐筆輸入統編、金額、產製時間，並選擇一個 PDF、PNG 或 JPG/JPEG 檔；修改既有資料時可不重新選檔
- 上傳視窗支援 PDF、PNG 與 JPG/JPEG 檔，並使用管理平台風格的檔案選取區；目前不支援 WebP
- 新增模式的上傳視窗在送出按鈕右側提供 `還有其他檔案要上傳` 勾選項，勾選後新增成功會保留視窗並清空欄位以便連續新增
- `還有其他檔案要上傳` 使用管理端共用 checkbox 色彩樣式，但不顯示外框線或背景，文字不可被滑鼠拖曳選取
- 若直接開啟營業稅繳稅證明子頁，點擊新增或修改按鈕後會使用頁內中央上傳視窗作為 fallback
- 現階段尚未串接後端資料來源、永久儲存或實際檔案上傳流程

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
      "issuedAt": null,
      "createdAt": "2026-04-28T06:02:00Z"
    }
  ]
}
```

### `POST /api/v1/admin/completion-certs/import`

- 匯入單一活動的 KKTIX CSV，後端只寫入白名單欄位；欄位規則由 [cosmos-data-model.md](cosmos-data-model.md) 定義
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 不保留原始 CSV 檔案；匯入後直接 upsert 到 Cosmos DB `completionCerts`

Request JSON example:

```json
{
  "eventId": "evt_20260425_ipg",
  "csvText": "報名序號,票種,Email,Id,你是誰，ID 或具有鑑識度的名稱 Name on Badge,服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)\n1,一般票,ming@example.com,KKTIX-001,Ming,iPlayground"
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
      "issuedAt": null,
      "createdAt": "2026-04-28T06:02:00Z"
    }
  ],
  "summary": {
    "imported": 1
  }
}
```

### `PUT /api/v1/admin/completion-certs/{certid}`

- 修改單筆完訓證明清單資料
- 只接受已登入且通過授權的管理者 session
- 必須是同源管理平台頁面送出的請求，並帶 `X-Portal-CSRF-Token` header
- 目前可修改欄位為 `name`、`organization`、`email`、`attendanceStatus`
- `attendanceStatus` 只接受 `checkedIn` 或 `notCheckedIn`
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
    "issuedAt": null,
    "createdAt": "2026-04-28T06:02:00Z"
  }
}
```

## 靜態資產

目前頁面透過下列路徑載入樣式、互動與品牌素材：

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/assets/portal.css` | 管理平台登入頁與管理中心共用樣式 |
| `GET` | `/assets/portal-login.js` | 管理平台登入入口的連結互動腳本 |
| `GET` | `/assets/portal-event-cache.js` | 管理平台活動清單分頁快取與跨頁更新事件腳本 |
| `GET` | `/assets/portal-dashboard.js` | 管理中心頁面互動腳本 |
| `GET` | `/assets/portal-dashboard-welcome.js` | 管理中心歡迎頁互動腳本 |
| `GET` | `/assets/portal-dashboard-completion-certs.js` | 完訓證明頁清單與 CSV 匯入腳本 |
| `GET` | `/assets/portal-dashboard-tax-receipts.js` | 營業稅繳稅證明頁清單與單筆 PDF、PNG 或 JPG/JPEG 新增、修改、刪除腳本 |
| `GET` | `/assets/portal-dashboard-events.js` | 活動管理頁清單列點擊、建立/編輯活動子畫面與 fallback modal 互動腳本 |
| `GET` | `/assets/page-alert.js` | 共用 alert 元件的關閉與自動消失腳本 |
| `GET` | `/assets/favicon.png` | 所有 HTML 頁面共用 favicon |
| `GET` | `/assets/home.css` | 首頁樣式 |
| `GET` | `/assets/home.js` | 首頁互動腳本 |
| `GET` | `/assets/theme.css` | 首頁與管理平台共用的日夜主題 token 與 shared alert 樣式 |
| `GET` | `/assets/google-g-icon.svg` | 管理平台 Google 登入按鈕使用的本地 SVG icon |
| `GET` | `/assets/language_icon.svg` | 首頁語系切換器使用的本地 SVG icon |
| `GET` | `/assets/logo_b_alpha.png` | iPlayground 品牌 logo |
| `GET` | `/assets/logo_sq_b.png` | dashboard 左上角品牌方形 logo |

## 暫時不保留

目前只保留下列頁面與路徑：

- `/`
- `/portal`
- `/portal/dashboard`
- `/portal/dashboard/welcome`
- `/portal/dashboard/completion-certs`
- `/portal/dashboard/tax-receipts`
- `/portal/dashboard/events`
- `/verify/{certId}`

其餘 API、管理子路由與相關實作暫時不保留。
