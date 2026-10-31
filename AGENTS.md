# 仓库工作规则

用户最新指令优先。完整目标见 [docs/PHASE_ONE.md](docs/PHASE_ONE.md)，迎战结算契约见
[docs/ENGAGE_SETTLEMENT.md](docs/ENGAGE_SETTLEMENT.md)，进度与当前证据见
[docs/HANDOFF.md](docs/HANDOFF.md)。完成状态以实际检查为准，不以文档措辞为准。

## 开始工作

- 阅读 README.md、docs/PHASE_ONE.md、docs/HANDOFF.md 与 docs/HEADLESS_TESTING.md；按任务读取
  相关源码、资产脚本与协议文档。
- 先检查工作区与 `git status`，保留用户已有改动；不明来源的改动不要覆盖。
- 在对话中说明本轮范围与不做项；已有实施授权时按依赖连续推进，不因内部分阶段反复请求授权。
- 本仓库不是可加载 Mod：当前只有资产、生产工具、规则参考与 M0 探针。不要用"已实现"描述
  尚未在游戏里验证的能力。

## 目标与边界

- 目标版本锁 StS2 **0.107.1 / 59260271**、Godot 4.5.1、.NET 9、RitsuLib 0.6.10
  Compat.0.107.1，领域 Tier 2。版本不符时部署必须拒绝，而不是"试试看"。
- 游戏程序集、反编译资料、测试存档、日志与本机路径不入 Git；不覆盖原版文件、普通存档或
  云端数据。
- 迎战必须保留真实敌人动作、吸收、完成响应与后续敌方阶段，不用意图数字模拟冒充等价实现；
  未通过 POC 前不声明可行性已验证。详见 docs/ENGAGE_SETTLEMENT.md。
- 雷伤、领域、卡牌数值以规则参考与已定稿文档为准，不凭方案文字重新定义；不支持的敌人行为
  记录为未支持，不称全覆盖。

## 目录约定

- `src/Volibear/`：C# Mod 探针与后续玩法实现，`tests/` 放 Python 契约与工具测试。
- `tools/`：开发入口（doctor/build/test/deploy/undeploy/run/logs、headless 运行器）。
  平台差异在工具内解析，不要求用户手工改脚本。
- `assets/`：动画、卡图、VFX、音频、UI 及其生产脚本；`reference/`：许可与规则参考；
  `docs/`：目标、契约、检查点。研究原文路径不伪造改写。
- `.local/`、`artifacts/`、`build` 输出、`node_modules`、`.venv` 均不入 Git。

## 实施与检查

- 先确定验收条件再改代码；不得通过删测试、放宽断言或跳过用例掩盖失败。
- 自动检查进入正式流程：`python -m unittest discover -s tests`；C# 用
  `python tools/dev.py build`；游戏内集成用 `python tools/headless.py`。
- 类型检查、编译成功或部署成功都不等于行为正确；符号存在不等于行为正确。未运行的用例
  如实标未执行。
- 验收证据分层：自动逻辑测试、构建与契约测试、真实游戏集成。报告注明提交号、脏工作区状态、
  游戏版本、实际命令与通过/失败/未执行。
- 不创建持久化验收报告、测试日志或哈希账本；测试结果在对话中报告，历史由 Git 保存。
  运行器在 `artifacts/` 下产生的单次报告是被忽略的临时产物。
- 引擎退出期泄漏必须与 `--nomods` 原生对照区分，不得直接删掉错误检查，也不得谎称退出干净。
- 资产脚本改动后重跑对应校验（`card_repo.py verify`、`validate_audio.py`、
  `official/build_catalog.py --check`），不修改已批准母图、导出字节或清单哈希去迁就实现。

## 完成或中断

- 完成前检查实际 diff，执行与改动相关的正式检查，并区分"通过"与"未执行"。
- 只有实际检查通过、相应要求满足，才把状态写为通过。
- 最终回复说明改动、测试结果和未完成部分；中断时在 docs/HANDOFF.md 保留精确下一步。
- Git 身份使用 fltb <fltbk@outlook.com>，提交前核对作者与提交者身份。
