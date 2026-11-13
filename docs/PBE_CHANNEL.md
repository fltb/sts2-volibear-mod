# PBE 通道工作流（只追最新分支）

稳定版不再承诺支持：仓库保留其构建代码，但发布与验收只针对当前 PBE。

## 资产与约定

- `.local/game-pbe`：当前 PBE 游戏副本（换新版本时整体替换）。
- `GameChannel=beta`：定义 `STS2_BETA`，用 PBE 程序集编译；包内 `mods/Volibear/BuildChannel.json` 驱动版本门。
- `IncludeDevProbes=true`：测试构建额外定义 `VOLIBEAR_DEV_PROBES`，包含 probe/验收宿主；出厂包永远不含 probe。
- BaseLib 3.4.8（PBE，含 BaseLibCompatibilityHelper 的 DLL 和 JSON）；PBE 的 `min_game_version` 为该 PBE 版本号。

## 每次 PBE 更新的固定流程

```bash
# 1. 复制新版游戏到独立目录 .local/game-pbe，保留 Steam 日常安装和旧副本。
export VOLIBEAR_CHANNEL=pbe
python tools/dependencies.py fetch

# 2. 比较旧副本与新副本的原生接口
python tools/api_diff.py --stable-dir "$OLD_GAME_DIR" --pbe-dir .local/game-pbe --json .local/logs/api-diff.json

# 3. 适配：Core/NativeCompat.cs（签名桥）与对应锚点（IL/字段/调用点）
#    失败信息形如 "Steam patch failed: attack-machine" / "Debris exact contribution drift"，
#    带模块标签，直接定位。

# 4. 编译两个变体
dotnet build src/Volibear/Volibear.csproj -c Release -p:GameChannel=beta \
  -p:Sts2DataDir="$PWD/.local/game-pbe/data_sts2_linuxbsd_x86_64"
dotnet build src/Volibear/Volibear.csproj -c Release -p:GameChannel=beta -p:IncludeDevProbes=true \
  -p:Sts2DataDir="$PWD/.local/game-pbe/data_sts2_linuxbsd_x86_64" -p:OutputPath="$PWD/.local/channels/pbe-test/bin/"
# 只在隔离副本中部署。将 BaseLib 缓存的五个文件放入 mods/BaseLib/。
# 将生产 DLL、当前 PCK 和以下清单放入 mods/Volibear/。
cp src/Volibear/Volibear.pbe.json .local/game-pbe/mods/Volibear/Volibear.json
python tools/compat_report.py --game-dir .local/game-pbe
```

## 原生玩法回归（PBE）

测试构建部署到 `.local/game-pbe/mods/Volibear`（DLL + Volibear.pck + Volibear.json + BuildChannel.json），
运行时把游戏目录暴露为 `.local/game`（runner 的窗口保护只认这一路径），并设置通道版本：

```bash
export VOLIBEAR_GAME_VERSION=v0.113.0 VOLIBEAR_GAME_COMMIT=16ac0fe3
python tools/headless.py --use-deployed --scenario persistent-contract --persistent-case PP-U03-clamp-priority
python tools/headless.py --use-deployed --scenario persistent-contract --persistent-case PP-U03-min-stack
python tools/headless.py --use-deployed --scenario persistent-contract --persistent-case PP-U03-other-retention
python tools/headless.py --use-deployed --scenario power-presentation
python tools/headless.py --use-deployed --scenario domain-visual
python tools/headless.py --use-deployed --scenario domain-suppression
```

已覆盖（PBE v0.111.0 实测通过）：留甲三例（夹击遗物/最小层数/Barricade 让位）、状态表现、领域表现、
领域压制三族（sandpit/knights/self）。其它机制场景（兽化、召唤、敌方贡献、卡牌生命周期、典藏/卡面）
仍按同一方式逐项接入，未通过前不计入“已验收”。

## 当前移植状态

PBE v0.113.0 / 16ac0fe3 的生产 DLL 与开发探针 DLL 均已编译。隔离游戏启动记录了
89 张卡、BaseLib 3.4.8 和零个补丁安装失败。以旧版 PBE DLL 对照时，自检同时报告三个
选择上下文缺少 GameActionType 和 AfterDeath 签名不匹配。尚未执行本版本的完整玩法矩阵。
旧包的 BuildChannel.json 仅标识此前的已测基线；新版本走结构自检。

## 出包

在隔离游戏验收完成后，使用上述生产 DLL、当前 PCK、PBE 清单和官方 BaseLib 五文件归档。
沿用已测基线的通道文件；仅通过启动检查时保持未知版本自检。

```bash
VOLIBEAR_CHANNEL=pbe VOLIBEAR_PACKAGE_GAME_VERSION=0.113.0 VOLIBEAR_PACKAGE_GAME_BUILD=16ac0fe3 \
python tools/release_package.py --manifest src/Volibear/Volibear.pbe.json \
  --output .local/release/Volibear-0.1.0-StS2-0.113.0-pbe-open.zip
```

## 已知边界

- probe 与 evidence 的版本常量已按 `VOLIBEAR_GAME_VERSION/COMMIT` 参数化；新增场景沿用该约定。
- PBE 自身会在退出时打印 `ERROR: Invalid Task ID` 与渲染资源泄漏，属于 stock 行为，已在 teardown 分类中排除。
- 每次 beta 更新都可能移动异步实现/私有成员；先跑 `compat_report` 再改代码，避免“修一处启动一次”。

## 开发循环约束（2026-11-08）

- 实机只用于**最终验收**，不作开发循环：每轮先完成“双通道编译 + `VOLIBEAR_CHANNEL=pbe` 回归 + 定向单测/反射与 IL 对照”，确认没有已知问题后再开游戏。
- 验收只有一条命令：`VOLIBEAR_GAME_VERSION=v0.113.0 VOLIBEAR_GAME_COMMIT=16ac0fe3 python tools/pbe_verify.py`。
  它按场景自动选择预算（卡面/生命周期/native-run/表现验收使用 216000 帧、900 秒上限），失败只输出场景与失败门，不逐个手开。
- `enemy-exploration` 是探索生成器（需要 catalog/selection fixture 输入），不属于验收矩阵；需要时单独用 `tools/headless.py` 带 fixture 参数运行。
- 探针必须在 `Install()` 打印 `<SCENARIO>_INSTALLED` 并带“错过 TurnStarted”的兜底，否则实机日志无法区分“没安装/没开始/失败”。
