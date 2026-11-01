# 沃利贝尔 · StS2 Mod 工作区

代码 GPL-3.0-only；原创资产与文档 CC-BY-SA-4.0。第三方例外见 [LICENSING.md](LICENSING.md)。当前已有可编译、可加载的开发候选，包含 89 张卡的 178 个基础／升级牌面及 2 个遗物；**尚未完成完整机制、全部敌人行为与普通窗口流程验收，不是完成品**。

完整实施目标与验收条件分别见 [实施计划](docs/OVERNIGHT_PLAN.md) 和 [测试规格](docs/TEST_SPEC.md)，游戏状态、转换条件及单元测试映射见 [状态机设计](docs/GAMEPLAY_STATE_MACHINES.md)，当前边界与接续工作见 [交接说明](docs/HANDOFF.md)。构建成功、受控原生场景通过及程序化 UI 操作，均不能替代普通鼠标键盘流程或完整分支覆盖。

## 开始

```sh
git clone git@github.com:fltb/sts2-volibear-mod.git
cd sts2-volibear-mod
```

Git 跟踪完整生产路径，不需要 ZIP restore；同内容文件由 Git 对象存储去重。可直接打开 `assets/cards/cards/index.html` 和 `assets/animation/animations/skeletal_v9/index.html`。预留至少 2 GB。官方 Riot 录音不纳入 Git，也不属于当前运行 cue 依赖。

## 迎战与领域：完整覆盖仍是验收门

必须保留真实敌人动作、吸收、完成响应及后续敌方阶段的正确结算，不能用意图数字模拟冒充等价实现。当前已有调度实现和限定场景的真实引擎验证，但不能扩写成所有敌人动作、状态转移或领域交互均已通过。

**先读 [迎战结算架构与验收门](docs/ENGAGE_SETTLEMENT.md)**；未执行、未支持和失败的分支必须保留，不能以历史研究中的乐观概括代替实际检查。

## 唯一有效版本

- 动画：2026-10-31 当前 V9，含用户直接编辑的双脚与近膝曲线。运行入口 `assets/animation/animations/clean/manifest.json`；制作权威 `assets/animation/animations/skeletal_v9/parts/`。26 序列、940 帧。**已有游戏内资源加载与限定表现回执验证，仍未完成本版逐帧艺术审核；自动音频事件回执不代表人耳听感验收**。
- 卡图：当前 V7 加 10-30 四卡修订（B01/C12/U36/T02），89 张、26 固定、63 重绘。当前审稿与母图/导出绑定；不使用旧 V7 ZIP。`assets/cards/data/asset_manifest.json` 是图像入口。
- VFX、音频、UI：`assets/animation/` 中对应目录。卡图仓同内容路径是兼容别名，不是另一套资产版本。
- 卡图仓的 cards_source 是旧美术语义，不是玩法数值权威。玩法以 `reference/bear-forge` 当前实现及其定稿文档、`docs/research/sts2-mod-research/content-cards.json` 为参考，旧方案的路径与版本描述是历史快照。

## 目录

- `assets/animation/`：当前动画、制作部件/源/脚本、VFX、音频、UI、未编译接入示例。
- `assets/cards/`：当前卡图、四种游戏格式导出、制作输入/编辑祖先、提示词、审稿与离线图库。STS1 导出作为现有生产管线的验证依赖保留；StS2 接入只使用 production/sts2。
- `reference/art/`：研究和许可资料，不是替代最终资产。
- `reference/bear-forge/`：规则参考源码与本地改动快照，剔除环境、构建、Git、缓存及归档。不是已移植的 StS2 Mod。
- `docs/research/`：原五份方案、机读数据和提取脚本，原文历史路径未伪造改写。
- `docs/ENGAGE_SETTLEMENT.md`：迎战结算决策与待执行 POC 验收。原本地迁移报告不作为 Git 当前完整性清单。

## 继续生产

Python 图像工具依赖 Pillow、NumPy、SciPy、fonttools；按各目录 requirements 安装到新的虚拟环境。音频需要 ffmpeg/ffprobe；浏览器自动测试需 Node 与 Playwright/Chromium。不携带旧电脑 node_modules 或虚拟环境。

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
python -m pip install Pillow numpy scipy fonttools
python assets/cards/scripts/card_repo.py verify
# 重导出卡图（会更新副本中的导出和技术报告）
python assets/cards/scripts/card_repo.py rebuild
# V9 动画重导出：耗时操作，使用现有用户部件，不重建 parts
python assets/animation/animations/skeletal_v9/scripts/export.py
python assets/animation/animations/skeletal_v9/scripts/export_clean.py
python assets/animation/animations/skeletal_v9/scripts/refresh_viewer.py
```

Windows 另需四点：脚本按 UTF-8 读写，须设 `PYTHONUTF8=1`；`ffmpeg`/`ffprobe` 要在 PATH 上；
克隆后确认换行未被转换（全局 `core.autocrlf=true` 会破坏清单里的字节级 SHA 校验，仓库已带
`* -text` 的 `.gitattributes`，本仓库仍需 `git config core.autocrlf false`）；不要用微软商店
版 Python，它在部分宿主上以低完整性级别运行、写不了游戏目录，若宿主会降低工作区内可执行文件
的权限，就把虚拟环境建在仓库外并直接调用其中的解释器。

**禁止直接运行** `build_parts.py`、旧 restore 脚本，或用旧 user_overrides 覆盖当前 parts。动画 GIF/WebP、逐帧和审查联系表未作为最终资产重复收录，可由 export.py 重建；查看器相关下载/审查入口若需要这些派生文件，先重导出。旧 Godot 场景、PCK、旧批准报告不能代表当前版本。

卡图 `finalize_v7_delivery.py` / `build_v7_overviews.py` 是带旧 28/61 假设的历史工具，**不要运行**；当前常规入口是 card_repo.py。生成式美术并非离线确定性重建：保留已有原图、提示词、参考与编辑链，但未来重新调用图像服务需要账号/网络，也不会承诺同字节输出。

## 开发与运行依赖

目标锁定 **StS2 0.107.1 / 59260271、Godot 4.5.1、.NET 9、BaseLib 3.4.7**。BaseLib 已取代旧研究中的 RitsuLib 选型；不要混用两套注册。领域 Tier 2 不允许静默豁免正式敌人行为。

仓库不分发游戏程序集、SDK、Godot、下载的框架依赖或本机测试存档。源码入口为 [Mod 工程](src/Volibear/Volibear.csproj)，本地依赖获取与校验见 [依赖工具](tools/dependencies.py)，开发命令见 [开发工具](tools/dev.py)。构建产物与本机配置不入 Git；已有开发候选部署验证不代表发布版安装／卸载及全部玩法验收完成。

游戏测试必须使用隔离资料目录，并保留普通／云端存档和其它 Mod。执行规则、原生退出对照和各独立测试入口见 [原生测试说明](docs/HEADLESS_TESTING.md)。不要在游戏或测试进程运行期间部署另一个候选。
