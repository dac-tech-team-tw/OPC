# OPC CLI — opc image 研究指南

> 基於 [小天fotos](https://space.bilibili.com/28554995) Bilibili「一人公司」系列的開源工具鏈研究筆記。

---

## 1. 專案是什麼

**OPC（One Person Company）** 是小天fotos 開源的「一人公司」工具鏈，核心模組：

| 模組 | 功能 | Windows |
|------|------|---------|
| `opc image` | AI 圖片生成（via ComfyUI） | ✅ |
| `opc tts` | 語音合成（Qwen 本地） | ❌ 需 Linux/macOS |
| `opc tts -e edge-tts` | 語音合成（微軟雲端） | ✅ |
| `opc asr` | 語音辨識 | ❌ 需 Linux/macOS |

圖片生成完全走 HTTP 呼叫 ComfyUI，與本地 GPU 無關，Windows 完全可用。

---

## 2. 工作原理

```
opc-cli (Python)
  └─ 讀取 workflow alias（-w）+ prompt（-p）+ 參數（-P）
  └─ inject_params：把參數注入 ComfyUI workflow JSON
  └─ POST /prompt → ComfyUI（HTTP API）
  └─ 輪詢 /history 等待完成
  └─ 下載圖片 → 存到輸出目錄
```

影片示範指令：

```bash
uv run opc image -w ernie-full -p "PROMPT" -P width=1024 -P height=576 -P seed=20006
```

---

## 3. 初始化步驟

### 3.1 安裝依賴

```bash
cd opc-cli
uv sync
uv run opc image --help  # 確認正常
```

### 3.2 連線 ComfyUI

```bash
uv run opc config --set-comfyui-host 10.0.251.47
uv run opc config --set-comfyui-port 8888
uv run opc config --set-image-output-dir ~/opc-output
```

### 3.3 載入 Workflow

Workflow 檔案不在 git 倉庫裡，需從 ComfyUI 匯出後放入：

```
~/.opc_cli/opc/workflows/
  image_<alias>.json       ← ComfyUI 匯出的 workflow
  image_<alias>.meta.json  ← 參數描述（需手動建立）
```

已設定好的三個 workflow（meta.json 在 `commfyui_workflows/`）：

| alias | 模型 | 步數 | 特色 |
|-------|------|------|------|
| `ernie-turbo` | ERNIE-Image-Turbo | 8 | 內建 LLM 自動增強 prompt，支援中文 |
| `z-image-turbo` | Z-Image-Turbo | 8 | 快速生成，Lumina2 架構 |
| `z-image` | Z-Image | 25 | 高品質，支援 negative_prompt |

---

## 4. Prompt 格式

### JSON 結構化（預設，推薦）

```bash
uv run opc image -w ernie-turbo -p '{"subject":"美食攝影","style":"photography","mood":"warm"}' -P width=1024 -P height=576
```

常用欄位：

```json
{
  "subject": "主體描述",
  "style": "photography / digital art / watercolor",
  "mood": "warm / dramatic / peaceful",
  "lighting": {"type": "natural", "quality": "soft"},
  "composition": {"framing": "medium shot"},
  "background": {"setting": "outdoor forest"},
  "color_palette": {"mood": "warm pastel"},
  "negative_constraints": ["blurry", "watermark"]
}
```

> `negative_constraints` 會自動轉為 negative prompt（z-image 支援）

### 純文字（加 --text）

```bash
uv run opc image -w z-image-turbo --text -p "a cat on a windowsill" -P width=1024 -P height=576 -P seed=42
```

---

## 5. 常用解析度

| 用途 | 寬 × 高 |
|------|---------|
| 橫版 16:9 | 1024 × 576 |
| 橫版 16:9 高清 | 1344 × 768 |
| 方形 | 1024 × 1024 |
| 直版 9:16 | 576 × 1024 |

---

## 6. Workflow 參數注入機制

`inject_params` 會根據 `meta.json` 的 node mapping，把 `-P key=value` 寫入 workflow JSON 對應的節點欄位：

```json
{
  "params": {
    "prompt": {"node": "88:94", "field": "value", "type": "string", "required": true},
    "width":  {"node": "88:71", "field": "width",  "type": "int", "default": 1024},
    "seed":   {"node": "88:70", "field": "seed",   "type": "int", "default": -1}
  }
}
```

- `node`：ComfyUI 節點 ID（格式 `<group>:<node>`）
- `field`：節點 inputs 中的欄位名
- `type`：自動型別轉換（string / int / float）
- `seed=-1`：執行時替換為隨機整數

---

## 7. ernie-turbo 特殊架構

ernie-turbo 有內建 LLM prompt 增強器（Ministral-3B），pipeline 如下：

```
使用者 prompt（node 88:94）
  └─ StringReplace × 3（填入 width/height）
  └─ TextGenerate（Ministral-3B LLM 增強）
  └─ ComfySwitchNode（可開關增強）
  └─ CLIPTextEncode
  └─ KSampler（8步，Flux2架構）
```

因此短句或中文描述也能出好結果，LLM 會自動擴寫細節。

---

## 8. 已知問題與修復

### `opc image import` 子命令失效

**問題**：`opc.py` 中 `cmd_image` 判斷 `image_action == "import_wf"`，但 argparse 實際上給的是 `"import"`，導致 import 指令永遠走到 generate 路徑並報錯。

**修復**（`opc-cli/scripts/opc.py`）：

```python
# 原本
elif image_action == "import_wf":
# 修復後
elif image_action in ("import_wf", "import"):
```

**臨時繞過方案**：手動複製 workflow JSON 到 `~/.opc_cli/opc/workflows/`。

---

## 9. Prompt 知識圖譜（KG）

```bash
# 從主題/風格取得 prompt 建構建議
uv run opc image kg skeleton subject:food style:photography

# 模糊搜尋實體
uv run opc image kg search portrait

# 列出所有分類
uv run opc image kg list --category style
```

推薦工作流：`kg skeleton` → 組 JSON prompt → `opc image -w` 生圖 → `opc image analyze` 分析 → 迭代優化。
