#!/usr/bin/env python3
"""
image_harness.py — AI 圖片生成自動 Harness

Flow:
  1. 用 Vision LLM 從參考圖逆推、或從文字描述擴展為 JSON prompt
  2. 用 opc image 生圖
  3. 用 Vision LLM 分析結果，給分 + 輸出改進後的 prompt
  4. 重複 2-3，直到品質達標或 max-round 到頂

Usage:
  # 從文字描述出發
  cd opc-cli
  uv run python ../image_harness.py --prompt "美食攝影，暖色調，日式風格"

  # 從參考圖出發（逆推 prompt 再生成）
  uv run python ../image_harness.py --image ../reference.png

  # 同時提供（文字描述 + 參考圖做評估對比）
  uv run python ../image_harness.py --prompt "美食攝影" --image ../reference.png --max-round 8

  # 指定 workflow 和解析度
  uv run python ../image_harness.py --prompt "..." --workflow z-image --width 1344 --height 768
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ── 設定（與 CLAUDE.md 一致） ─────────────────────────────────────────────
OPC_CLI_DIR = Path(__file__).parent / "opc-cli"
OUTPUT_DIR = Path.home() / "opc-output"
VISION_API_URL = "http://10.0.251.33:11434/v1/chat/completions"
VISION_MODEL = "qwen3.6:35b"
# ──────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是一個專業的 AI 圖片生成 prompt 工程師。
任務：設計能讓 ComfyUI（ernie-turbo / z-image）生成高品質圖片的結構化 JSON prompt。

輸出規則（重要）：
- 只輸出純 JSON，不加任何說明、標題或 markdown 符號
- 每個欄位盡量具體，避免空洞的抽象詞
- negative_constraints 一律用英文
- 其他欄位可中英文混用

JSON 格式（所有欄位均可選）：
{
  "subject": "主體具體描述",
  "style": "藝術風格（如 food photography / digital art / watercolor）",
  "mood": "氛圍（如 warm / dramatic / peaceful）",
  "lighting": {
    "type": "natural / neon / studio / dramatic",
    "quality": "soft / hard",
    "direction": "side / back / front"
  },
  "composition": {
    "framing": "close-up / medium shot / wide shot",
    "angle": "eye level / bird's eye / low angle"
  },
  "background": {
    "setting": "背景場景描述",
    "depth": "blurred / sharp"
  },
  "color_palette": {
    "dominant": ["顏色1", "顏色2"],
    "mood": "warm pastel / cool dramatic / vibrant"
  },
  "negative_constraints": ["blurry", "watermark", "low quality", "deformed"]
}
"""


def call_vision_llm(messages: list) -> str:
    payload = json.dumps({
        "model": VISION_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode()
    req = urllib.request.Request(
        VISION_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Vision LLM 連線失敗：{e}")
        print(f"  請確認 Ollama 服務在 {VISION_API_URL} 正常運作")
        sys.exit(1)


def encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def image_content(path: Path) -> dict:
    ext = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/{mime};base64,{encode_image(path)}"},
    }


def extract_json(text: str) -> dict:
    """從 LLM 回應中抽取 JSON，處理 markdown code block 包裝"""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"無法解析 LLM 回應為 JSON：\n{text[:400]}")


# ── 步驟 1：初始 prompt 生成 ─────────────────────────────────────────────

def prompt_from_image(image_path: Path) -> dict:
    """從參考圖逆推 JSON prompt"""
    print("  → 分析參考圖，逆推 JSON prompt...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            image_content(image_path),
            {"type": "text", "text": "分析這張圖，逆推出能生成類似效果的 JSON prompt。只輸出 JSON。"},
        ]},
    ]
    return extract_json(call_vision_llm(messages))


def prompt_from_text(user_text: str) -> dict:
    """從簡單文字描述擴展為 JSON prompt"""
    print("  → 根據描述生成初始 JSON prompt...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"根據以下需求，生成詳細的 JSON prompt：\n{user_text}\n\n只輸出 JSON。"},
    ]
    return extract_json(call_vision_llm(messages))


# ── 步驟 2：生圖 ──────────────────────────────────────────────────────────

def generate_image(workflow: str, json_prompt: dict, width: int, height: int) -> Path:
    """呼叫 opc image，回傳生成圖片路徑"""
    prompt_str = json.dumps(json_prompt, ensure_ascii=False)
    cmd = [
        "uv", "run", "opc", "image",
        "-w", workflow,
        "-p", prompt_str,
        "-P", f"width={width}",
        "-P", f"height={height}",
    ]
    result = subprocess.run(cmd, cwd=OPC_CLI_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n[ERROR] 生圖失敗：\n{result.stderr}")
        sys.exit(1)

    images = sorted(OUTPUT_DIR.glob(f"{workflow}_*.png"), key=lambda p: p.stat().st_mtime)
    if not images:
        print("[ERROR] 找不到輸出圖片，請確認 OUTPUT_DIR 設定")
        sys.exit(1)
    return images[-1]


# ── 步驟 3：分析 + 改進 ───────────────────────────────────────────────────

def analyze_and_improve(
    generated: Path,
    current_prompt: dict,
    threshold: int,
    reference: Optional[Path] = None,
) -> dict:
    """
    讓 Vision LLM 評分並給出改進 prompt。

    回傳格式：
      {"score": int, "done": bool, "reason": str}              # 達標時
      {"score": int, "done": bool, "improved_prompt": dict, "changes": str}  # 需改進時
    """
    content = [image_content(generated)]

    if reference:
        content.append(image_content(reference))
        compare_note = "第一張是生成結果，第二張是你的參考目標。請對比兩者。"
    else:
        compare_note = "這是生成結果。"

    content.append({"type": "text", "text": f"""\
{compare_note}

目前使用的 JSON prompt：
{json.dumps(current_prompt, ensure_ascii=False, indent=2)}

請評估生成品質，然後回傳以下格式的純 JSON（不加任何說明）：

品質達標（>= {threshold} 分）：
{{"score": <1-10>, "done": true, "reason": "<為什麼不需再改>"}}

需要改進：
{{"score": <1-10>, "done": false, "improved_prompt": {{...完整 JSON prompt...}}, "changes": "<本次修改了哪些維度及原因>"}}
"""})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    return extract_json(call_vision_llm(messages))


# ── 主程式 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI 圖片生成自動 Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--workflow", "-w", default="ernie-turbo",
                        choices=["ernie-turbo", "z-image-turbo", "z-image"],
                        help="Workflow alias（預設：ernie-turbo）")
    parser.add_argument("--prompt", "-p",
                        help="初始簡易描述，與 --image 至少提供一個")
    parser.add_argument("--image", "-i",
                        help="參考圖路徑（逆推 prompt 用，評估時也會做對比）")
    parser.add_argument("--max-round", "-r", type=int, default=5,
                        help="最大迭代次數（預設：5）")
    parser.add_argument("--width", type=int, default=1024,
                        help="圖片寬度（預設：1024）")
    parser.add_argument("--height", type=int, default=576,
                        help="圖片高度（預設：576）")
    parser.add_argument("--threshold", type=int, default=8,
                        help="停止品質閾值 1-10（預設：8）")
    args = parser.parse_args()

    if not args.prompt and not args.image:
        parser.error("需提供 --prompt 或 --image（至少一個）")

    reference = Path(args.image) if args.image else None
    if reference and not reference.exists():
        parser.error(f"找不到參考圖：{args.image}")

    print("=" * 60)
    print(f"  Workflow : {args.workflow}")
    print(f"  Size     : {args.width} × {args.height}")
    print(f"  Max round: {args.max_round}  |  品質門檻: {args.threshold}/10")
    if reference:
        print(f"  參考圖   : {reference}")
    print("=" * 60)

    # ── 步驟 1：初始 prompt ──
    print("\n[Step 1] 生成初始 JSON prompt")
    if reference and not args.prompt:
        current_prompt = prompt_from_image(reference)
    else:
        current_prompt = prompt_from_text(args.prompt)
        if reference:
            print("  (--image 提供，將在每輪評估時做對比)")

    print(f"  初始 prompt:\n{json.dumps(current_prompt, ensure_ascii=False, indent=2)}")

    # ── 主迴圈 ──
    final_image = None
    for round_num in range(1, args.max_round + 1):
        print(f"\n{'─' * 60}")
        print(f"  Round {round_num} / {args.max_round}")
        print(f"{'─' * 60}")

        # 生圖
        print("[Step 2] 生圖中...")
        final_image = generate_image(args.workflow, current_prompt, args.width, args.height)
        print(f"  輸出：{final_image.name}")

        # 分析
        print("[Step 3] Vision LLM 分析中...")
        try:
            result = analyze_and_improve(final_image, current_prompt, args.threshold, reference)
        except ValueError as e:
            print(f"  [WARN] 解析 LLM 回應失敗，跳過本輪：{e}")
            continue

        score = result.get("score", 0)
        done = result.get("done", False)
        print(f"  品質評分：{score}/10")

        if done or score >= args.threshold:
            reason = result.get("reason", "品質達標")
            print(f"\n{'=' * 60}")
            print(f"  ✅ 完成！{reason}")
            print(f"  最終圖片：{final_image}")
            print(f"  最終 prompt:\n{json.dumps(current_prompt, ensure_ascii=False, indent=2)}")
            print(f"{'=' * 60}")
            return

        if "improved_prompt" in result:
            changes = result.get("changes", "（無說明）")
            print(f"  改進方向：{changes}")
            current_prompt = result["improved_prompt"]
        else:
            print("  [WARN] LLM 未提供改進 prompt，使用原 prompt 繼續")

    print(f"\n{'=' * 60}")
    print(f"  ⏹ 已達最大迭代次數 {args.max_round}")
    if final_image:
        print(f"  最終圖片：{final_image}")
    print(f"  最終 prompt:\n{json.dumps(current_prompt, ensure_ascii=False, indent=2)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
