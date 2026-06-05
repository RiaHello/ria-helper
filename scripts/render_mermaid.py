#!/usr/bin/env python3
"""小石出图器 render_mermaid.py

把一段 mermaid 代码渲染成图，并**弹窗显示**（用系统默认浏览器打开）。

设计：生成一个内嵌 mermaid.js 的自包含 HTML，写到文件后用浏览器打开 —— 不依赖
任何第三方 Python 包，跨平台。需要联网加载 mermaid.js（首次后浏览器会缓存）。

用法：
    python3 render_mermaid.py --in diagram.mmd --title "小石：XX 的阶段-分支图"
    echo 'flowchart TD; A-->B' | python3 render_mermaid.py
    python3 render_mermaid.py --in diagram.mmd --no-open   # 只生成 HTML 不弹窗

输入可带 ```mermaid 围栏，会自动剥掉。
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import webbrowser
from pathlib import Path

HTML_TEMPLATE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body { margin:0; font-family:-apple-system,system-ui,sans-serif; background:#0f1115; color:#e6e6e6; }
  header { padding:14px 20px; border-bottom:1px solid #262a33; font-size:15px; font-weight:600; }
  .wrap { padding:24px; display:flex; justify-content:center; }
  .mermaid { background:#fff; border-radius:12px; padding:24px; max-width:100%; overflow:auto; }
  .err { color:#ff8a8a; padding:20px; white-space:pre-wrap; font-family:monospace; }
</style>
</head>
<body>
<header>__TITLE__</header>
<div class="wrap"><pre class="mermaid">__DIAGRAM__</pre></div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "default" });
</script>
</body>
</html>
"""


def strip_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="把 mermaid 渲染成图并弹窗显示")
    ap.add_argument("--in", dest="infile", default=None, help="mermaid 文件（缺省读 stdin）")
    ap.add_argument("--title", default="小石出图", help="窗口标题")
    ap.add_argument("--out", default=None, help="输出 HTML 路径（缺省用临时文件）")
    ap.add_argument("--no-open", action="store_true", help="只生成不弹窗")
    args = ap.parse_args()

    if args.infile:
        diagram = Path(args.infile).read_text(encoding="utf-8")
    else:
        diagram = sys.stdin.read()
    diagram = strip_fences(diagram)
    if not diagram:
        raise SystemExit("[render_mermaid] 没有收到 mermaid 内容。")

    html = (HTML_TEMPLATE
            .replace("__TITLE__", args.title)
            .replace("__DIAGRAM__", diagram))

    if args.out:
        out = Path(args.out).expanduser().resolve()
    else:
        fd = tempfile.NamedTemporaryFile(
            prefix="shier-mermaid-", suffix=".html", delete=False
        )
        out = Path(fd.name)
        fd.close()
    out.write_text(html, encoding="utf-8")
    print(f"[render_mermaid] 已生成：{out}")

    if not args.no_open:
        opened = webbrowser.open(out.as_uri())
        if opened:
            print("[render_mermaid] 已在默认浏览器弹窗显示。")
        else:
            print(f"[render_mermaid] 未能自动弹窗，请手动打开：{out}")


if __name__ == "__main__":
    main()
