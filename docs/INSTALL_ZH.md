# 沃利贝尔中文单人模组：安装与卸载

版本 **0.1.0**。包含沃利贝尔角色、89张卡牌及其升级牌面、两件专属遗物，以及迎战、领域、雷伤、兽化和配套图像动画音频。

本说明用于含`PACKAGE.json`和`mods/`的完整安装ZIP。若拿到的是可覆盖Git仓库的源码包，
先按源码仓库的`docs/LOCAL_WORKFLOW.md`执行`tools/local_delivery.py`生成完整包。
本轮源码候选尚未在维护环境获得锁版游戏完整编译/运行证据；PCK单独通过不代表游戏流程已通过。

仅面向《Slay the Spire 2》**0.107.1 / 构建 59260271**；版本不同请停止安装。依赖固定为 **BaseLib 3.4.7**，不得混用其它版本或另一套基础注册库。本包随附该依赖。

安装后正常启动游戏，在单人新局中选择沃利贝尔。无需源码、开发环境或测试启动参数。本版本按功能实现交付，未宣称通过全部旧验收矩阵。

## 包内内容

- `mods/Volibear/`：原始 `Volibear.dll`、`Volibear.pck`、`Volibear.json`。
- `mods/BaseLib/`：固定官方发行包中的 `BaseLib.dll`、`BaseLib.pck`、`BaseLib.json`。
- `licenses/BaseLib-LICENSE.txt`：BaseLib 原始 MIT 许可。
- `LICENSE`、`LICENSE-ASSETS`、`LICENSING.md`：模组代码、原创资产及第三方例外的许可。
- `licenses/audio/`：默认开放音频的作者、来源 URL、录音摘要及 Kenney 原始许可。
- `PACKAGE.json`：构建标识、锁定版本、官方依赖来源及每个包内文件的 SHA-256。没有本机安装目录。

模组源码与构建说明：https://github.com/fltb/sts2-volibear-mod

官方依赖来源：https://github.com/Alchyr/BaseLib-StS2/releases/tag/v3.4.7

本包不含游戏程序集、日志、存档、开发配置或自动安装程序。不要从研发工作目录另外复制文件，也不要添加测试启动参数。

## 安装（手工操作，禁止覆盖未知模组）

1. 退出游戏。通过 Steam 的“管理 → 浏览本地文件”定位游戏目录，并核对游戏版本与构建号。
2. 将压缩包解压到一个新的空目录，保留原压缩包与 `PACKAGE.json`，不要直接解压进游戏目录。对照清单核对各文件 SHA-256；不一致则停止。Windows 可用 `Get-FileHash .\mods\Volibear\Volibear.dll -Algorithm SHA256`，其它文件同理。
3. 检查游戏目录下的 `mods/Volibear`。**只要已有同名目录或文件、符号链接、目录联接，而你无法证明其归属，就停止；不要点击覆盖或合并。** 即使是旧版自己的安装，也先按旧包清单和旧哈希卸载，不能用新包清单认领旧文件。
4. 检查 `mods/BaseLib`。若不存在，可复制本包整个 `mods/BaseLib` 目录。若已存在，仅在三个文件都与本包清单哈希一致、版本确为 3.4.7、且没有可疑重定向时原样复用；任何不符都停止，不替换、不删除已有 BaseLib。它可能被其它模组共同使用。
5. 仅在 `mods/Volibear` 不存在时，复制本包的 `mods/Volibear` 目录到游戏的 `mods` 下。不要复制整个包根目录、清单或说明文档到 `mods`，避免它们被识别为模组清单。不要操作其它模组目录。
6. 正常启动游戏，按游戏自身提示确认模组加载。加载失败或版本不符时停止使用；保留现有存档，不要为排错删除或重置存档。

这是手工流程，文件管理器不会替你验证归属；出现任何“替换同名文件”提示均应取消操作。

## 卸载（仅删除自己安装且未改动的三个文件）

1. 退出游戏，使用当时安装的原包清单，确认目标仍是游戏目录下真实的 `mods/Volibear`，不是链接或目录联接。
2. 逐一核对以下文件与原 `PACKAGE.json` 中相同相对路径的 SHA-256：
   - `mods/Volibear/Volibear.dll`
   - `mods/Volibear/Volibear.pck`
   - `mods/Volibear/Volibear.json`
3. 仅删除已确认来自本包且哈希未变的上述文件。文件缺失可跳过；任何已有文件哈希不符或来源不明，立即停止，不删除它。
4. 仅在 `mods/Volibear` 完全为空时删除空目录；不得递归删除包含其它内容的目录。

**卸载 Volibear 不删除或修改 BaseLib、其它模组、游戏原文件、游戏设置、存档或云端数据。** 本包没有存档迁移或回退承诺；不要借卸载操作清理存档。


## 音频方案切换

完整安装包默认使用 `open`：47 个开放声音覆盖 54 个声音事件。可选 `riot_en` 的英文原声来源、自动获取和构建命令见源码仓库 `assets/animation/audio/profiles/README.md`；公开源码不包含 Riot 录音。

两套资源替换包都只替换 `mods/Volibear/Volibear.pck`。退出游戏、保留原 PCK 后，使用与当前 DLL 同一版源码构建的目标 PCK 替换；切回 `open` 时恢复默认 PCK。资源替换包不包含 DLL 和 BaseLib，不能单独安装成完整模组。使用替换包后，卸载时以其实际 PCK 摘要核对该文件，另外两份文件仍以原完整包清单核对。
