# 頁面路徑定義

本文件目前只定義會直接由瀏覽器打開的頁面路徑。

## 目前保留頁面

| Method | Path | 說明 | 輸出格式 |
| --- | --- | --- | --- |
| `GET` | `/` | 首頁，用於供會眾填寫基本資料並進入完訓證明流程 | `text/html` |
| `GET` | `/verify/{certId}` | 公開驗證頁面 | `text/plain` |

## 第一版頁面內容

目前首頁改為靜態 HTML GUI；公開驗證頁面仍維持靜態純文字顯示。兩者都不加入實際業務邏輯。

頁面語系目前採以下規則：

- 若存在使用者先前在首頁選擇的 `ipg_locale` cookie，所有頁面都優先使用該語系
- 若不存在語系 cookie，才依瀏覽器 `Accept-Language` 決定初始語系
- 語系切換器只出現在首頁 `/`
- 首頁切換語系時，由前端直接更新頁面文案，不會整頁重新整理

- `/`
  - 顯示置中單卡式首頁版型
  - 顯示 iPlayground logo 與品牌色樣式
  - 顯示語系切換器，目前支援 `zh-TW` 與 `en-US`
  - 提供活動名自訂下拉元件，目前固定為 `iPlayground 2026`
  - 提供報名人姓名輸入欄位
  - 提供 email 輸入欄位
  - 顯示目前尚未串接資料庫與證明流程的提示
  - 顯示頁尾版權聲明
- `/verify/{certId}`
  - 顯示頁面名稱
  - 顯示 `certId`
  - 顯示目前尚未串接實際驗證資料
  - 不提供語系切換器，但會沿用首頁選擇的語系 cookie

## 靜態資產

首頁目前透過下列路徑載入樣式、互動與品牌素材：

| Method | Path | 說明 |
| --- | --- | --- |
| `GET` | `/assets/home.css` | 首頁樣式 |
| `GET` | `/assets/home.js` | 首頁互動腳本 |
| `GET` | `/assets/language_icon.svg` | 首頁語系切換器使用的本地 SVG icon |
| `GET` | `/assets/logo_b_alpha.png` | iPlayground 品牌 logo |

## 暫時不保留

除上述兩個頁面外，其餘 API、管理路由與相關實作暫時移除。
