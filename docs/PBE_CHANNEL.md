# PBE 通道工作流（只追最新分支）

稳定版不再承诺支持：仓库保留其构建代码，但发布与验收只针对当前 PBE。

## 资产与约定

- `.local/game-pbe`：当前 PBE 游戏副本（换新版本时整体替换）。
- `GameChannel=beta`：定义 `STS2_BETA`，用 PBE 程序集编译；包内 `mods/Volibear/BuildChannel.json` 驱动版本门。
- `IncludeDevProbes=true`：测试构建额外定义 `VOLIBEAR_DEV_PROBES`，包含 probe/验收宿主；出厂包永远不含 probe。
- BaseLib 3.4.7（两个通道共用）；PBE 的 `min_game_version` 为该 PBE 版本号。

## 每次 PBE 更新的固定流程

```bash
# 1. 换游戏副本（Steam 切到 beta 后整体复制）
rm -rf .local/game-pbe && cp -a "<Steam>/Slay the Spire 2" .local/game-pbe

# 2. 一次启动拿到全部断点（版本门 + 全部补丁安装 + 内容注册）
python tools/compat_report.py --game-dir .local/game-pbe

# 3. 原生接口面差异（需要 stable 程序集作为基线才可用）
python tools/api_diff.py --stable-dir <stable-game> --pbe-dir .local/game-pbe --json .local/logs/api-diff.json

# 4. 修两处：Core/NativeCompat.cs（签名桥）与对应锚点（IL/字段/调用点）
#    失败信息形如 "Steam patch failed: attack-machine" / "Debris exact contribution drift"，
#    带模块标签，直接定位。

# 5. 编译两个变体
dotnet build src/Volibear/Volibear.csproj -c Release -p:GameChannel=beta \
  -p:Sts2DataDir="$PWD/.local/game-pbe/data_sts2_linuxbsd_x86_64"
dotnet build src/Volibear/Volibear.csproj -c Release -p:GameChannel=beta -p:IncludeDevProbes=true \
  -p:Sts2DataDir="$PWD/.local/game-pbe/data_sts2_linuxbsd_x86_64" -p:OutputPath="$PWD/.local/channels/pbe-test/bin/"
```

## 原生玩法回归（PBE）

测试构建部署到 `.local/game-pbe/mods/Volibear`（DLL + Volibear.pck + Volibear.json + BuildChannel.json），
运行时把游戏目录暴露为 `.local/game`（runner 的窗口保护只认这一路径），并设置通道版本：

```bash
export VOLIBEAR_GAME_VERSION=v0.111.0 VOLIBEAR_GAME_COMMIT=41cef1ea
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

## 出包

```bash
VOLIBEAR_PACKAGE_GAME_VERSION=0.111.0 VOLIBEAR_PACKAGE_GAME_BUILD=41cef1ea \
VOLIBEAR_PACKAGE_CHANNEL_JSON="$PWD/.local/game-pbe/mods/Volibear/BuildChannel.json" \
python tools/release_package.py --dll .local/channels/pbe/bin/Volibear.dll \
  --manifest .local/channels/pbe/Volibear.json --output .local/release/Volibear-0.1.0-StS2-0.111.0-pbe-open.zip
```

`BuildChannel.json` 由 PBE 通道生成（`{"channel":"pbe","game_version":"v0.111.0","game_commit":"41cef1ea"}`），
不得随稳定包分发；安装后日志应出现 `BUILD_GATE build=verified channel=pbe` 与 `LOAD_OK ... target=v0.111.0`。

## 已知边界

- probe 与 evidence 的版本常量已按 `VOLIBEAR_GAME_VERSION/COMMIT` 参数化；新增场景沿用该约定。
- PBE 自身会在退出时打印 `ERROR: Invalid Task ID` 与渲染资源泄漏，属于 stock 行为，已在 teardown 分类中排除。
- 每次 beta 更新都可能移动异步实现/私有成员；先跑 `compat_report` 再改代码，避免“修一处启动一次”。
