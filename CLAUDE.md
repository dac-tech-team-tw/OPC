# OPC CLI — AI 助理使用手冊

這個專案是 [小天fotos](https://space.bilibili.com/28554995) 開源的「一人公司」工具鏈。

## 執行環境

**所有 opc 指令必須在這個目錄下執行：**

```bash
cd "C:\Users\Tommy Wu\Desktop\code\OPC\opc-cli"
uv run opc <command>
```

## 連線資訊

| 服務 | Host | Port | 備註 |
|------|------|------|------|
| ComfyUI（生圖） | `10.0.251.47` | `8888` | 已設定在 config |
| Vision LLM（圖片分析） | `10.0.251.33` | `11434` | Ollama，OpenAI 相容 API |

**Vision LLM 可用 model：** `qwen3.6:35b`、`gemma4:31b`

Vision LLM 初次設定（只需一次）：
```bash
uv run opc config --set-vision-api-url "http://10.0.251.33:11434/v1/chat/completions"
uv run opc config --set-vision-model "qwen3.6:35b"
uv run opc config --set-vision-api-key ""
```

## 文件索引

| 文件 | 內容 |
|------|------|
| `docs/opc-image-guide.md` | workflow 初始化、參數注入機制、ernie-turbo pipeline |
| `docs/opc-advanced-guide.md` | analyze、KG、JSON prompt 格式、完整 Harness 流程 |
| `opc-cli/SKILL.md` | AI agent skill 定義（觸發詞、快速指令）|
| `opc-cli/references/image.md` | JSON prompt 所有欄位、AI Agent 5 階段 SOP |

## 注意事項

- Windows 上只有 `opc image` 可用；`opc tts`（Qwen 本地）和 `opc asr` 需要 Linux/macOS
- KG（知識圖譜）功能目前**無資料檔**，直接呼叫 `opc image kg` 會 crash，需先建立 `~/.opc_cli/opc/kg/prompt_graph.json`
- `ernie-turbo` prompt 會先送內建 Ministral-3B LLM 增強再生圖，中英文短描述都支援
- `seed=-1` 表示隨機種子；固定 seed 可重現相同圖片
- 圖片輸出位置：`C:\Users\Tommy Wu\opc-output\`
