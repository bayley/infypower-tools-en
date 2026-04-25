# 开源化发布 — `infypower-tools` 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 `INFY_POWER` 工程包装成规范开源仓库，并以 `MisakaMikoto128/infypower-tools` (Public, GPL-3.0) 推送到 GitHub。

**Architecture:** 不重写代码，只做"包装"——加 README/LICENSE/CI/ISSUE_TEMPLATE/CONTRIBUTING/.gitkeep，删敏感证书 `build_sign.pfx`，改 `main.py` 里硬编码的作者姓名。所有改动落在 `feat/group-control-main` 分支，最后 merge 到 `main` 并首推。

**Tech Stack:** Bash / Git / gh CLI / Python 3.10+ / pytest / GitHub Actions (Windows runner) / Markdown。

**Spec:** `docs/superpowers/specs/2026-04-25-opensource-release-design.md`

---

## 文件 Map

| 动作 | 路径 | 责任 |
|---|---|---|
| 删除 | `build_sign.pfx` | 代码签名证书，永不能进公开仓库 |
| 修改 | `.gitignore` | 加 `*.pfx` 泛化保护 |
| 修改 | `main.py` | `ProfileCard` 姓名 `刘沅林` → `MisakaMikoto` |
| 修改 | `requirements.txt` | 移除 `pytest==9.0.3` |
| 创建 | `requirements-dev.txt` | 仅放开发依赖（`pytest`） |
| 创建 | `LICENSE` | GPL-3.0 全文 |
| 创建 | `CONTRIBUTING.md` | 短版贡献指引 |
| 创建 | `.github/workflows/ci.yml` | Windows runner + pytest |
| 创建 | `.github/ISSUE_TEMPLATE/bug_report.md` | bug 模板 |
| 创建 | `.github/ISSUE_TEMPLATE/feature_request.md` | 需求模板 |
| 创建 | `doc/screenshots/.gitkeep` | 截图占位（README 引用，用户后补图） |
| 创建 | `README.md` | 中英双语 + 6 徽章 |

---

## Task 1: 删除签名证书 + 加固 .gitignore

**Files:**
- Delete: `build_sign.pfx`
- Modify: `.gitignore`

- [ ] **Step 1: 确认 pfx 未进过 git 历史**

Run:
```bash
git log --all --oneline -- build_sign.pfx
git ls-files | grep -i pfx
```
Expected: 两条命令都无输出（说明从未被追踪，直接 `rm` 就够了）。

- [ ] **Step 2: 删除文件**

Run:
```bash
rm build_sign.pfx
```
Expected: 无输出，文件被删。

- [ ] **Step 3: `.gitignore` 把 `build_sign.pfx` 一行替换成泛化的 `*.pfx`**

修改 `.gitignore`，把这一行：
```
build_sign.pfx
```
替换为：
```
*.pfx
```

- [ ] **Step 4: 验证 .gitignore 仍然能匹配到 pfx**

Run:
```bash
git check-ignore -v *.pfx 2>&1 || echo "no pfx files in working tree (expected after rm)"
```
Expected: 输出 `no pfx files in working tree (expected after rm)` 或类似。

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: 删除签名证书并把 .gitignore 改为通配 *.pfx"
```

---

## Task 2: 修改 `main.py` ProfileCard 姓名

**Files:**
- Modify: `main.py`（约第 122-126 行的 `ProfileCard` 实例化）

- [ ] **Step 1: 定位字符串**

Run:
```bash
grep -n "刘沅林" main.py
```
Expected: 至少一行命中，类似 `122:        card = ProfileCard('resource/shoko.png', '刘沅林',`。

- [ ] **Step 2: 改名**

把 `main.py` 中的 `'刘沅林'` 替换为 `'MisakaMikoto'`。邮箱 `liuyuanlins@outlook.com` **保留不动**（用户决定）。

变更前：
```python
card = ProfileCard('resource/shoko.png', '刘沅林',
                   'liuyuanlins@outlook.com', menu)
```
变更后：
```python
card = ProfileCard('resource/shoko.png', 'MisakaMikoto',
                   'liuyuanlins@outlook.com', menu)
```

- [ ] **Step 3: 验证只改了这一处，没有别处遗留**

Run:
```bash
grep -n "刘沅林" main.py
grep -n "MisakaMikoto" main.py
```
Expected: 第一条命令无输出；第二条命令命中一行（且邮箱所在行未改）。

- [ ] **Step 4: 跑现有测试套件，确保没破坏什么**

Run:
```bash
pytest -q
```
Expected: 全绿（不依赖 main.py 的测试不该受影响）。

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "chore(main): ProfileCard 作者签名改为 MisakaMikoto"
```

---

## Task 3: 拆分 `requirements.txt` → `requirements-dev.txt`

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: 创建 `requirements-dev.txt`**

写入文件 `requirements-dev.txt`：
```
-r requirements.txt
pytest==9.0.3
```

- [ ] **Step 2: 从 `requirements.txt` 移除 `pytest`**

变更前（`requirements.txt` 当前内容）：
```
PyQt5==5.15.11
PyQt5-sip==12.18.0
PyQt-Fluent-Widgets[full]==1.8.6
PyQt5-Frameless-Window==0.7.3
pywin32==306
pytest==9.0.3
```
变更后：
```
PyQt5==5.15.11
PyQt5-sip==12.18.0
PyQt-Fluent-Widgets[full]==1.8.6
PyQt5-Frameless-Window==0.7.3
pywin32==306
```

- [ ] **Step 3: 验证 pytest 仍能跑（已在 .venv 中安装）**

Run:
```bash
pytest -q
```
Expected: 全绿。

- [ ] **Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "chore: 把 pytest 从 requirements.txt 拆到 requirements-dev.txt"
```

---

## Task 4: 写入 GPL-3.0 `LICENSE`

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: 拉取 GPL-3.0 全文**

Run:
```bash
curl -fsSL https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE
```
Expected: 无输出（成功）；`LICENSE` 文件大小约 35KB。

- [ ] **Step 2: 验证文件完整**

Run:
```bash
head -1 LICENSE
tail -3 LICENSE
wc -l LICENSE
```
Expected:
- 第一行：`                    GNU GENERAL PUBLIC LICENSE`
- 末尾几行包含 `<https://www.gnu.org/licenses/>` 字样
- 总行数约 674

如果 `head` 第一行不是 GPL 标题（比如 curl 失败抓到 HTML 错误页），删除 LICENSE 重试，或者用 PowerShell 备用方案：
```powershell
Invoke-WebRequest -Uri https://www.gnu.org/licenses/gpl-3.0.txt -OutFile LICENSE -UseBasicParsing
```

- [ ] **Step 3: Commit**

```bash
git add LICENSE
git commit -m "docs: 添加 GPL-3.0 LICENSE"
```

---

## Task 5: 创建 `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: 写入 CONTRIBUTING.md**

完整内容：

````markdown
# 贡献指南 / Contributing

感谢你考虑为 `infypower-tools` 做贡献！

## 报 issue / Report a bug

- 优先用 GitHub Issue 模板（bug report / feature request）
- bug 请附：复现步骤、CAN 设备型号、Windows 版本、Python 版本、报错日志
- 涉及具体协议命令（0x01–0x1F）的 bug，请贴抓到的 CAN 帧（id + 8 字节 data）

## 提 PR / Pull request

1. Fork → 新建分支：`feat/<topic>` 或 `fix/<topic>`
2. 沿用现有 commit 风格：
   - `feat(scope): 描述`
   - `fix(scope): 描述`
   - `refactor(scope): 描述`
   - `chore: 描述`
   - `test(scope): 描述`
   - `docs: 描述`
3. 改动若涉及协议解析 / 状态机，请在 `tests/` 加对应测试（参考 `tests/test_group_poller.py` 的写法和 `MockCAN` fixture）
4. 跑 `pytest -q` 全绿再发 PR
5. PR 描述里说明 **改了什么 / 为什么 / 怎么测的**

## 代码风格

- Python：跟随 PEP 8，遵循现有文件的缩进 / 命名 / 中文注释惯例
- UI 文案保持中文
- 避免引入新依赖，除非必要（依赖少的项目对终端用户友好）

## License

提交即视为同意以 GPL-3.0 协议发布你的贡献。
````

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: 添加 CONTRIBUTING.md"
```

---

## Task 6: 创建 GitHub Issue Templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`

- [ ] **Step 1: 创建 bug_report.md**

完整内容：

````markdown
---
name: Bug 报告 / Bug report
about: 报告一个能稳定复现的问题
labels: bug
---

## 现象 / What happened

<!-- 简要描述 -->

## 复现步骤 / Steps to reproduce

1.
2.
3.

## 期望行为 / Expected

## 实际行为 / Actual

## 环境 / Environment

- Windows 版本：
- Python 版本：
- USBCAN 设备型号 / 驱动版本：
- 充电模块型号 / 协议版本：
- 本仓库 commit hash：

## 日志 / 抓帧 / Logs

```
（粘贴报错堆栈、关键日志、CAN 帧）
```
````

- [ ] **Step 2: 创建 feature_request.md**

完整内容：

````markdown
---
name: 功能请求 / Feature request
about: 提出一个新功能想法
labels: enhancement
---

## 你想解决什么问题 / Problem

<!-- 不是描述功能，而是描述使用场景中遇到的痛点 -->

## 你期望的行为 / Proposal

<!-- 你设想的功能或改动 -->

## 备选方案 / Alternatives

<!-- 现有的 workaround 或者其它你想过的方案 -->

## 补充上下文 / Context

<!-- 截图、协议章节引用、相关 issue/PR 链接等 -->
````

- [ ] **Step 3: 验证目录结构**

Run:
```bash
ls -la .github/ISSUE_TEMPLATE/
```
Expected: 看到 `bug_report.md` 和 `feature_request.md` 两个文件。

- [ ] **Step 4: Commit**

```bash
git add .github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md
git commit -m "docs: 添加 GitHub Issue 模板（bug/feature）"
```

---

## Task 7: 创建 CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: 写入 ci.yml**

完整内容：

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: pip
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run tests
        run: pytest -q
```

- [ ] **Step 2: 本地干跑（可选）确保 yaml 合法**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```
Expected: `OK`（如果环境没装 PyYAML 就跳过这步，CI 自身会校验）。

- [ ] **Step 3: 验证 pytest 在本机能跑（CI 会做同样的事）**

Run:
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```
Expected: 全绿。

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: 添加 GitHub Actions（windows-latest + pytest）"
```

---

## Task 8: 截图占位目录

**Files:**
- Create: `doc/screenshots/.gitkeep`

> **注意**：用户已手工建了 `doc/screenshots/` 空目录（不是 `docs/`）。本任务用 `.gitkeep` 让该目录可以被 git 追踪。

- [ ] **Step 1: 创建 .gitkeep**

写入文件 `doc/screenshots/.gitkeep`，内容空（0 字节）即可。

Run:
```bash
touch doc/screenshots/.gitkeep
ls -la doc/screenshots/
```
Expected: 看到 `.gitkeep` 文件。

- [ ] **Step 2: Commit**

```bash
git add doc/screenshots/.gitkeep
git commit -m "docs(screenshots): 占位目录，README 引用 home/manual/chart 三张图"
```

---

## Task 9: 创建 README.md（中英双语）

**Files:**
- Create: `README.md`

> **注意：徽章和链接里的 `MisakaMikoto128/infypower-tools` 是仓库还没创建时的目标 URL。push 之后徽章会自动可达。**

- [ ] **Step 1: 写入 README.md**

完整内容：

````markdown
<div align="center">

# infypower-tools

[简体中文](#简体中文) · [English](#english)

[![License](https://img.shields.io/github/license/MisakaMikoto128/infypower-tools)](LICENSE)
[![CI](https://github.com/MisakaMikoto128/infypower-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/MisakaMikoto128/infypower-tools/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![UI](https://img.shields.io/badge/UI-PyQt%E2%80%91Fluent%E2%80%91Widgets-orange)
[![Stars](https://img.shields.io/github/stars/MisakaMikoto128/infypower-tools?style=social)](https://github.com/MisakaMikoto128/infypower-tools/stargazers)

</div>

---

## 简体中文

![home](doc/screenshots/home.png)

英飞源 INFYPOWER 充电模块（型号 **REG1K0100A2**，1000V / 100A / 30kW）的 Windows 桌面控制台。基于 PyQt-Fluent-Widgets，按厂家公开的 **CAN 通讯协议 V1.09** 实现，支持多组管理、模块级监控、实时图表，以及全协议命令的手动控制台。

### 功能特性

- **组级控制**：在最多 15 个组之间切换；一键开/关机、设输出电压/电流、Walk-In 使能、绿灯闪烁、模块休眠
- **模块表**：组内每模块的电压/电流/告警/休眠/绿灯状态实时刷新，支持 4 态生命周期（pending/online/offline/gone）
- **实时图表**：整组聚合 ↔ 单模块切换，N-动态量程，目标模块消失时自动重置
- **手动命令面板**：协议表 `0x01`–`0x1F` 全命令任发，参数对话框按命令定义自动生成
- **双 CAN 通道**：CAN1 / CAN2 活动徽章 + 链式 RX 解码（0x09 系统电压电流、0x04 模块状态、0x08 系统定点电压电流 等）
- **可配置**：`config.json` 调电压/电流量程、组数上限、轮询周期、模块超时阈值

### 截图

| 主页（多组聚合视图） | 手动命令面板 | 实时图表 |
|---|---|---|
| ![home](doc/screenshots/home.png) | ![manual](doc/screenshots/manual.png) | ![chart](doc/screenshots/chart.png) |

### 硬件要求

- 周立功 USBCAN-2A / USBCAN-II 系列板卡（依赖随包附带的 `ControlCAN.dll`）
- 一台或多台英飞源 **REG1K0100A2** 充电模块（其它沿用同一 CAN 协议 V1.09 的英飞源型号也理论可用，未实测）
- Windows 10 / 11，Python 3.10+

### 安装运行

```bash
pip install -r requirements.txt
python main.py
```

### 打包

仓库附带多套打包脚本：
- `build_nuitka.bat` / `build_nuitka_debug.bat` — Nuitka 编译
- `python build.py` — 自定义打包流程
- `make_package.bat` — 旧 PyInstaller 流程（main.spec）

### 协议参考

完整 CAN 协议规范见 [`doc/充电模块CAN通讯协议V1.09 20240510.md`](doc/充电模块CAN通讯协议V1.09%2020240510.md)（PDF 同目录）。

### 项目结构

```
.
├── main.py                # 应用入口（FluentWindow + 系统托盘）
├── home_widget.py         # 主页：多组聚合视图 + 模块表 + 实时图表
├── manual_widget.py       # 手动命令面板（协议 0x01–0x1F）
├── chart_widget.py        # RealtimeChart（整组 / 单模块切换）
├── module_table.py        # 组内模块表格 + 自定义 Delegate
├── group_state.py         # GroupState / ModuleState 数据类 + 4 态生命周期
├── group_poller.py        # 链式调度组级 + 模块级命令的 RX 解码轮询器
├── REG1K0100A2.py         # 协议层：发送 helper + RxEvent + listener
├── HDL_CAN.py             # 周立功 ControlCAN.dll 的 ctypes 封装
├── config_manager.py      # AppConfig 数据类 + JSON 加载
├── config.json            # 用户可编辑配置
├── tests/                 # pytest 单测（含 MockCAN fixture）
├── doc/                   # 协议 PDF/MD + 截图
└── requirements*.txt
```

### 测试

```bash
pip install -r requirements-dev.txt
pytest -q
```

测试不依赖 USBCAN 硬件，使用 `tests/conftest.py` 的 `MockCAN` fixture 注入。

### License

[GPL-3.0](LICENSE)

### 第三方版权声明

`ControlCAN.dll` 版权归 **广州周立功（致远电子）** 所有，本仓库为方便读者一键运行将其附带，并非授权再发布。如版权方有异议，请通过 GitHub Issue 或邮件联系作者，会在第一时间移除。读者也可自行从周立功官网下载对应版本驱动。

### 鸣谢

- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — 漂亮的 Fluent Design Qt 组件库
- 周立功 ControlCAN — USBCAN 设备 SDK
- 英飞源 INFYPOWER — 公开的 CAN 协议规范

---

## English

![home](doc/screenshots/home.png)

A Windows desktop console for **INFYPOWER REG1K0100A2** charging modules (1000V / 100A / 30kW), built with PyQt-Fluent-Widgets. Implements the vendor's published **CAN protocol V1.09**, with multi-group control, per-module monitoring, real-time charts, and a full-protocol manual command console.

### Features

- **Group-level control**: switch between up to 15 groups; one-click power on/off, set output V/I, Walk-In enable, green LED blink, module sleep
- **Module table**: live per-module V/I/alarms/sleep/LED state with a 4-state lifecycle (pending / online / offline / gone)
- **Real-time chart**: group aggregate ↔ single-module view, dynamic N-axis range, auto-reset on target module disappearance
- **Manual command panel**: send any protocol command `0x01`–`0x1F` with auto-generated parameter dialogs
- **Dual CAN channels**: CAN1 / CAN2 activity badges + chained RX decoding (0x09 system V/I, 0x04 module status, 0x08 system fixed-point V/I, etc.)
- **Configurable**: `config.json` controls V/I ranges, max group count, poll interval, module timeouts

### Screenshots

| Home (multi-group aggregate) | Manual console | Real-time chart |
|---|---|---|
| ![home](doc/screenshots/home.png) | ![manual](doc/screenshots/manual.png) | ![chart](doc/screenshots/chart.png) |

### Hardware

- ZLG USBCAN-2A / USBCAN-II adapter (uses the bundled `ControlCAN.dll`)
- One or more INFYPOWER **REG1K0100A2** modules (other INFYPOWER models implementing CAN protocol V1.09 should work in theory, untested)
- Windows 10 / 11, Python 3.10+

### Install & Run

```bash
pip install -r requirements.txt
python main.py
```

### Build

- `build_nuitka.bat` / `build_nuitka_debug.bat` — Nuitka compile
- `python build.py` — custom build flow
- `make_package.bat` — legacy PyInstaller flow

### Protocol Reference

See [`doc/充电模块CAN通讯协议V1.09 20240510.md`](doc/充电模块CAN通讯协议V1.09%2020240510.md) (PDF in the same folder).

### Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests don't need USBCAN hardware — they use a `MockCAN` fixture in `tests/conftest.py`.

### License

[GPL-3.0](LICENSE)

### Third-party Notice

`ControlCAN.dll` is © **Guangzhou ZLG (Zhiyuan Electronics)**. It is bundled here purely as a convenience for one-click reproducibility, NOT as a redistribution license. If the rights holder objects, please open an issue or email the author and it will be removed immediately. Readers may also download the driver from ZLG's official website.

### Acknowledgements

- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — beautiful Fluent Design Qt widgets
- ZLG ControlCAN — USBCAN device SDK
- INFYPOWER — public CAN protocol spec
````

- [ ] **Step 2: 验证 README 渲染**

Run:
```bash
head -20 README.md
wc -l README.md
```
Expected: 头部能看到 `# infypower-tools` 和徽章块；总行数 200+。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: 添加中英双语 README（徽章 + 截图占位 + 完整结构）"
```

---

## Task 10: 本地完整验证

**Files:** 无修改，只跑测试。

- [ ] **Step 1: 跑全套测试**

Run:
```bash
pytest -q
```
Expected: 全绿。如果有失败，回到对应 Task 修复，然后再跑这一步。

- [ ] **Step 2: 检查 main.py 能 import（不实际启动 GUI，避免硬件依赖）**

Run:
```bash
python -c "import sys; sys.path.insert(0, '.'); import config_manager, REG1K0100A2, HDL_CAN, group_state, group_poller, module_table; print('imports OK')"
```
Expected: `imports OK`。`main.py` 本身因为依赖 `ControlCAN.dll` + Qt 显示，不在这里 import。

- [ ] **Step 3: 检查工作树状态**

Run:
```bash
git status
git log --oneline -10
```
Expected:
- `git status` 显示干净（无未提交改动），分支仍是 `feat/group-control-main`
- `git log` 顶部 9 条是 Task 1–9 的 commit

---

## Task 11: 合并到 main

**Files:** 无新文件。

- [ ] **Step 1: 切到 main 分支**

Run:
```bash
git checkout main
```
Expected: `Switched to branch 'main'`。

- [ ] **Step 2: 确认 main 当前是干净的**

Run:
```bash
git status
git log --oneline -3
```
Expected: 干净，最新 commit 是 feat 分支分叉前的旧 commit。

- [ ] **Step 3: 合并 feat 分支**

Run:
```bash
git merge --no-ff feat/group-control-main -m "merge: 主页组控制 + 开源化发布"
```
Expected: 合并成功，没有冲突（因为 feat 分支是 main 的后裔）。

- [ ] **Step 4: 验证 main 上所有开源化文件都到位**

Run:
```bash
ls -1 LICENSE README.md CONTRIBUTING.md requirements-dev.txt
ls -1 .github/workflows/ci.yml .github/ISSUE_TEMPLATE/
ls -1 doc/screenshots/
```
Expected: 所有文件存在，`build_sign.pfx` 不存在。

Run:
```bash
test -f build_sign.pfx && echo "ERROR: build_sign.pfx still exists" || echo "OK: pfx deleted"
```
Expected: `OK: pfx deleted`。

---

## Task 12: 创建 GitHub 仓库 + 首推

**Files:** 无文件改动，纯 gh / git 操作。

> **前置条件：用户必须先重新登录 gh**。在用户的终端执行（这条是用户跑，不是 agent 跑）：
> ```
> ! gh auth login -h github.com
> ```

- [ ] **Step 1: 验证 gh 认证**

Run:
```bash
gh auth status 2>&1
```
Expected: `Logged in to github.com account MisakaMikoto128`，**没有** "token in keyring is invalid" 字样。
如果还失败，停下让用户重新登录，再继续。

- [ ] **Step 2: 创建仓库**

Run:
```bash
gh repo create MisakaMikoto128/infypower-tools \
  --public \
  --source=. \
  --remote=origin \
  --description "英飞源 INFYPOWER 充电模块（REG1K0100A2）桌面控制台：PyQt-Fluent UI + USBCAN，多组、实时图表、全协议手动命令"
```
Expected: 输出仓库 URL `https://github.com/MisakaMikoto128/infypower-tools`，且本地新增 `origin` remote。

- [ ] **Step 3: 验证 remote 已设置**

Run:
```bash
git remote -v
```
Expected: 看到 `origin  https://github.com/MisakaMikoto128/infypower-tools.git (fetch/push)`。

- [ ] **Step 4: 推 main 分支并设 upstream**

Run:
```bash
git push -u origin main
```
Expected: `Branch 'main' set up to track remote branch 'main' from 'origin'`，所有 commit 推完。

- [ ] **Step 5: 推 feat 分支（保留 PR 历史观感）**

Run:
```bash
git push -u origin feat/group-control-main
```
Expected: 推送成功。

- [ ] **Step 6: 添加 topics**

Run:
```bash
gh repo edit MisakaMikoto128/infypower-tools \
  --add-topic infypower \
  --add-topic charging-module \
  --add-topic can-bus \
  --add-topic usbcan \
  --add-topic pyqt5 \
  --add-topic pyqt-fluent-widgets \
  --add-topic power-electronics \
  --add-topic ev-charger \
  --add-topic windows \
  --add-topic desktop-app
```
Expected: `https://github.com/MisakaMikoto128/infypower-tools` 输出。

---

## Task 13: 推送后验收

**Files:** 无。

- [ ] **Step 1: 仓库元信息核对**

Run:
```bash
gh repo view MisakaMikoto128/infypower-tools --json name,visibility,description,licenseInfo,repositoryTopics
```
Expected JSON 中：
- `name = infypower-tools`
- `visibility = PUBLIC`
- `description` 非空且符合 spec
- `licenseInfo.spdxId = GPL-3.0`
- `repositoryTopics` 含 §2 的全部 10 个 topic

- [ ] **Step 2: CI 已被触发**

Run:
```bash
gh run list --repo MisakaMikoto128/infypower-tools --workflow ci.yml --limit 3
```
Expected: 至少一条记录（首次 push 触发）。状态为 `in_progress` 或 `queued` 或 `completed`。

- [ ] **Step 3: 等 CI 跑完看结果（可选，但建议）**

Run:
```bash
gh run watch --repo MisakaMikoto128/infypower-tools $(gh run list --repo MisakaMikoto128/infypower-tools --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```
Expected: 最终绿色 ✅。如果红了，看 `gh run view --log` 排查（windows runner 上 PyQt5 有时安装慢，但应该能装上）。

- [ ] **Step 4: 浏览器目检**

打印仓库 URL 给用户：
```bash
echo "https://github.com/MisakaMikoto128/infypower-tools"
```
让用户在浏览器打开核对：徽章渲染 / README 中英双语切换 / 截图占位 404（这是预期的，截图需用户后补）/ topics 显示。

- [ ] **Step 5: 列出后续待办（提示给用户）**

打印：
```
后续手动事项（非本 plan 范围）：
1. 截图：把 home.png / manual.png / chart.png 放到 doc/screenshots/，commit 推送
2. Social preview：GitHub web 端 Settings → Social preview 上传一张 1280×640 图（这一步 gh CLI 做不了）
3. （可选）创建 GitHub Discussions 接收用户反馈
4. （可选）发 v0.1.0 release，附带 Nuitka 打包好的 .exe
```

---

## Self-Review 笔记

✓ Task 1 删 pfx + 加固 .gitignore — 对应 spec §3.3 + 风险表
✓ Task 2 改名 — 对应 spec §3.2 main.py
✓ Task 3 拆 requirements — 对应 spec §3.2
✓ Task 4 GPL-3.0 LICENSE — 对应 spec §2 + §3.1
✓ Task 5 CONTRIBUTING — 对应 spec §3.1
✓ Task 6 Issue templates — 对应 spec §3.1
✓ Task 7 CI — 对应 spec §3.1 + §5
✓ Task 8 截图占位 — 对应 spec §3.1，**目录改为 `doc/screenshots/` 因用户已建该目录**
✓ Task 9 README — 对应 spec §3.1 + §4
✓ Task 10 本地验证 — 对应 spec §8.6
✓ Task 11 合并 main — 对应 spec §6 步骤 4
✓ Task 12 推送 + topics — 对应 spec §6 步骤 1-6
✓ Task 13 验收 — 对应 spec §8 全部

无 placeholder。所有命令可直接执行，所有文件内容完整。
