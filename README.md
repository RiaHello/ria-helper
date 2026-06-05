# RIA Helper · 小石学习搭子

一个 SKILL（提示词技能），不含前后端。

**小石**专门帮你看懂**一个 SKILL（技能）是怎么工作的**，只干一件事：

**拆 SKILL.md → 分阶段 → 理清每个阶段有哪些分支（为什么有 / 各解决什么问题 / 怎么解决）→ 用脚本画一张「阶段-分支图」并弹窗渲染 mermaid。**

核心信条：再花哨的 skill 也是积木拼大楼，小石帮你看清是哪几块积木拼的。

## 用法

技能定义在 [`SKILL.md`](SKILL.md)。触发：对智能体说「用小石分析 <github 地址>」。

采集目标 skill（输出更稳）：

```bash
python3 scripts/fetch_skill.py <github_url | owner/repo | 本地路径> --out .sdd/tmp/skill-bundle.md
```

出图并弹窗渲染：

```bash
python3 scripts/render_mermaid.py --in .sdd/tmp/diagram.mmd --title "小石：阶段-分支图"
```

## 多端安装（单一真相源 → 各平台投影）

本目录是唯一真相源。用安装器铺到各 AI 平台，解决「某端装了、另一端用不了」：

```bash
python3 scripts/install.py --ai claude --target /path/to/project
python3 scripts/install.py --ai codex  --target /path/to/project
python3 scripts/install.py --ai all    --target /path/to/project   # 一次铺所有
python3 scripts/install.py --ai claude --global                    # 装到家目录
```

Codex 会同时在目标项目 `AGENTS.md` 写一条轻入口（幂等）。

## 目录

- `SKILL.md`：技能本体（小石的分析逻辑与输出格式）—— 单一真相源
- `scripts/fetch_skill.py`：确定性采集器
- `scripts/render_mermaid.py`：mermaid 渲染 + 弹窗
- `scripts/install.py`：多端安装器
- `scripts/memory.py`：记忆库（list / index）
- `memory/`：每个分析过的 skill 的专属记忆 + `INDEX.md` 速查表
- `reference/skill-patterns.md`：常见 skill 模式词典
- `reference/example-report.md`：合格输出样板
- `.sdd/`：项目状态、经验、日志
- `AGENTS.md`：项目轻入口；核心规则在 Harness 根目录 `harness-core/`
