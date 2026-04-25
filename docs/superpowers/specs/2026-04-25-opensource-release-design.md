# 开源化发布设计 — `infypower-tools`

**日期**：2026-04-25
**目标仓库**：`MisakaMikoto128/infypower-tools` （Public，GPL-3.0）
**作者**：MisakaMikoto128

## 1. 背景与目标

当前工程目录名 `INFY_POWER`，以本地工具方式开发，未发布过。需要把它包装成"看起来正经、容易拿 star"的开源项目并推到 GitHub。

**目标人群**：在搜 `infypower / 英飞源 / REG1K0100A2 / 充电模块 / USBCAN / CAN 协议 V1.09` 等关键词的同行工程师（充电桩、储能、电源行业），以及对 PyQt-Fluent-Widgets 桌面应用感兴趣的 Python GUI 开发者。

**非目标**：
- 不重写代码、不重构架构。本次只做"包装"。
- 不引入英文化代码（注释、变量名、UI 文案保持中文）。
- 不做版本发布（v1.0.0、CHANGELOG、release artifacts），首推先把仓库立起来。

## 2. 仓库元信息

| 项 | 值 |
|---|---|
| 仓库 | `MisakaMikoto128/infypower-tools` |
| 可见性 | Public |
| Description | `英飞源 INFYPOWER 充电模块（REG1K0100A2）桌面控制台：PyQt-Fluent UI + USBCAN，多组、实时图表、全协议手动命令` |
| License | GPL-3.0 |
| Topics | `infypower` `charging-module` `can-bus` `usbcan` `pyqt5` `pyqt-fluent-widgets` `power-electronics` `ev-charger` `windows` `desktop-app` |
| 默认分支 | `main` |
| Homepage | （留空） |

**分支策略**：当前在 `feat/group-control-main`。开源化改动也在这条分支上做完，最后合并到 `main` 再 push。第一次 push 用 `git push -u origin main`，之后再推 feat 分支无所谓。

## 3. 文件清单

### 3.1 新增

| 文件 | 用途 |
|---|---|
| `README.md` | 中英双语，结构详见 §4 |
| `LICENSE` | GPL-3.0 全文（GitHub `gh repo create --license gpl-3.0` 也会自动加，但本地写一份更可控） |
| `CONTRIBUTING.md` | 短版：issue 模板、PR 流程、commit message 风格沿用现有的 `feat:/fix:/refactor:/chore:/test:/docs:` |
| `.github/workflows/ci.yml` | `windows-latest` + Python 3.10 + `pytest` |
| `.github/ISSUE_TEMPLATE/bug_report.md` | bug 报告模板 |
| `.github/ISSUE_TEMPLATE/feature_request.md` | 功能请求模板 |
| `docs/screenshots/.gitkeep` | 占位目录，README 引用 `home.png` / `manual.png` / `chart.png`，**用户后补图** |
| `requirements-dev.txt` | 把 `pytest` 拆出来（不是开发者不需要装） |

### 3.2 修改

| 文件 | 改动 |
|---|---|
| `main.py` | `ProfileCard('resource/shoko.png', '刘沅林', 'liuyuanlins@outlook.com', menu)` → 姓名改为 `'MisakaMikoto'`，邮箱保留 `liuyuanlins@outlook.com`（用户决定） |
| `.gitignore` | 加 `*.pfx` 一行（已有 `build_sign.pfx`，泛化更稳） |
| `requirements.txt` | 移除 `pytest==9.0.3`（迁到 `requirements-dev.txt`） |

### 3.3 删除

| 文件 | 原因 |
|---|---|
| `build_sign.pfx` | 代码签名证书，永不能进公开仓库。**已确认从未进过 git 历史（.gitignore 一直在拦），直接 `rm` 即可，无需 rewrite history。** |

### 3.4 保留（用户已决定）

- `ControlCAN.dll`（周立功闭源 SDK）— 保留以便开箱即用。README 顶部写第三方版权声明。
- `FluentQtTest.py` / `FluentQtTest.ui` — 保留。
- `BMSDataType.py` — 保留。
- `main.spec` — 保留。
- `resource/shoko.png` — 保留（作者头像）。
- `liuyuanlins@outlook.com` 邮箱 — 保留（用户作者签名）。

## 4. README 结构

**布局**：顶部一行语言切换，简体中文在前，English 紧随其后。锚点 `#简体中文` `#english`。

**徽章一行**（紧贴标题下方）：
- `![License](https://img.shields.io/github/license/MisakaMikoto128/infypower-tools)`
- `![CI](https://github.com/MisakaMikoto128/infypower-tools/actions/workflows/ci.yml/badge.svg)`
- `![Python](https://img.shields.io/badge/python-3.10%2B-blue)`
- `![Platform](https://img.shields.io/badge/platform-Windows-blue)`
- `![PyQt-Fluent](https://img.shields.io/badge/UI-PyQt%E2%80%91Fluent%E2%80%91Widgets-orange)`
- `![Stars](https://img.shields.io/github/stars/MisakaMikoto128/infypower-tools?style=social)`

**正文章节**（中英文各一份，结构相同）：

1. 顶部抢眼截图（`docs/screenshots/home.png`，占位，用户后补）
2. 一句话定位 ：英飞源 INFYPOWER 充电模块（REG1K0100A2）的桌面控制台，PyQt-Fluent UI + USBCAN，支持多组管理、实时图表、按官方 CAN 协议 V1.09 实现的全命令手动控制台。
3. **功能特性**（要点列表）
   - 组级控制：在最多 15 个组之间切换；一键开/关机、设输出电压/电流、Walk-In 使能、绿灯闪烁、模块休眠
   - 模块表：组内每模块的电压/电流/告警/休眠/绿灯状态实时刷新
   - 实时图表：整组聚合 ↔ 单模块切换，自动 N-动态量程
   - 手动命令面板：协议表 `0x01`–`0x1F` 全命令任发，参数对话框自动生成
   - 双 CAN 通道：CAN1/CAN2 活动徽章 + 链式 RX 解码（0x09 / 0x04 / 0x08 等）
   - 配置：`config.json` 可调电压/电流量程、组数上限、轮询周期、模块超时时间
4. **截图**（3 张：主页 / 手动命令 / 实时图表，占位）
5. **硬件要求**
   - 周立功 USBCAN-2A / USBCAN-II 系列板卡（依赖 `ControlCAN.dll`）
   - 一台或多台英飞源 REG1K0100A2 充电模块（其他英飞源型号若沿用同一 CAN 协议 V1.09 也理论可用）
   - Windows 10 / 11，Python 3.10+
6. **安装运行**
   ```
   pip install -r requirements.txt
   python main.py
   ```
7. **打包**：`build_nuitka.bat` / `python build.py` （引用现有脚本）
8. **协议参考**：链接到 `doc/充电模块CAN通讯协议V1.09 20240510.md` 和 `doc/...pdf`
9. **项目结构**（一个目录树 + 每个模块一行说明）
10. **测试**：`pytest`
11. **License**：GPL-3.0
12. **第三方版权声明**：`ControlCAN.dll` 版权归周立功（致远电子）所有，本仓库为方便读者一键运行附带，如有版权方异议请提 issue 或邮件作者，会立刻移除。
13. **鸣谢**：[PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) / 周立功 ControlCAN

## 5. CI 设计

`.github/workflows/ci.yml`：

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
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest -q
```

**已知限制**：CI 跑不了 `main.py`（需要 `ControlCAN.dll` + 实际 USBCAN 设备），只跑 `tests/`（已有 `MockCAN` 不依赖硬件）。

## 6. 推送流程

1. 在当前分支 `feat/group-control-main` 上完成所有改动 + 一个或多个 commit
2. 用户跑 `gh auth login -h github.com` 重新登录（**当前 token 已失效**）
3. `gh repo create MisakaMikoto128/infypower-tools --public --source=. --remote=origin --description "英飞源 INFYPOWER ..."`
4. `git checkout main && git merge --no-ff feat/group-control-main`（本地 `main` 分支已存在，无需 -b）
5. `git push -u origin main` （以及 `git push -u origin feat/group-control-main` 把 feat 分支也推上去，对外可见 PR 历史更自然）
6. `gh repo edit --add-topic infypower --add-topic charging-module ...`
7. （可选，用户自己做）GitHub web 上传 social preview 图

## 7. 风险 & 已知遗留

| 风险 | 处置 |
|---|---|
| `ControlCAN.dll` 版权 | README 顶部注明第三方版权 + 联系移除渠道。用户自负风险。 |
| `liuyuanlins@outlook.com` 公开邮箱被爬虫抓取 | 用户已选择保留。可后续随时改 no-reply 邮箱。 |
| `feat/group-control-main` 分支当前 commit 历史里包含未发布的私有提交（无敏感信息但风格散） | 不 squash，保留原始 commit 历史，开源后这部分对路人是中性的。 |
| 截图缺失 | `docs/screenshots/.gitkeep` 占位，README 用相对路径引用。**首推会顶部少图**——用户接受。 |
| 首推无 CI 通过记录 | push 触发 CI 后徽章会变绿。第一次访问可能短暂红/灰。 |

## 8. 验收标准

执行完本 spec + 后续 plan 后应满足：

1. `gh repo view MisakaMikoto128/infypower-tools` 显示 public + GPL-3.0 + 设定的 description
2. README 中英双语，徽章一行 6 个全部渲染（CI 徽章在 push 后会变绿/红）
3. `gh repo view --json topics` 含 §2 的 10 个 topic
4. 仓库根目录无 `build_sign.pfx`
5. `gh run list --workflow ci.yml --limit 1` 能看到至少一次 CI 运行
6. `pytest` 在本地仍然通过（改动不破坏现有测试）
7. 启动 `python main.py`，右键菜单的 ProfileCard 显示 `MisakaMikoto` 而非 `刘沅林`

## 9. 范围外（明确不做）

- 不写 CHANGELOG.md
- 不发 GitHub Release
- 不上传 social preview（需要用户在 web 端操作）
- 不做仓库 Wiki / Discussions 设置
- 不写英文版的代码注释或 docstring
- 不重命名工作目录 `INFY_POWER`（GitHub 仓库名和本地目录名解耦，本地保持原状）
- 不动现有 `doc/` 目录下的协议 PDF/MD（只在 README 里链接它）
