# 頁面路徑定義

本文件作為目前瀏覽器頁面路徑與畫面行為的主文件。

## 目前保留頁面

| Method | Path | 說明 | 輸出格式 |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾填寫基本資料、選擇文件類型並進入文件申請流程 | `text/html` |
| `GET` | `/portal` | 管理平台登入入口 | `text/html` |
| `GET` | `/portal/dashboard` | 管理者登入後的內部工作區頁面 | `text/html` |
| `GET` | `/portal/dashboard/welcome` | dashboard iframe 預設載入的歡迎頁 | `text/html` |
| `GET` | `/portal/dashboard/completion-certs` | dashboard iframe 的完訓證明頁 | `text/html` |
| `GET` | `/portal/dashboard/tax-receipts` | dashboard iframe 的營業稅繳稅證明頁 | `text/html` |
| `GET` | `/portal/dashboard/events` | dashboard iframe 的活動管理頁 | `text/html` |
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

目前首頁與管理平台都先以 HTML 頁面呈現；公開驗證頁面仍維持靜態純文字顯示。管理平台目前已接入 Google Workspace SSO、Google Group 授權檢查與 session cookie，但尚未串接實際業務資料。

- 首頁與管理平台目前為靜態 HTML GUI，部分管理頁面已有前端暫存互動
- 公開驗證頁面目前為靜態純文字輸出
- 實際業務資料、資料存取、後端上傳處理與持久化流程尚未串接
- 完訓證明頁目前已有前端 CSV 解析與頁面暫存清單，用於管理介面流程示意

### 表單輸入規則

- 首頁的報名人姓名、`email` 欄位與管理平台的活動名稱欄位不是登入憑證欄位，應在初始 HTML 標記為不使用瀏覽器自動完成與常見密碼管理器 autofill
- 目前採用 `autocomplete="off"`，並搭配常見密碼管理器的忽略屬性：`data-1p-ignore`、`data-op-ignore`、`data-lpignore`、`data-bwignore`、`data-protonpass-ignore` 與 `data-form-type="other"`
- 不以 CSS 隱藏密碼管理器注入的 DOM 作為基線做法；若日後新增同類型非憑證文字輸入欄位，應沿用同一組 HTML 屬性

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
- 左側功能清單固定依序顯示 `活動管理`、`完訓證明` 與 `營業稅繳稅證明`
- 左側功能清單說明文字：`活動與文件設定`、`清單與資料上傳`、`內容規劃中`

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
- 左側功能清單說明文字：`活動與文件設定`、`清單與資料上傳`、`內容規劃中`

## 各頁面定義

### `/`

- 置中單卡式首頁版型
- 顯示 iPlayground logo 與品牌色
- logo 置中顯示
- 提供語系切換器，目前支援 `zh-TW` 與 `en-US`
- 提供活動名自訂下拉元件，目前固定為 `iPlayground 2026`
- 提供文件類型自訂下拉元件，目前固定為 `完訓證明`、`營業稅繳稅證明`
- 首頁文件類型顯示文字納入 i18n，表單值使用穩定文件類型代碼：`completionCert`、`taxReceipt`
- 提供報名人姓名與 `email` 輸入欄位
- 顯示目前尚未串接資料庫與文件流程的提示
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
- 左側 `營業稅繳稅證明` 功能項目目前保留入口，但內頁內容先留空
- 右側工作區固定使用 iframe 呈現
- 點擊左上方 `文件管理平台` 品牌按鈕時，右側 iframe 載入 `/portal/dashboard/welcome`
- 點擊功能項目時，右側 iframe 會切換到對應的獨立頁面
- 父頁 title 會同步成目前 iframe 顯示頁面的 title
- `/portal/dashboard` 與其 iframe 子頁都會在伺服器端重新檢查 session cookie 與授權狀態
- 點擊 `登出` 會導向 `/portal/auth/logout`，再回到 `/portal`

### `/portal/dashboard/welcome`

- 作為 dashboard 右側 iframe 預設載入的歡迎頁
- 顯示與首頁頂部一致的品牌 logo、平台標題、登入帳號歡迎訊息與四格統計資訊
- 四格統計目前顯示 `系統可下載數`、`下載人數`、`驗證次數`、`待處理案件數量`

### `/portal/dashboard/completion-certs`

- 作為 dashboard 右側 iframe 的完訓證明頁
- 頁面標題不顯示額外的左上角小字
- 主畫面提供完訓證明資料的清單檢視區
- CSV 匯入目前由前端解析並暫存在頁面狀態，尚未送出到後端
- CSV 匯入後的清單列預設為 `未簽到`，下載按鈕停用
- 同一活動再次匯入 CSV 時，會以新的暫存清單取代該活動既有暫存清單
- 清單欄位包含報名序號、票種、姓名、Email、簽到狀態與操作
- 清單表格標題列置中，資料列內容維持欄位閱讀對齊
- 清單上方提供目前活動全部資料的批次設定，可設為 `已簽到` 或 `未簽到`
- 完訓證明清單不提供選取列功能，批次設定一律套用至目前活動全部資料
- 每列提供可雙向切換的簽到狀態開關
- 每列在操作欄提供 `下載` 按鈕
- 清單上方提供採用專案主題樣式的活動篩選下拉選單，選擇時直接套用篩選
- 標題列右上方提供 `上傳完訓證明資料` 按鈕
- 點擊 `上傳完訓證明資料` 後開啟中央上傳視窗
- 上傳視窗可選擇匯入資料所屬活動，預設帶入目前清單篩選活動
- 上傳視窗僅接受 CSV 檔，並使用管理平台風格的檔案選取區
- 若直接開啟完訓證明子頁，點擊上傳按鈕後會使用頁內中央上傳視窗作為 fallback
- 現階段尚未串接後端資料來源、永久儲存或實際檔案上傳流程

### `/portal/dashboard/tax-receipts`

- 作為 dashboard 右側 iframe 的營業稅繳稅證明頁
- 路徑名稱採用簡化的 407 收據相關語意：`tax-receipts`
- 現階段內頁先留空
- 僅保留 HTML title，供父層 dashboard 同步頁面標題

### `/portal/dashboard/events`

- 作為 dashboard 右側 iframe 的活動管理頁
- 預設顯示目前活動清單、活動狀態與各活動可申請文件類型；目前資料為靜態示意資料
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
- `營業稅繳稅證明` 的文件類型代碼為 `taxReceipt`，管理端說明文字為 `開放協會 407 收據聯影本供下載`
- 現階段尚未串接資料庫、權威活動資料或文件類型設定寫入流程

## 靜態資產

目前頁面透過下列路徑載入樣式、互動與品牌素材：

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/assets/portal.css` | 管理平台登入頁與管理中心共用樣式 |
| `GET` | `/assets/portal-login.js` | 管理平台登入入口的連結互動腳本 |
| `GET` | `/assets/portal-dashboard.js` | 管理中心頁面互動腳本 |
| `GET` | `/assets/portal-dashboard-welcome.js` | 管理中心歡迎頁互動腳本 |
| `GET` | `/assets/portal-dashboard-completion-certs.js` | 完訓證明頁清單與 CSV 匯入腳本 |
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
