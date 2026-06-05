#!/usr/bin/env python3
"""小石多端安装器 install.py

把 ria-helper 这个 skill 从「单一真相源」铺到各 AI 平台的 skills 目录，
解决「Claude Code 装了、Codex 用不了」这类单平台问题。

设计哲学（抄自 ui-ux-pro-max）：
- 单一真相源：本仓库根目录的 SKILL.md + scripts/ + reference/。
- 各平台只是真相源的「投影」+ 一个轻量入口，逻辑零重复。

用法：
    python3 scripts/install.py --ai claude   --target /path/to/project
    python3 scripts/install.py --ai codex    --target /path/to/project
    python3 scripts/install.py --ai cursor   --target /path/to/project
    python3 scripts/install.py --ai all      --target /path/to/project
    python3 scripts/install.py --ai claude   --global       # 装到家目录

不指定 --target 时默认安装到当前工作目录。
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SKILL_NAME = "ria-helper"

# 真相源里要铺出去的内容
SOURCE_ITEMS = ["SKILL.md", "scripts", "reference", "memory"]

# 平台 -> (项目内 skills 目录, 家目录 skills 目录)
PLATFORMS = {
    "claude": (".claude/skills", "~/.claude/skills"),
    "codex": (".codex/skills", "~/.codex/skills"),
    "cursor": (".cursor/skills", "~/.cursor/skills"),
    "windsurf": (".windsurf/skills", "~/.windsurf/skills"),
    "gemini": (".gemini/skills", "~/.gemini/skills"),
}

# 部分平台需要一个「轻入口」声明，指向 skill。键为平台，值为 (入口文件, 文本模板)
LIGHT_ENTRIES = {
    "codex": (
        "AGENTS.md",
        "\n## Skill: ria-helper（小石）\n"
        "拆解一个 skill 的工作逻辑时，读取并遵循 `.codex/skills/ria-helper/SKILL.md`。\n"
        "触发词：分析这个 skill / 拆解技能 / 它怎么工作 / 小石。\n",
    ),
}


def source_root() -> Path:
    # scripts/install.py 的上一级就是真相源根目录
    return Path(__file__).resolve().parent.parent


def copy_skill(src: Path, dest_dir: Path) -> None:
    skill_dir = dest_dir / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    for item in SOURCE_ITEMS:
        s = src / item
        if not s.exists():
            continue
        d = skill_dir / item
        if s.is_dir():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(s, d)
    print(f"  ✓ 已铺设 {skill_dir}")


def ensure_light_entry(platform: str, target: Path) -> None:
    if platform not in LIGHT_ENTRIES:
        return
    fname, snippet = LIGHT_ENTRIES[platform]
    f = target / fname
    existing = f.read_text(encoding="utf-8") if f.exists() else ""
    if "Skill: ria-helper" in existing:
        return  # 已声明，幂等
    f.write_text(existing + snippet, encoding="utf-8")
    print(f"  ✓ 已写入轻入口 {f}")


def install_one(platform: str, target: Path, use_global: bool, src: Path) -> None:
    proj_dir, global_dir = PLATFORMS[platform]
    if use_global:
        dest_dir = Path(global_dir).expanduser()
    else:
        dest_dir = target / proj_dir
    print(f"[{platform}]")
    copy_skill(src, dest_dir)
    if not use_global:
        ensure_light_entry(platform, target)


def main() -> None:
    ap = argparse.ArgumentParser(description="小石多端安装器")
    ap.add_argument("--ai", required=True,
                    choices=list(PLATFORMS) + ["all"],
                    help="目标平台，或 all")
    ap.add_argument("--target", default=".", help="目标项目根目录（默认当前目录）")
    ap.add_argument("--global", dest="use_global", action="store_true",
                    help="安装到家目录而非项目目录")
    args = ap.parse_args()

    src = source_root()
    if not (src / "SKILL.md").exists():
        raise SystemExit(f"[install] 真相源缺少 SKILL.md：{src}")

    target = Path(args.target).expanduser().resolve()
    platforms = list(PLATFORMS) if args.ai == "all" else [args.ai]

    print(f"真相源：{src}")
    print(f"目标：{'家目录' if args.use_global else target}\n")
    for p in platforms:
        install_one(p, target, args.use_global, src)

    print("\n完成。提示：")
    print("- 自动触发型平台（Claude/Cursor/Codex/Windsurf 等）靠 SKILL.md 的 description 触发。")
    print("- 只认斜杠命令的平台，可在其 commands 目录加 /ria-helper 指向同一 SKILL.md。")


if __name__ == "__main__":
    main()
