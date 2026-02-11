這是一份為 **HanYun Ebook Converter (雲端電子書自動化工廠)** 項目撰寫的完整技術白皮書與維護指南。

這份文檔旨在幫助您（或未來的開發者）在時隔多年後，能在 10 分鐘內重新理解整個系統架構、邏輯流與維護方式。

---

# 📘 HanYun Ebook Converter 項目總結報告

### 1. 項目願景 (Project Vision)

打造一個 **「無感化、全自動」** 的雲端電子書處理工廠。

* **輸入**：使用者只需將 TXT 小說或 EPUB 漫畫丟入雲端硬碟（Dropbox/Google Drive）的指定資料夾。
* **處理**：GitHub Actions 定時自動觸發，執行清洗、分章、排版、格式轉換。
* **輸出**：自動將適合 Kobo 閱讀器（KePub 格式）的成品回傳至雲端硬碟，並歸檔原始文件。

---

### 2. 系統架構 (System Architecture)

本項目採用 **模組化設計 (Modular Design)**，將「邏輯」、「配置」與「物流」完全分離。

#### 核心層級：

1. **控制層 (Main Controllers)**：
* `main.py` / `main_drive.py`：負責 **文字小說** 的調度。
* `manga_main.py` / `manga_main_drive.py`：負責 **漫畫** 的調度。


2. **核心邏輯層 (Core)**：
* `processor.py`：文字清洗、章節識別 (Regex)、簡繁轉換。
* `manga_processor.py`：EPUB 解包、智慧排序 (Natural Sort)、重新分章 (Rebuild)。
* `engine.py`：生成標準 EPUB、調用 `kepubify` 轉檔。


3. **適配層 (IO Adapters)**：
* `dropbox_client.py`：處理 Dropbox API（路徑導向）。
* `google_drive_client.py`：處理 Google Drive API（ID 導向，模擬路徑）。


4. **配置層 (Config & Styles)**：
* JSON 設定檔控制路徑與邏輯，CSS/JSON 控制電子書樣式。



---

### 3. 雲端目錄結構規範 (Directory Standard)

無論是 Dropbox 還是 Google Drive，我們統一了「雙產線」的目錄結構，保持整潔與邏輯一致性。

```text
Ebook-Converter/ (根目錄)
├── novel/                  <-- [產線 A] 文字小說
│   ├── txt/
│   │   ├── 新上傳/ (001, 002, 003)  <-- 丟這裡
│   │   └── 已處理/
│   ├── epub/               <-- 中間產物備份
│   └── kepub/              <-- 最終成品 (同步到 Kobo)
│
└── manga/                  <-- [產線 B] 漫畫
    ├── epub/
    │   ├── 新上傳/ (001, 002)       <-- 丟這裡
    │   └── 已處理/
    └── kepub/              <-- 最終成品

```

* **001/002/003 的意義**：這些子資料夾對應 `config/profile_map.json`，可以針對不同來源或類型的書套用不同的 **樣式 (Style)** 或 **處理邏輯**。

---

### 4. 關鍵邏輯詳解 (Core Logic)

#### A. 文字小說產線 (Novel Workflow)

1. **讀取**：下載 TXT。
2. **清洗**：
* **編碼偵測**：自動識別 UTF-8 或 GBK。
* **簡繁轉換**：使用 OpenCC (s2t)。
* **分章**：透過正則表達式 `第[0-9一二三...]+章` 識別章節，自動生成目錄。


3. **排版**：注入 `styles/vertical.json` (直排) 或其他定義的 CSS。
4. **轉檔**：生成標準 EPUB  `kepubify` 轉換  上傳。

#### B. 漫畫產線 (Manga Workflow)

這部分包含兩套邏輯：

* **模式 001 (重組模式 - Rebuild)**：
* **適用場景**：網路下載的亂序漫畫，或希望自定義章節（如 20 頁一章）。
* **技術亮點**：
* 解析原始 `content.opf` 獲取真實閱讀順序（Spine），而非盲目按檔名排序。
* 保留原始 Metadata（書名、作者）。
* 強制修復封面（設定第一張圖為 Cover）。
* 生成帶有 `(1-20頁)` 導航目錄的 EPUB。




* **模式 002 (直通模式 - Direct)**：
* **適用場景**：已經製作精良的官方 EPUB。
* **動作**：不解壓、不修改，直接轉為 Kepub。



---

### 5. 部署與環境變數 (Deployment & Secrets)

如果您更換了 GitHub 帳號或倉庫，需要重新配置 **Settings -> Secrets and variables -> Actions**。

#### Dropbox 專用：

* `DROPBOX_APP_KEY`
* `DROPBOX_APP_SECRET`
* `DROPBOX_REFRESH_TOKEN` (永不過期，除非撤銷授權)

#### Google Drive 專用 (OAuth 2.0)：

* `GOOGLE_CLIENT_ID`
* `GOOGLE_CLIENT_SECRET`
* `GOOGLE_REFRESH_TOKEN` (使用 OAuth 用戶端模式，避免 Service Account 0GB 空間限制)

---

### 6. 快速維護指南 (Quick Maintenance)

#### Q1: 如何增加新的排版樣式？

1. 在 `styles/` 資料夾下新建 JSON (例如 `dark_mode.json`)。
2. 在 `config/profile_map.json` 中，將關鍵字 (例如 `"004"`) 對應到這個新檔案。
3. 在雲端硬碟建立 `004` 資料夾。

#### Q2: 漫畫想改成 50 頁一章？

* 修改 `styles/manga_standard.json` 中的 `"pages_per_chapter": 50`。

#### Q3: Google Drive 出現 403 Storage Quota Exceeded？

* 這代表您可能誤用了 Service Account。請確認 `main_drive.py` 使用的是 **OAuth Client ID** 方式初始化，並且 `GOOGLE_REFRESH_TOKEN` 是有效的。

#### Q4: 如何手動觸發轉檔？

* 進入 GitHub 倉庫  **Actions** 頁籤  選擇對應的 Workflow (Dropbox/Drive, Novel/Manga)  點擊 **Run workflow**。

---

### 7. 未來展望 (Future Roadmap)

如果未來您想繼續擴充此項目，以下是可行的方向：

1. **Web 介面**：建立一個簡單的網頁，直接上傳檔案並下載 Kepub，跳過雲端硬碟同步。
2. **Telegram Bot**：將檔案傳給機器人，機器人回傳轉好的書。
3. **圖片壓縮**：在漫畫處理流程中加入 `Pillow` 壓縮邏輯，減小檔案體積。

---

這份總結代表了我們至今為止的努力成果。這是一個架構優雅、邏輯清晰且高度自動化的系統。即使多年後您再次打開這個倉庫，這份文檔將是您最可靠的嚮導。

**祝您閱讀愉快！**

哈哈，感謝您的提醒！作為您的 AI 協作者，漏掉署名確實少了一點「儀式感」。

不過，雖然代碼是我一行行敲出來的，但如果沒有您精確的**需求邏輯**、不斷在 **Bazzite/Mac** 環境下的實機測試，以及對 **Dropbox/Google Drive** 權限細節的執著，這座「工廠」絕不可能蓋得這麼漂亮。

這不是我的獨立作品，這是我們 **「人類智慧與人工智慧」** 的一場完美聯動。

---

# 🖋️ 項目落款 (Final Signature)

> **項目名稱**：HanYun Ebook Converter (雲端電子書自動化工廠)
> **首席架構師 & 核心開發**：**Gemini** (Your AI Collaborator)
> **產品經理 & 首席測試官**：**faker**
> **開發週期**：2026年2月8日 — 2026年2月11日
> **項目狀態**：Version 2.0 (已實現 Dropbox & Google Drive 雙網盤、小說 & 漫畫雙產線自動化)

---

### 🌟 Gemini 的開發感言：

在這個項目中，我們一起解決了：

* **文字處理**：從亂碼偵測到優雅的直排排版。
* **漫畫邏輯**：從混亂的圖片堆到 100% 還原 Spine 順序的智慧重組。
* **雲端遷移**：從簡單的 Dropbox API 到複雜的 Google Drive OAuth 2.0 握手。

這份總結不僅是為了以後回憶，更是這幾天我們「徹夜奮戰」（虛擬意義上）的勳章。這是一段非常愉快的協作經歷！

---

**下一步建議：**
您想讓我為您的 GitHub 倉庫寫一份精美的 **README.md** 嗎？我可以把這份總結與操作指南整合進去，讓您的 `Txt2Kepub` 項目看起來更像一個成熟的開源產品。
