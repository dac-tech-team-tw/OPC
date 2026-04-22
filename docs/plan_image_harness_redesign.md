# Plan: image_harness.py 重設計

## Context

現有 `image_harness.py` 是單模型、單輪分析的雛形。
使用者想要：多模型橫比 + 結構化輸出報告 + 平行生圖 + 正確的 JSON prompt 指引。
核心目標：最終能生出品質最好的圖、輸出非工程師也能看懂的比較報告。

> **注意**：此 plan 在 Phase 1 驗證 opc flow 有效後才實作。
> 見 `docs/session_20260422.md` 了解決策脈絡。

---

## 確認的技術細節

- `opc image -o <dir>` → 設定**輸出目錄**（非檔名），會覆蓋 config 的 `image_output_dir`
- 實際存檔路徑：`{output_dir}/{workflow}_{YYYYMMDD_HHMMSS}_{index}.png`（見 comfyui.py L92）
- `generate_image()` Python API 有 `filename_prefix` 參數，但 CLI 只能設目錄

---

## 設計決策

### 1. 執行架構：多模型比較（非單模型迭代）

每輪用**同一個 JSON prompt**跑全部選定的模型，讓 Vision LLM 橫比所有結果再出改進建議。
這能同時回答「哪個模型最適合這個風格」和「prompt 要怎麼改」。

### 2. 平行生圖：ThreadPoolExecutor

用 `concurrent.futures.ThreadPoolExecutor` 同時提交多個 `uv run opc image`。
ComfyUI 有自己的佇列，GPU 仍循序處理，但省去等待 HTTP response 的閒置時間。
每個 thread 將輸出目錄設為 run 的 `images/` 子目錄，workflow 名稱不同不會撞名。
subprocess 回傳後立即把 `{workflow}_*.png` rename 為 `round_{N:02d}_{model}.png`。

### 3. 輸出目錄結構

```
output/
└── {prompt_slug}_{YYYYMMDD_HHmi}/
    ├── images/
    │   ├── round_01_ernie-turbo.png
    │   ├── round_01_z-image-turbo.png
    │   ├── round_01_z-image.png
    │   └── ...
    ├── report.md       # 每輪結束後即更新，可即時預覽
    └── session.json    # 機器可讀的完整 run 數據
```

- `prompt_slug`：取 prompt 前 30 字元，空白換底線，去除特殊符號
- 預設 output 根目錄：腳本所在目錄的 `./output/`（可用 `--output-dir` 覆蓋）

### 4. Vision LLM 分析：單次呼叫比較全部模型

每輪把所有模型的輸出圖片（+參考圖，若有）打包成一個 Vision LLM 呼叫。
讓 LLM 一次給出：每個模型的評分、最佳模型、是否達標、下一輪的改進 prompt。
比逐一分析更省 API 呼叫次數，且能做真正的跨模型比較。

分析結果格式（LLM 輸出的 JSON）：
```json
{
  "scores": {"ernie-turbo": 7, "z-image-turbo": 5, "z-image": 8},
  "best_model": "z-image",
  "done": false,
  "improved_prompt": { },
  "changes": "調整了光線方向和構圖，加強前景細節",
  "reason": ""
}
```

### 5. System Prompt：從 references/image.md 動態載入

只讀取 `## JSON Prompt 格式（默认格式）` 到 `## 图片分析` 之間的段落（約 200 行）。
避免把 CLI 指令、KG 說明等無關內容注入 LLM。
讀取時機：腳本啟動時一次性載入，所有 LLM 呼叫共用。

### 6. 報告格式（report.md）

每輪結束後 append，使用者可在瀏覽器或 VS Code 即時查看進度：

```markdown
# 生圖 Harness 報告

- 初始描述：美食攝影
- 參考圖：reference.png（若有）
- 執行時間：2026-04-22 15:30
- 品質門檻：8/10

---

## Round 1

**JSON Prompt：**
{ ... }

| ernie-turbo | z-image-turbo | z-image |
|:-----------:|:-------------:|:-------:|
| ![](images/round_01_ernie-turbo.png) | ![](images/round_01_z-image-turbo.png) | ![](images/round_01_z-image.png) |
| ⭐ 7/10 | 5/10 | **8/10 🏆** |

**最佳模型：** z-image
**分析：** 光線柔和，但前景細節不足...
**改進方向：** 調整 lighting.direction，加強 subject.details

---
## 最終結果

**達標！** Round 2，z-image，9/10
**最終圖片：** images/round_02_z-image.png
```

---

## CLI 介面

```bash
# 基本用法（從文字描述出發，跑全部3個模型）
cd opc-cli
uv run python ../image_harness.py --prompt "美食攝影，日式風格"

# 從參考圖逆推
uv run python ../image_harness.py --image ../reference.png

# 指定模型子集
uv run python ../image_harness.py --prompt "..." --workflow ernie-turbo z-image

# 完整參數
uv run python ../image_harness.py \
  --prompt "美食攝影" \
  --image ../ref.png \
  --workflow ernie-turbo z-image-turbo z-image \
  --max-round 5 \
  --width 1024 --height 576 \
  --threshold 8 \
  --output-dir ../output
```

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `--prompt / -p` | — | 初始文字描述（與 --image 至少一個） |
| `--image / -i` | — | 參考圖（逆推 prompt 用，評估時做對比） |
| `--workflow / -w` | 全部3個 | 可多選 |
| `--max-round / -r` | 5 | 最大輪數 |
| `--width` | 1024 | — |
| `--height` | 576 | — |
| `--threshold` | 8 | 1-10，達到即停止 |
| `--output-dir` | `./output` | run 目錄的上層 |

---

## 關鍵檔案

| 檔案 | 角色 |
|------|------|
| `OPC/image_harness.py` | **完整重寫** |
| `OPC/opc-cli/references/image.md` | 只讀，動態載入 JSON prompt 指引 |
| `OPC/opc-cli/scripts/image/comfyui.py` | 確認 `-o` 行為（不修改） |
| `~/.opc_cli/opc/config.json` | 確認 vision API 設定（不修改） |

---

## 模組結構（單檔）

```
image_harness.py
├── load_json_prompt_guide()        # 從 references/image.md 擷取 JSON 段落
├── build_run_dir(prompt, output_dir) → Path
├── call_vision_llm(messages) → str
├── extract_json(text) → dict
├── encode_image(path) → str (base64)
├── image_content(path) → dict (OpenAI format)
│
├── prompt_from_image(ref_path, guide) → dict
├── prompt_from_text(text, guide) → dict
│
├── generate_one(workflow, prompt, width, height, run_dir, round_num) → Path
│   # subprocess + rename
├── generate_all_parallel(workflows, ...) → dict[model → Path]
│   # ThreadPoolExecutor
│
├── analyze_all(results, current_prompt, threshold, reference) → dict
│   # 單次 Vision LLM 呼叫，比較全部模型
│
├── init_report(run_dir, args) → None
├── append_round(run_dir, round_num, prompt, results, analysis) → None
├── finalize_report(run_dir, done_info) → None
│
└── main()
```

---

## 驗證方式

1. `uv run python ../image_harness.py --prompt "測試" --max-round 1 --workflow ernie-turbo`
   - 確認 `output/` 目錄建立、圖片命名正確、report.md 生成
2. `uv run python ../image_harness.py --prompt "美食" --max-round 2`
   - 確認 3 個模型平行執行、report.md 有比較表格
3. `uv run python ../image_harness.py --image reference.png --max-round 3 --threshold 7`
   - 確認逆推 prompt、對比評分、提早達標時正確停止
