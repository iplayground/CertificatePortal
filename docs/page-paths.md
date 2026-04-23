# 頁面路徑定義

本文件作為目前瀏覽器頁面路徑與畫面行為的主文件。

## 目前保留頁面

| Method | Path | 說明 | 輸出格式 |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾填寫基本資料並進入完訓證明流程 | `text/html` |
| `GET` | `/portal` | 管理平台登入入口 | `text/html` |
| `GET` | `/portal/dashboard` | 管理者登入後的內部工作區頁面 | `text/html` |
| `GET` | `/portal/dashboard/welcome` | dashboard iframe 預設載入的歡迎頁 | `text/html` |
| `GET` | `/portal/dashboard/records` | dashboard iframe 的檢視清單頁 | `text/html` |
| `GET` | `/portal/dashboard/upload` | dashboard iframe 的上傳清單頁 | `text/html` |
| `GET` | `/verify/{certId}` | 公開驗證頁面 | `text/plain` |

## 共用規則

### 呈現方式

- 首頁與管理平台目前為靜態 HTML GUI
- 公開驗證頁面目前為靜態純文字輸出
- 所有頁面暫不接入實際業務邏輯、資料存取、上傳處理或登入驗證

### 語系規則

- 首頁與公開驗證頁支援 `zh-TW` 與 `en-US`
- 若存在使用者先前在首頁選擇的 `ipg_locale` cookie，公開頁面優先使用該語系
- 若不存在語系 cookie，才依瀏覽器 `Accept-Language` 決定初始語系
- 語系切換器只出現在首頁 `/`
- 首頁切換語系時，由前端直接更新頁面文案，不會整頁重新整理
- 管理平台固定使用繁體中文，不納入 i18n 範圍

### 主題與 head 規則

- 依使用者 `prefers-color-scheme` 自動切換日間與夜間模式
- 日間模式沿用首頁既有淺色視覺，夜間模式沿用管理平台既有深色視覺
- `/assets/theme.css` 提供首頁與管理平台共用主題 token
- 個別頁面 CSS 只負責版面與元件樣式
- 所有 HTML 頁面都載入 `/assets/favicon.png`
- 頁面 title 統一使用 `頁面名稱 - iPlayground`
- `/portal/dashboard` 會在 iframe 載入後，將父頁 title 同步成目前內容頁 title
- 首頁只保留 `twitter:card`，其餘社群分享資訊以 Open Graph metadata 為主

### 管理平台命名空間

- 管理平台入口固定為 `/portal`
- 登入後頁面使用 `/portal/...` 子路徑
- 首頁 `/` 不提供管理平台按鈕入口
- 完訓證明管理平台目前位於 `/portal/dashboard`
- dashboard 以 iframe 載入 `welcome`、`records`、`upload` 三個獨立頁面
- 左側功能清單固定顯示 `檢視清單` 與 `上傳清單`

## 各頁面定義

### `/`

- 置中單卡式首頁版型
- 顯示 iPlayground logo 與品牌色
- 提供語系切換器，目前支援 `zh-TW` 與 `en-US`
- 提供活動名自訂下拉元件，目前固定為 `iPlayground 2026`
- 提供報名人姓名與 `email` 輸入欄位
- 顯示目前尚未串接資料庫與證明流程的提示
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
- 顯示 `完訓證明管理平台` 標題與 `管理者登入` 小標
- 提供管理者帳號與密碼欄位，以及顯示或隱藏密碼的前端互動
- 登入按鈕預設為 disabled，只有在帳號與密碼都已輸入時才可點擊
- 成功送出後導向 `/portal/dashboard`
- 以瀏覽器 session storage 暫存目前輸入的帳號字串，用於登入後頁面顯示

### `/portal/dashboard`

- 作為完訓證明管理平台登入後的桌面版工作區頁面
- 左側保留固定導覽列
- 左側品牌區塊下方、功能清單上方顯示目前登入帳號與返回首頁按鈕
- 右側工作區固定使用 iframe 呈現
- 點擊左上方品牌按鈕時，右側 iframe 載入 `/portal/dashboard/welcome`
- 點擊功能項目時，右側 iframe 會切換到對應的獨立頁面
- 點擊 `返回首頁` 會清除前端暫存帳號並回到 `/`

### `/portal/dashboard/welcome`

- 作為 dashboard 右側 iframe 預設載入的歡迎頁
- 顯示品牌 logo、平台標題、登入帳號歡迎訊息與四格統計資訊
- 四格統計目前顯示 `系統可下載數`、`下載人數`、`驗證次數`、`待處理案件數量`

### `/portal/dashboard/records`

- 作為 dashboard 右側 iframe 的檢視清單頁
- 現階段只保留獨立工作頁骨架

### `/portal/dashboard/upload`

- 作為 dashboard 右側 iframe 的上傳清單頁
- 現階段只保留獨立工作頁骨架

## 靜態資產

目前頁面透過下列路徑載入樣式、互動與品牌素材：

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/assets/portal.css` | 管理平台登入頁與管理中心共用樣式 |
| `GET` | `/assets/portal-login.js` | 管理平台登入頁互動腳本 |
| `GET` | `/assets/portal-dashboard.js` | 管理中心頁面互動腳本 |
| `GET` | `/assets/favicon.png` | 所有 HTML 頁面共用 favicon |
| `GET` | `/assets/home.css` | 首頁樣式 |
| `GET` | `/assets/home.js` | 首頁互動腳本 |
| `GET` | `/assets/theme.css` | 首頁與管理平台共用的日夜主題 token |
| `GET` | `/assets/language_icon.svg` | 首頁語系切換器使用的本地 SVG icon |
| `GET` | `/assets/logo_b_alpha.png` | iPlayground 品牌 logo |
| `GET` | `/assets/logo_sq_b.png` | dashboard 左上角品牌方形 logo |

## 暫時不保留

除 `/`、`/portal`、`/portal/dashboard`、`/portal/dashboard/welcome`、`/portal/dashboard/records`、`/portal/dashboard/upload` 與 `/verify/{certId}` 外，其餘 API、管理子路由與相關實作暫時不保留。
