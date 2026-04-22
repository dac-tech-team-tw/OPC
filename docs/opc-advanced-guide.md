# OPC CLI — 進階功能指南（Image）

> 基於實際程式碼驗證。TTS / ASR 不在此範圍。

---

## 功能可用性速查

| 功能 | 狀態 | 說明 |
|------|------|------|
| `opc image`（生圖） | ✅ 可用 | 需 ComfyUI 連線 |
| `opc image analyze --describe` | ✅ 可用 | 需設定 vision model |
| `opc image analyze --compare` | ✅ 可用 | 需設定 vision model |
| JSON prompt 驗證/轉換 | ✅ 可用 | 內建，無需額外設定 |
| Gallery（自動記錄生圖） | ✅ 可用 | 自動運作 |
| `opc image kg`（知識圖譜） | ❌ **會 crash** | 程式碼完整，但資料檔不存在 |
| Templates | ❌ 無效果 | 程式碼完整，但資料檔不存在 |

---

## 1. Vision Model 設定（analyze 前置）

`opc image analyze` 需要一個可以「看圖」的 multimodal model，透過 **OpenAI 相容 API** 呼叫。

```bash
uv run opc config --set-vision-api-url "http://10.0.251.33:11434/v1/chat/completions"
uv run opc config --set-vision-model "qwen3.6:35b"
uv run opc config --set-vision-api-key ""
```

> Ollama 的 OpenAI 相容 endpoint 是 `/v1/chat/completions`，不是 `/api/tags`（那個只是查 model 清單用的）

確認設定：

```bash
uv run opc config --show
```

---

## 2. opc image analyze

### 2.1 描述圖片（--describe）

```bash
uv run opc image analyze <圖片路徑> --describe
```

加自訂問題：

```bash
uv run opc image analyze photo.png --describe --prompt "這張圖的文字渲染清晰嗎？有哪些缺陷？"
```

預設會描述：主體、風格、構圖、光線、顏色、氛圍，並指出 AI 生圖的瑕疵。

**輸出格式：**

```json
{
  "description": "...",
  "comfyui_metadata": {
    "positive_prompt": "...",
    "seed": 12345,
    "steps": 8,
    "cfg": 1.0,
    "resolution": {"width": 1024, "height": 576}
  }
}
```

> `comfyui_metadata` 從 PNG 元數據自動抽取，只有 opc 生成的圖片才有

### 2.2 對比兩張圖（--compare）

```bash
uv run opc image analyze <生成圖> --describe --compare <參考圖>
```

範例：

```bash
uv run opc image analyze ~/opc-output/ernie-turbo_20260422_001.png --describe --compare reference.png
```

**注意參數順序：**
- 第一個位置引數是你要分析的**生成圖**
- `--compare` 後面是**參考目標圖**
- Vision model 會把「第一張」視為 generated attempt，「第二張（compare）」視為 reference/target

預設會輸出：兩圖差異、哪裡做對了、哪裡不符、相似度 1-10 分、具體改進建議。

---

## 3. JSON 結構化 Prompt

### 為什麼要用 JSON？

`opc image -p` **預設期望 JSON 格式**，純文字需加 `--text`。

小天的核心洞見：ernie-image 是 8B 模型，無法從一句話理解複雜構圖意圖；但若給一份精確描述每個維度的 JSON，模型對指令的遵循能力會大幅提升。

### 快速用法

```bash
uv run opc image -w ernie-turbo -p '{"subject":"美食攝影","style":"photography","mood":"warm"}' -P width=1024 -P height=576
```

### 完整欄位

所有欄位均可選，按需組合。簡單場景用字串，精細控制用物件。

```json
{
  "subject": {
    "main": "主體描述",
    "details": "細節（如動作、表情、服裝）",
    "count": 1,
    "position": "center of frame"
  },
  "style": {
    "medium": "photography / digital art / watercolor / oil painting",
    "techniques": ["macro", "bokeh"],
    "references": ["Studio Ghibli", "cyberpunk"],
    "era": "modern"
  },
  "composition": {
    "framing": "close-up / medium shot / wide shot / full body",
    "angle": "eye level / bird's eye / low angle",
    "depth_of_field": "shallow / deep"
  },
  "lighting": {
    "type": "natural / neon / studio / dramatic",
    "direction": "side / back / front",
    "quality": "soft / hard",
    "color_temperature": "warm / cool / neutral"
  },
  "background": {
    "setting": "outdoor forest / urban street / minimal studio",
    "details": "背景細節",
    "depth": "blurred / sharp"
  },
  "color_palette": {
    "dominant": ["#FF5733"],
    "accent": ["#FFC300"],
    "scheme": "monochromatic / complementary",
    "mood": "warm pastel / cool dramatic / vibrant"
  },
  "mood": "peaceful / dramatic / mysterious / joyful",
  "text_content": {
    "visible_text": ["標題", "副標"],
    "typography": "handwritten / bold sans-serif / serif",
    "language": "zh"
  },
  "layout": "頂部大標題，底部三欄並排圖文",
  "negative_constraints": ["blurry", "watermark", "低質量"]
}
```

> `negative_constraints` 在 z-image 自動轉為 negative prompt

### 進階欄位：typography_layout（中文排版 DSL）

專為中文文字排版設計，可精確控制每行的位置、顏色、樣式：

```json
{
  "typography_layout": {
    "style": "手寫體，清晰可讀",
    "lines": [
      {
        "position": "top",
        "segments": [
          {"text": "秋日味道", "color": "深棕", "style": "大號標題"}
        ]
      },
      {
        "position": "bottom_center",
        "segments": [
          {"text": "溫暖每一刻", "color": {"from": "橘紅", "to": "金黃", "direction": "從左到右"}}
        ]
      }
    ],
    "decorations": ["星星點綴", "落葉飄散"]
  }
}
```

`position` 可選值：`top` `second` `third` `middle` `center` `bottom` `bottom_center` `bottom_left` `bottom_right` `top_left` `top_right` `left` `right`

### 進階欄位：confrontation（對比構圖）

```json
{
  "confrontation": {
    "layout": "left_vs_right",
    "left": {"name": "健康飲食", "color": "綠色", "feel": "清新活力"},
    "right": {"name": "垃圾食品", "color": "紅色", "feel": "油膩沉重"}
  }
}
```

`layout` 可選：`left_vs_right`、`top_vs_bottom`

---

## 4. 知識圖譜（KG）

### 現況

**KG 程式碼完整，但資料檔不存在，目前無法使用。**

呼叫任何 `opc image kg` 指令都會 crash：

```
FileNotFoundError: No such file or directory: '...prompt_graph.json'
```

### 若要啟用 KG

需手動建立資料檔 `~/.opc_cli/opc/kg/prompt_graph.json`，最小格式：

```json
{
  "entities": {
    "style:photography": {
      "category": "style",
      "name": "photography",
      "count": 10
    }
  },
  "prompt_index": [
    {
      "id": "p001",
      "title": "Food Photography",
      "title_zh": "美食攝影",
      "tags": ["style:photography", "subject:food"],
      "prompt_short": "natural light food photo",
      "prompt_short_zh": "自然光美食照"
    }
  ],
  "co_occurrence": {
    "style:photography": {
      "lighting:natural": 8,
      "subject:food": 6
    }
  },
  "meta": {}
}
```

建立後，可用的指令：

```bash
uv run opc image kg list
uv run opc image kg list --category style
uv run opc image kg search food
uv run opc image kg skeleton subject:food style:photography
uv run opc image kg validate style:photography subject:food lighting:natural
uv run opc image kg similar subject:food style:photography
uv run opc image kg templates
```

`skeleton` 是核心：輸入幾個種子實體，自動推薦其他維度（lighting、composition 等）並給出參考 prompt。

---

## 5. 完整 Harness 流程（不依賴 KG 的版本）

目前 KG 無法用，但不影響主要流程：

```
步驟 1：構思 JSON prompt
  根據主題，手寫或讓 AI 幫忙組 JSON

步驟 2：生圖
  uv run opc image -w ernie-turbo -p '<json>' -P width=1024 -P height=576

步驟 3：分析結果
  uv run opc image analyze ~/opc-output/ernie-turbo_xxx.png --describe

步驟 4：有參考圖時做對比
  uv run opc image analyze generated.png --describe --compare reference.png

步驟 5：根據 analyze 輸出的建議修改 JSON prompt

步驟 6：回到步驟 2，迭代 3-5 次
```

### 多模型橫評（手動）

同一個 prompt 跑三個 workflow，再逐一分析：

```bash
uv run opc image -w ernie-turbo   -p '<json>' -P width=1024 -P height=576
uv run opc image -w z-image-turbo -p '<json>' -P width=1024 -P height=576
uv run opc image -w z-image       -p '<json>' -P width=1024 -P height=576

uv run opc image analyze ~/opc-output/ernie-turbo_xxx.png   --describe
uv run opc image analyze ~/opc-output/z-image-turbo_xxx.png --describe
uv run opc image analyze ~/opc-output/z-image_xxx.png       --describe
```

---

## 6. 三個 Workflow 比較

| | `ernie-turbo` | `z-image-turbo` | `z-image` |
|--|---------------|-----------------|-----------|
| 步數 | 8 | 8 | 25 |
| 速度 | 快 | 快 | 慢 |
| negative_prompt | ❌ | ❌ | ✅ |
| 內建 LLM 增強 | ✅ Ministral-3B | ❌ | ❌ |
| 中文描述 | ✅ | △ | △ |
| 最適場景 | 中文 / 快速迭代 | 英文快速抽卡 | 高精度最終輸出 |

---

## 7. Gallery

每次生圖後自動記錄到 `~/.opc_cli/opc/gallery.json`，不需要手動操作。

格式：

```json
{
  "images": [
    {
      "id": "g_abc123",
      "filename": "ernie-turbo_20260422_120000_0.png",
      "filepath": "/Users/.../opc-output/...",
      "prompt": "{...}",
      "alias": "ernie-turbo",
      "created_at": "2026-04-22T12:00:00Z",
      "file_size": 245678,
      "width": 1024,
      "height": 576
    }
  ]
}
```
