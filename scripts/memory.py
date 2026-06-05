#!/usr/bin/env python3
"""小石记忆库 memory.py

为每个分析过的 skill 维护一份专属记忆，存在 memory/<id>.md。
每份记忆必须记三件事：
  1. skill 的名称与流程；
  2. skill 的流程与关键节点（用结构化字段存，方便脚本提取对比）；
  3. 用户这次讨论最多的内容（用户的最深记忆）。

记忆文件格式（memory/<id>.md）——结构化字段在 frontmatter：

    ---
    id: ui-ux-pro-max
    name: UI UX Pro Max
    source: github.com/nextlevelbuilder/ui-ux-pro-max-skill
    flow: 请求 > 多域检索 > 推理引擎 > 输出设计系统 > 生成代码 > 交付前校验
    nodes: 多域并行检索(5库); BM25推理引擎; 交付前清单门禁; CLI多端适配
    patterns: 真相源+适配; 脚本+数据引擎; 两种激活模式
    concepts: 161 Reasoning Rules; BM25; Master+Overrides
    deep_memory: 用户最关心“如何多端适配，解决 Codex 用不了”
    ---
    （正文：阶段-分支摘要，自由书写）

约定：
- flow 用 ` > ` 连接阶段，机器可解析。
- nodes / patterns / concepts 用 `;` 分隔。

命令：
    python3 scripts/memory.py list             # 打印全部历史记忆
    python3 scripts/memory.py list --brief      # 只打印 frontmatter 摘要
    python3 scripts/memory.py index             # 重建 memory/INDEX.md
    python3 scripts/memory.py compare [--exclude <id>]
        # 提取所有历史 skill 的【流程 + 关键节点 + 最深记忆】，供结尾做对比分析
"""
from __future__ import annotations

import argparse
from pathlib import Path

MEM_DIR = Path(__file__).resolve().parent.parent / "memory"

STRUCT_FIELDS = ["flow", "nodes", "patterns", "concepts", "deep_memory"]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
    return meta, body


def load_records() -> list[tuple[Path, dict, str]]:
    if not MEM_DIR.exists():
        return []
    out = []
    for p in sorted(MEM_DIR.glob("*.md")):
        if p.name == "INDEX.md":
            continue
        meta, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        out.append((p, meta, body))
    return out


def cmd_list(brief: bool) -> None:
    records = load_records()
    if not records:
        print("[memory] 记忆库为空（还没分析过 skill）。这会是第一条记忆。")
        return
    print(f"[memory] 共 {len(records)} 条历史记忆：\n")
    for p, meta, body in records:
        print(f"=== {meta.get('id', p.stem)} | {meta.get('name', '')} ===")
        for f in STRUCT_FIELDS:
            print(f"{f}: {meta.get(f, '?')}")
        if not brief:
            print(body.strip())
        print()


def cmd_compare(exclude: str | None) -> None:
    records = [r for r in load_records() if r[1].get("id") != exclude]
    if not records:
        print("[memory] 没有可对比的历史 skill（记忆库为空或只有当前这个）。")
        print("结论提示：这是第一个分析的 skill，先存档，后续才能横向对比。")
        return
    print(f"[memory] 历史 skill 的流程 + 关键节点（共 {len(records)} 个，供对比分析）：\n")
    for _p, meta, _body in records:
        print(f"### {meta.get('id','')} | {meta.get('name','')}")
        print(f"- 流程: {meta.get('flow', '?')}")
        print(f"- 关键节点: {meta.get('nodes', '?')}")
        print(f"- 模式积木: {meta.get('patterns', '?')}")
        print(f"- 用户最深记忆: {meta.get('deep_memory', '?')}")
        print()
    print("---")
    print("对比要求：把当前 skill 的【流程】逐阶段、【关键节点】逐个与上面对照，")
    print("找出最相似的一个，说清流程哪几段同构、哪个节点≈哪个节点、关键区别，给出结论。")


def cmd_index() -> None:
    records = load_records()
    lines = ["# 小石记忆库索引", "", f"共 {len(records)} 条。", "",
             "| id | 名称 | 流程 | 关键节点 | 用户最深记忆 |",
             "|----|------|------|----------|--------------|"]
    for _p, meta, _body in records:
        lines.append(
            f"| {meta.get('id','')} | {meta.get('name','')} "
            f"| {meta.get('flow','')} | {meta.get('nodes','')} "
            f"| {meta.get('deep_memory','')} |"
        )
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    (MEM_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[memory] 已重建 {MEM_DIR / 'INDEX.md'}（{len(records)} 条）")


def main() -> None:
    ap = argparse.ArgumentParser(description="小石记忆库")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="打印历史记忆")
    p_list.add_argument("--brief", action="store_true", help="只打印摘要")
    sub.add_parser("index", help="重建 INDEX.md")
    p_cmp = sub.add_parser("compare", help="提取历史流程+关键节点供对比")
    p_cmp.add_argument("--exclude", default=None, help="排除某个 id（通常是当前正在分析的）")
    args = ap.parse_args()

    if args.cmd == "list":
        cmd_list(args.brief)
    elif args.cmd == "index":
        cmd_index()
    elif args.cmd == "compare":
        cmd_compare(args.exclude)


if __name__ == "__main__":
    main()
