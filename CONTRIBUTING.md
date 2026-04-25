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
