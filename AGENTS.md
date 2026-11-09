# 仓库工作规则

沃利贝尔 · StS2 Mod（BaseLib 接入）。玩法、数值与设计以用户最新裁决为准。

## 分支与提交

- 工作分支：`main`（原 `codex/mode7-completion` 已合并并回收）。
- Git 身份：`fltb <fltbk@outlook.com>`。
- 提交前检查 `git status` 与 diff，不提交游戏程序集、本机配置、存档、日志、产物或秘密。

## 构建与验证

| 依赖 | 版本 |
| --- | --- |
| Slay the Spire 2 | PBE 0.111.0 / 41cef1ea |
| Godot | 4.5.1 stable Mono/.NET |
| .NET SDK | 9.0.320 |
| BaseLib | 3.4.7 |

- 完整交付入口：`tools/local_delivery.py`。
- PBE 验收矩阵：`tools/pbe_verify.py`（需设 `VOLIBEAR_GAME_VERSION/COMMIT`）。
- 静态回归：`tools/regression.py`。

细节见 `README.md` 与 `docs/`。
