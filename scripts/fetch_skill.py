#!/usr/bin/env python3
"""小石采集器 fetch_skill.py

确定性地把一个 skill 的「主入口 + 被引用文件 + 目录树」打成一个 bundle，
供小石（ria-helper）做后续逻辑拆解。

设计目标：让「信息采集」这一步不再靠模型即兴抓取 —— 同一个 skill 每次采集到的
内容一致，从而让小石的输出稳定。

特性：
- 纯标准库，无第三方依赖。
- 不 git clone：GitHub 通过 HTTP API + raw 拉取；本地目录直接读。
- 按固定优先级定位主入口，自动顺着主入口里的引用再拉一层。

用法：
    python3 fetch_skill.py <github_url | owner/repo | 本地路径> [选项]

选项：
    --ref REF          分支/标签/commit（默认用仓库默认分支）
    --out FILE         输出到文件（默认 stdout）
    --token TOKEN      GitHub token（也可用环境变量 GITHUB_TOKEN，提升 API 限额）
    --max-files N      最多额外拉取的被引用文件数（默认 12）
    --max-bytes N      单文件内容截断字节数（默认 20000）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 主入口候选，按优先级从高到低
ENTRY_PRIORITY = [
    "SKILL.md",
    "skill.json",
    "router.md",
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
    "README",
]

# 可被当作「引用文件」拉取的扩展名
REF_EXTS = {
    ".md", ".mdc", ".py", ".json", ".csv", ".txt",
    ".yaml", ".yml", ".toml", ".js", ".ts", ".sh",
}

# 目录树里不展示的噪音
NOISE_DIRS = (".git/", "node_modules/", ".venv/", "venv/", "__pycache__/", "dist/", "build/")
NOISE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov", ".pdf",
    ".lock", ".pack", ".idx",
}


def is_noise(path: str) -> bool:
    if any(seg in path for seg in NOISE_DIRS):
        return True
    return Path(path).suffix.lower() in NOISE_EXTS

API_ROOT = "https://api.github.com"
RAW_ROOT = "https://raw.githubusercontent.com"
UA = "ria-helper-fetch-skill/1.0"


def _request(url: str, token: str | None = None, accept: str | None = None,
             timeout: int = 30, retries: int = 2) -> bytes:
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # 显式不继承环境代理，行为更可预测
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers=headers)
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with opener.open(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError:
            raise  # 业务层按状态码处理，不重试
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            last_err = e
    raise SystemExit(
        f"[fetch_skill] 网络读取超时/失败：{url}\n"
        f"  原因：{last_err}\n"
        f"  建议：检查网络/代理，或改用本地路径（先手动 clone 再传目录），或 --token 提升限额。"
    )


def parse_github_target(target: str):
    """返回 (owner, repo) 或 None。接受完整 URL 或 owner/repo。"""
    t = target.strip()
    t = re.sub(r"^git\+", "", t)
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?(?:/|$)", t)
    if m:
        return m.group(1), m.group(2)
    m = re.fullmatch(r"([\w.-]+)/([\w.-]+?)(?:\.git)?", t)
    if m:
        return m.group(1), m.group(2)
    return None


def truncate(text: str, max_bytes: int) -> str:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore") + "\n... [truncated]"


def extract_referenced_paths(content: str, tree_paths: set[str]) -> list[str]:
    """从主入口内容里找它引用的、且确实存在于仓库中的文件路径。"""
    candidates: list[str] = []
    # markdown 链接 [..](path)
    candidates += re.findall(r"\]\(([^)]+)\)", content)
    # 反引号内的路径
    candidates += re.findall(r"`([^`\n]+)`", content)
    # 裸路径（含斜杠、带扩展名）
    candidates += re.findall(r"(?<![\w/])([\w./-]+\.[a-zA-Z0-9]{1,5})", content)

    norm = []
    seen = set()
    for c in candidates:
        c = c.strip().split("#")[0].split("?")[0]
        c = c.lstrip("./").strip()
        if not c or c.startswith(("http://", "https://", "mailto:")):
            continue
        if Path(c).suffix.lower() not in REF_EXTS:
            continue
        # 在 tree 里精确匹配，或按文件名后缀匹配
        match = None
        if c in tree_paths:
            match = c
        else:
            for p in tree_paths:
                if p == c or p.endswith("/" + c):
                    match = p
                    break
        if match and match not in seen:
            seen.add(match)
            norm.append(match)
    return norm


def pick_entry(tree_paths: list[str]) -> str | None:
    best = None
    best_rank = (len(ENTRY_PRIORITY), 999)
    for p in tree_paths:
        name = p.split("/")[-1]
        if name in ENTRY_PRIORITY:
            depth = p.count("/")
            rank = (ENTRY_PRIORITY.index(name), depth)
            if rank < best_rank:
                best_rank = rank
                best = p
    return best


def fetch_github(owner: str, repo: str, ref: str | None, token: str | None,
                 max_files: int, max_bytes: int) -> str:
    token = token or os.environ.get("GITHUB_TOKEN")
    meta = {}
    try:
        meta = json.loads(_request(f"{API_ROOT}/repos/{owner}/{repo}", token))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SystemExit(f"[fetch_skill] 仓库不存在或非公开：{owner}/{repo}")
        if e.code in (403, 429):
            raise SystemExit("[fetch_skill] GitHub API 限额受限，请用 --token 或设 GITHUB_TOKEN。")
        raise SystemExit(f"[fetch_skill] 访问仓库失败：HTTP {e.code}")

    ref = ref or meta.get("default_branch") or "main"

    tree_data = json.loads(
        _request(f"{API_ROOT}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1", token)
    )
    tree_paths = [
        t["path"] for t in tree_data.get("tree", [])
        if t.get("type") == "blob" and not is_noise(t["path"])
    ]
    tree_set = set(tree_paths)

    entry = pick_entry(tree_paths)
    if not entry:
        raise SystemExit("[fetch_skill] 没找到主入口（SKILL.md/router.md/CLAUDE.md/README 等）。")

    def raw(path: str) -> str:
        return _request(f"{RAW_ROOT}/{owner}/{repo}/{ref}/{path}").decode("utf-8", "replace")

    entry_content = raw(entry)
    refs = extract_referenced_paths(entry_content, tree_set)[:max_files]

    out = []
    out.append(f"# SKILL BUNDLE: {owner}/{repo}")
    out.append("")
    out.append("## 仓库元信息")
    out.append(f"- repo: {owner}/{repo}")
    out.append(f"- ref: {ref}")
    out.append(f"- stars: {meta.get('stargazers_count', '?')}")
    out.append(f"- license: {(meta.get('license') or {}).get('spdx_id', '?')}")
    out.append(f"- language: {meta.get('language', '?')}")
    out.append(f"- pushed_at: {meta.get('pushed_at', '?')}")
    out.append(f"- description: {meta.get('description', '')}")
    out.append("")
    out.append(f"## 主入口（自动判定）：`{entry}`")
    out.append("")
    out.append("## 目录树（blob，最多 200 条）")
    out.append("```text")
    out += tree_paths[:200]
    if len(tree_paths) > 200:
        out.append(f"... 共 {len(tree_paths)} 个文件，已截断")
    out.append("```")
    out.append("")
    out.append(f"## 主入口内容：`{entry}`")
    out.append("```")
    out.append(truncate(entry_content, max_bytes))
    out.append("```")
    out.append("")
    out.append(f"## 被主入口引用的文件（共 {len(refs)} 个）")
    for p in refs:
        out.append("")
        out.append(f"### `{p}`")
        try:
            out.append("```")
            out.append(truncate(raw(p), max_bytes))
            out.append("```")
        except Exception as e:  # noqa: BLE001
            out.append(f"[拉取失败：{e}]")
    return "\n".join(out)


def fetch_local(root: Path, max_files: int, max_bytes: int) -> str:
    all_paths = [
        rel for p in root.rglob("*") if p.is_file()
        for rel in [str(p.relative_to(root)).replace(os.sep, "/")]
        if not is_noise(rel)
    ]
    tree_set = set(all_paths)
    entry = pick_entry(all_paths)
    if not entry:
        raise SystemExit("[fetch_skill] 本地目录里没找到主入口文件。")

    def read(rel: str) -> str:
        return (root / rel).read_text(encoding="utf-8", errors="replace")

    entry_content = read(entry)
    refs = extract_referenced_paths(entry_content, tree_set)[:max_files]

    out = [f"# SKILL BUNDLE (local): {root}", ""]
    out.append(f"## 主入口（自动判定）：`{entry}`")
    out.append("")
    out.append("## 目录树（最多 200 条）")
    out.append("```text")
    out += all_paths[:200]
    out.append("```")
    out.append("")
    out.append(f"## 主入口内容：`{entry}`")
    out.append("```")
    out.append(truncate(entry_content, max_bytes))
    out.append("```")
    out.append("")
    out.append(f"## 被主入口引用的文件（共 {len(refs)} 个）")
    for p in refs:
        out.append("")
        out.append(f"### `{p}`")
        out.append("```")
        out.append(truncate(read(p), max_bytes))
        out.append("```")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="小石采集器：把一个 skill 打成可分析的 bundle")
    ap.add_argument("target", help="GitHub URL / owner/repo / 本地路径")
    ap.add_argument("--ref", default=None, help="分支/标签/commit")
    ap.add_argument("--out", default=None, help="输出文件（默认 stdout）")
    ap.add_argument("--token", default=None, help="GitHub token")
    ap.add_argument("--max-files", type=int, default=12)
    ap.add_argument("--max-bytes", type=int, default=20000)
    args = ap.parse_args()

    local = Path(args.target).expanduser()
    if local.exists() and local.is_dir():
        bundle = fetch_local(local, args.max_files, args.max_bytes)
    else:
        gh = parse_github_target(args.target)
        if not gh:
            raise SystemExit(f"[fetch_skill] 无法识别目标：{args.target}（既不是本地目录，也不是 GitHub 地址）")
        bundle = fetch_github(gh[0], gh[1], args.ref, args.token, args.max_files, args.max_bytes)

    if args.out:
        Path(args.out).write_text(bundle, encoding="utf-8")
        print(f"[fetch_skill] 已写入 {args.out}（{len(bundle)} 字符）")
    else:
        sys.stdout.write(bundle)


if __name__ == "__main__":
    main()
