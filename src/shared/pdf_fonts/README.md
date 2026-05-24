# PDF 字體

此目錄是完訓證明 PDF 字體在部署包內的位置。PDF 產生器會從這裡讀取 regular 與 bold 字體並嵌入輸出 PDF，讓動態文字能跨平台穩定顯示。

字體二進位檔不提交到 git。本機驗證時，請依 `src/shared/completion_certificate_pdf.py` 預期的檔名，將 regular 與 bold 字體檔放入此目錄；`.gitignore` 會避免這些本機檔案被誤提交。

正式部署時，GitHub Actions 會在打包 Azure Function app 前，從 private `document-assets` Blob container 下載已核准的字體檔到此目錄。不要在 `.funcignore` 排除此目錄或字體副檔名，否則下載後的字體檔不會被放進 Function 部署包。

若本機測試或其他部署方式需要從原始碼目錄外提供字體，需同時設定：

- `COMPLETION_CERTIFICATE_REGULAR_FONT_PATH`
- `COMPLETION_CERTIFICATE_BOLD_FONT_PATH`

若部署包內沒有字體，也沒有同時設定上述兩個環境變數，PDF 產生器會退回 ReportLab CID 字體與平台字體。這個 fallback 可用於開發，但不具備嵌入 TrueType/TTC 字體的跨平台顯示保證。
