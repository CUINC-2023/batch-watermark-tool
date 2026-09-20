# Batch Watermark Tool Pro v5

由 CUverse 製作的 Windows 桌面圖片批次加工工具。v5 是以 Python 3.12、PySide6、Pillow、PyInstaller 重新架構的正式版產品線；v4 原始碼保留在 `legacy_v4/`，不與新版共用 UI 或影像流程。

## 目前版本

`5.0.0-alpha.1`（第一階段可執行核心框架）

已完成：

- PySide6 三欄桌面介面：左側縮圖、中央互動預覽、右側設定、底部固定導出列。
- 單張、多張、資料夾與拖曳匯入，支援 JPG、JPEG、PNG、WebP。
- 原圖／加工後切換與預覽更新合併。
- 可拖曳、四角調整的正規化視覺裁切框。
- Logo 九宮格、自由座標、平鋪、縮放、旋轉與透明度的共用影像核心。
- 文字浮水印、百分比尺寸、指定長邊、輸出品質與檔案大小限制。
- 指定輸出資料夾、原圖旁建立「加工後」、保留資料夾結構。
- EXIF／ICC Profile 傳遞、原子寫入、錯誤隔離、背景導出、Progress／Cancel。
- Preset 與多尺寸輸出的資料模型及服務層基礎。
- CUverse 官方 Logo 與「由 CUverse 製作」來源標示（不會加入使用者輸出圖片）。
- Python 3.12 測試與 Windows 免安裝 EXE GitHub Actions 流程。

下一階段：

- 中央預覽的 Logo 四角拖曳縮放、直接拖曳定位與旋轉控制點。
- Brand Preset／一般加工 Preset 的完整管理介面。
- 多尺寸規格編輯器、批次重新命名編輯器。
- 更完整的輸出摘要、錯誤日誌檢視器與大量圖片效能驗收。

## 架構

```text
ui/        PySide6 介面與互動預覽
core/      Preview／Export 共用 Image Pipeline
models/    設定與圖片資料模型
services/  匯入、輸出、Preset、錯誤日誌
workers/   背景批次工作
utils/     路徑、版本與共用工具
assets/    CUverse 製作來源品牌素材
tests/     核心與整合測試
legacy_v4/ 舊版封存
```

## 本機執行

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python main.py
```

測試：

```bash
.venv/Scripts/python -m compileall -q core models services ui workers utils main.py tests
.venv/Scripts/pytest -q
.venv/Scripts/python main.py --smoke-test
```

## Windows EXE

推送 `main`、`feature/**` 或 `release/**` 後，GitHub Actions 會：

1. 使用 Python 3.12 執行語法檢查、pytest 與 Pipeline smoke test。
2. 在 `windows-latest` 以 PyInstaller 建置 `BatchWatermarkToolProV5.exe`。
3. 實際啟動封裝後 EXE 執行 smoke test。
4. 上傳 `BatchWatermarkToolProV5-Windows` Artifact。

## 品牌來源

Batch Watermark Tool Pro 由 CUverse 製作。CUverse 品牌標示只存在於應用程式介面與「關於」資訊，不會自動套用到加工圖片。
