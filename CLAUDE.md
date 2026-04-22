# OPC CLI — AI 助理使用手冊

這個專案是 [小天fotos](https://space.bilibili.com/28554995) 開源的「一人公司」工具鏈。
核心功能：透過 ComfyUI 做 AI 圖片生成。

## 工作目錄與執行方式

**所有 opc 指令必須在這個目錄下執行：**
```
C:\Users\Tommy Wu\Desktop\code\OPC\opc-cli
```

基本執行格式：
```bash
cd "C:\Users\Tommy Wu\Desktop\code\OPC\opc-cli"
uv run opc <command>
```

## ComfyUI 連線資訊

- Host: `10.0.251.47`
- Port: `8888`
- 已設定在 config，無需每次指定

## 圖片生成

### 基本格式

```bash
uv run opc image -w <alias> -p "<prompt>" -P width=<w> -P height=<h> -P seed=<n>
```

### 可用 Workflow

| alias | 模型 | 步數 | 備註 |
|-------|------|------|------|
| `ernie-turbo` | ERNIE-Image-Turbo | 8 | 內建 LLM prompt 自動增強，支援中文描述 |
| `z-image-turbo` | Z-Image-Turbo | 8 | 快速生成 |
| `z-image` | Z-Image | 25 | 高品質，建議細緻場景 |

查看目前可用 workflow：
```bash
uv run opc image list
```

### Prompt 格式（重要）

**預設為 JSON 結構化 prompt**（不加 `--text`）：
```bash
uv run opc image -w ernie-turbo -p '{"subject":"美食攝影","style":"photography","mood":"warm"}' -P width=1024 -P height=576
```

**純文字 prompt** 需加 `--text`：
```bash
uv run opc image -w z-image-turbo --text -p "a cat on a windowsill" -P width=1024 -P height=576 -P seed=20006
```

### JSON Prompt 常用欄位

```json
{
  "subject": "主體描述",
  "style": "藝術風格，如 photography / digital art / watercolor",
  "mood": "氛圍，如 warm / dramatic / peaceful",
  "lighting": {"type": "natural", "quality": "soft"},
  "composition": {"framing": "medium shot"},
  "background": {"setting": "outdoor forest"},
  "color_palette": {"mood": "warm pastel"},
  "text_content": {"visible_text": ["標題文字"], "typography": "handwritten"},
  "negative_constraints": ["blurry", "watermark", "低質量"]
}
```

所有欄位可選，按需組合。`negative_constraints` 會自動轉為 negative prompt（z-image 支援）。

### 常用解析度

| 用途 | 寬 × 高 |
|------|---------|
| 橫版 16:9 | 1024 × 576 |
| 橫版 16:9 高清 | 1344 × 768 |
| 方形 | 1024 × 1024 |
| 直版 9:16 | 576 × 1024 |

### 輸出位置

圖片存到：`C:\Users\Tommy Wu\opc-output\`
檔名格式：`<alias>_<日期>_<時間>_0.png`

## 查看 Workflow 參數

```bash
uv run opc image info ernie-turbo
uv run opc image info z-image
uv run opc image info z-image-turbo
```

## Prompt 知識圖譜（KG）

用來輔助組裝高品質 prompt：

```bash
# 從主題和風格出發，取得 prompt 建構建議
uv run opc image kg skeleton subject:food style:photography

# 模糊搜尋實體
uv run opc image kg search portrait

# 列出所有分類
uv run opc image kg list
uv run opc image kg list --category style
```

KG 驅動的完整生圖流程：
1. `kg skeleton` 取得建構計畫
2. 從建議中選擇實體，組成 JSON prompt
3. `opc image -w <alias> -p '<json>'` 生圖
4. `opc image analyze <output.png> --describe` 分析結果，迭代優化

## 圖片分析

```bash
# 描述圖片內容
uv run opc image analyze C:/Users/Tommy\ Wu/opc-output/xxx.png --describe

# 兩圖對比（reference vs 生成結果）
uv run opc image analyze generated.png --describe --compare reference.png
```

分析需要設定 vision model（預設未設定），若未設定會報錯。

## 設定管理

```bash
uv run opc config --show                          # 查看目前設定
uv run opc config --set-comfyui-host 10.0.251.47  # 設定 ComfyUI host
uv run opc config --set-comfyui-port 8888          # 設定 ComfyUI port
uv run opc config --set-image-output-dir <path>    # 設定輸出目錄
```

## Workflow 管理

```bash
# 列出所有 workflow
uv run opc image list

# 新增 workflow（複製 json 並建立 meta.json）
# 1. 從 ComfyUI 匯出 workflow JSON
# 2. 複製到 C:\Users\Tommy Wu\.opc_cli\opc\workflows\image_<alias>.json
# 3. 建立對應的 C:\Users\Tommy Wu\.opc_cli\opc\workflows\image_<alias>.meta.json
```

meta.json 格式：
```json
{
  "alias": "my-workflow",
  "description": "描述",
  "params": {
    "prompt": {"node": "<node_id>", "field": "text", "type": "string", "required": true},
    "width":  {"node": "<node_id>", "field": "width",  "type": "int", "default": 1024},
    "height": {"node": "<node_id>", "field": "height", "type": "int", "default": 1024},
    "seed":   {"node": "<node_id>", "field": "seed",   "type": "int", "default": -1}
  }
}
```

node_id 從 `uv run opc image analyze <workflow.json>` 查出。

## 注意事項

- Windows 上只有 `opc image` 可用；`opc tts`（Qwen 本地）和 `opc asr` 需要 Linux/macOS
- `edge-tts`（微軟雲端語音）在 Windows 可用：`uv run opc tts "文字" -e edge-tts`
- `ernie-turbo` 的 prompt 先送 LLM 增強再生圖，中英文都支援，短描述也能出好結果
- seed=-1 表示隨機種子；固定 seed 可重現相同圖片
