<div align="center">

# ⚡ Volibear · The Relentless Storm
### 《杀戮尖塔 2》角色模组 —— 沃利贝尔 · 不灭狂雷

[![GitHub Release](https://img.shields.io/github/v/release/fltb/sts2-volibear-mod?style=flat-square&color=3b82f6)](https://github.com/fltb/sts2-volibear-mod/releases)
[![GitHub Issues](https://img.shields.io/github/issues/fltb/sts2-volibear-mod?style=flat-square&color=eab308)](https://github.com/fltb/sts2-volibear-mod/issues)
[![Languages](https://img.shields.io/badge/Localization-EN%20%7C%20%E7%AE%80%E4%B8%AD%20%7C%20%E7%B9%81%E4%B8%AD-10b981?style=flat-square)](#-localization--本地化支持)

**[English](#english) | [简体中文](#简体中文)**

</div>

---

<a name="english"></a>
## 🌍 English

**Game support** · Main v0.111.1 and Public Beta v0.114.0. Install **BaseLib 3.4.8**. Volibear handles its own patch ordering. See the [compatibility notes](docs/LOAD_ORDER_COMPATIBILITY.md) for details.

Compatibility is checked by the actual APIs, patch structure and startup evidence,
without per-mod exceptions. Shared-target metadata and complete-log diagnostics
explain unsupported combinations; a successful load is not a universal compatibility guarantee.
When an extension owns a per-hit damage operation, ordinary Domain lightning and
segment responders remain composed into its completion. Exact mid-hit Steam Eruption
damage suppression yields with a `degraded` report explaining the limited feature.

> *"Beneath stone walls, there is no wild!! They may forget the old ways, yet the old ways will never forget them."*

**Volibear**, the Thunder Demigod of the Freljord, descends upon the Spire! Despising dead stone, cold clockwork, and false order, Valhir forces enemies to fight on his terms, suppresses their tricks inside his Domain, and unleashes primal Lightning and Beast Forms to shatter the Spire's summit.

### ✨ Features
* **New Playable Character:** **Volibear · The Relentless Storm**, complete with custom character select screen, signature *Storm Sea Glass*, and multiplayer prompts.
* **89 Custom Cards:** Full card pool across Basic, Common, Uncommon, Rare, and Token tiers supporting multiple synergistic archetypes.
* **2 Signature Relics:** Starter relic **The Relentless Storm** and upgraded/boss relic **Undying Across the Ages**.
* **6 Epoch Story Cards:** Unlock Volibear's lore timeline from *First Thunder of Vorrijaard* to *I Am the Storm* as you clear Acts, defeat Elites/Bosses, and climb Ascension levels.
* **Full Custom Dialogues & Events:** Unique multi-stage interactions with **The Architect** and all **Ancients** (*Neow, Pael, Orobas, Tezcatara, Nonupeipe, Tanx, Vakuu, Darv*), plus custom Mystery Room events.
* <a name="-localization--本地化支持"></a> **Full Trilingual Localization:** Native support for **English**, **简体中文 (Simplified Chinese)**, and **繁體中文 (Traditional Chinese)**.

### 🐻 Core Mechanics
| Mechanic | Description |
| :--- | :--- |
| **Engage** | Force the target enemy to immediately execute its current intent. Turn enemy aggression into fuel for Block **Absorption**, card draw, and Energy. |
| **Domain** | Deploy a storm field for several rounds. While active, **enemy special abilities are disabled** (no revives, damage caps, summons, card/gold theft, or debuff immunity), your own debuffs are suspended, drawn Status/Curse cards are Exhausted and replaced, and every Attack played strikes ALL enemies with Lightning. |
| **Lightning & Storm Charge** | Spell damage amplified by **Storm Charge**. Chain multi-hit Lightning triggers to generate Energy, stack Thunder Armor, and discount cards. |
| **Beastify** | Exhaust cards in hand to transform them into savage **Beast Forms**—Attacks become **Bone-Rending Claw** and non-Attacks become **Storm Body**, inheriting upgrades and triggering primal synergies. |

### 📦 Installation
1. **Steam Workshop (Recommended):** Subscribe to [**Volibear - The Relentless Storm**](https://steamcommunity.com/sharedfiles/filedetails/?id=3840408533&l=english) on the Steam Workshop and launch the game with mods enabled.
2. **Manual Installation:**
   * Download the archive for your game branch from [**Releases**](https://github.com/fltb/sts2-volibear-mod/releases).
   * Choose one audio package: `riot-sound.zip` uses Riot English voices (the audio profile used by Steam Workshop); `opensound.zip` uses open audio. Install only one.
   * Extract the folder into your *Slay the Spire 2* `mods` directory.
   * Launch the game and enable the mod in the Mod Menu.

### Changelog · v0.1.3

- Raised 85 quieter lines in the Riot English voice profile to a consistent level. Sound-effect levels are unchanged.
- Refined the pacing of eight combat animations using the existing poses and hit timing.

### Changelog · v0.1.2

- Added 14 combat animations and 29 visual effects, with presentation configured for all 89 cards. Multi-hit effects play as each attack hit lands.
- Updated eight power icons, including Battle Scars, Battle-Forged Deity, and Pool of Thunder.
- Domain's base Lightning damage to all enemies is now 3. Hold the Ground draws 1 card at base and 2 when upgraded.
- The Relentless Storm deals 3/5 Lightning damage on deployment and 2/3 after each attack hit (base/upgraded).

### 🐛 Bug Reports & Feedback
Found a bug, balance issue, or localization typo? Please open an issue on [**GitHub Issues**](https://github.com/fltb/sts2-volibear-mod/issues) with reproduction steps or logs attached.

---

<a name="简体中文"></a>
## 🇨🇳 简体中文

**支持的游戏版本** · 正式分支 v0.111.1 和公开测试分支 v0.114.0。请安装 **BaseLib 3.4.8**。沃利贝尔自行处理补丁顺序，详见[兼容性说明](docs/LOAD_ORDER_COMPATIBILITY.md)。

兼容性按实际接口、补丁结构和完整启动日志判断，不加入针对其他模组的特判。
不支持的组合会保留具体失败原因和相关补丁信息；共享同一方法只标为待验证，不按模组名称拉黑。
其他补丁接管每段伤害时，保留普通攻击段的领域附雷和响应，仅让出无法精确归属的蒸汽爆发中途伤害拦截。
报告会标为 `degraded`（功能受限），列出能力、原因和具体影响，不把可加载当成全功能兼容。

> *“石墙之下，毫无野性！！他们或许会遗忘古道，但古道，永远不会遗忘他们。”*

来自弗雷尔卓德的雷霆半神——**沃利贝尔（Volibear）**现已踏入高塔！他厌恶一切冰冷的石墙、死铁与虚假的秩序。化身初开之雷霆，主动迎击强敌、展开压制一切的狂雷领域，在战斗中解放野性兽化，用利爪与天雷将高塔顶端彻底碾作齑粉。

### ✨ 模组内容
* **全新可玩角色：** **沃利贝尔 · 不灭狂雷**（含专属角色选择界面、专属「风暴海玻璃」与联机互动台词）。
* **89 张原创卡牌：** 涵盖基础、普通、罕见、稀有与衍生卡牌，支持完整卡牌升级与多流派构筑。
* **2 件专属遗物：** 初始遗物 **「不灭狂雷」** 与进阶遗物 **「万古不灭」**。
* **6 张完整纪元故事卡（Epoch）：** 从《沃尔瑞加德的初雷》到《我即风暴》，随通关与击杀进度解锁背景史诗与进阶难度。
* **全套专属剧情与交互：** 包含与 **建筑师** 及 **涅奥、佩尔、欧洛巴斯、特兹卡塔拉、诺奴佩普、坦克斯、瓦库、达弗** 等全部先古之民的多组专属对话，以及专属问号房事件。
* **三语完整本地化：** 内置 **简体中文**、**English**、**繁體中文（台灣）** 三语全文本。

### 🐻 核心战斗机制
| 机制 | 效果说明 |
| :--- | :--- |
| **迎战 (Engage)** | 令目标立即执行当前意图。配合高额格挡与「吸收」机制，在敌人攻击的瞬间反制爆发、过牌与回能。 |
| **领域 (Domain)** | 展开持续数轮的雷霆领域：期间**禁用敌方特殊能力**（复活、限伤、护盾阶段、召唤、偷牌偷钱等全部失效），禁用自身负面状态，抽到状态/诅咒牌自动消耗并补抽，且每次打出攻击牌对全体敌人造成 3 点雷伤。 |
| **雷伤与雷势** | 雷伤为法术伤害，受「雷势」与各类能力牌层层增幅，高频触发回能、叠甲与减费。 |
| **兽化 (Beastify)** | 消耗手牌并将其转化为野性「兽形」：攻击牌化为 **「裂骨之爪」**，非攻击牌化为 **「风暴之躯」**，继承原牌升级并触发专属联动。 |

### 📦 安装方式
1. **Steam 创意工坊（推荐）：** 在 Steam 创意工坊搜索并订阅 [**沃利贝尔 · 不灭狂雷**](https://steamcommunity.com/sharedfiles/filedetails/?id=3840408533&l=schinese)，启动游戏启用模组即可。
2. **手动安装：**
   * 前往 [**Releases**](https://github.com/fltb/sts2-volibear-mod/releases)，下载与游戏分支匹配的压缩包。
   * 音频包二选一：`riot-sound.zip` 使用 Riot 英文语音（与创意工坊相同的音频方案），`opensound.zip` 使用 open 音频。只需安装其中一个。
   * 将解压后的模组文件夹放入《杀戮尖塔 2》游戏根目录下的 `mods` 文件夹中。
   * 启动游戏并在模组菜单中勾选启用。

### 更新日志 · v0.1.3

- 提高 Riot 英文音频中 85 条偏轻台词的响度，音效维持原响度。
- 调整 8 套战斗动作的起手、出招和收招节奏，沿用原有姿势与命中时点。

### 更新日志 · v0.1.2

- 新增 14 组战斗动作和 29 类特效，为 89 张卡牌配置战斗表现。多段攻击的特效随每段实际命中播放。
- 更新 8 个能力图标，其中战痕、愈战神躯、雷池使用专属图标。
- 领域对全体敌人的基础附雷降到 3。稳住阵脚基础抽 1 张牌，升级后抽 2 张。
- 狂雷渐起部署时造成 3／5 雷伤，每段普通攻击后追雷 2／3 点（基础／升级）。

### 🐛 问题反馈
如遇到 Bug、数值建议或翻译错误，欢迎前往 [**GitHub Issues**](https://github.com/fltb/sts2-volibear-mod/issues) 提交反馈（附上复现步骤或报错日志最佳）。

---

## 📜 Disclaimer / 免责声明

This mod is an unofficial, non-commercial fan project created in compliance with Riot Games' *"Legal Jibber Jabber"* policy. Volibear and related lore elements are trademarks of Riot Games, Inc. Not endorsed by or affiliated with Riot Games or Mega Crit.

本模组为《英雄联盟》同人非营利粉丝创作（Fan Project），遵循 Riot Games《Legal Jibber Jabber》同人创作政策制作，与 Riot Games 或《杀戮尖塔 2》官方无任何关联。

## 本地构建正式版和 PBE 包

首次使用时，将[配置样例](tools/local_config.example.json)复制为 `.local/config.json`。
`stable_game_dir` 指向独立下载的正式版 v0.111.1，`game_dir` 指向 PBE v0.114.0。
两套构建共用源码，并分别读取对应目录的游戏程序集。Godot 使用 4.5.1 Mono，.NET SDK 使用 9.0.320。

```sh
python tools/build_pbe_release.py --channel stable
python tools/build_pbe_release.py --channel pbe
```

默认从各游戏副本的 `mods/BaseLib/BaseLib.dll` 引用 BaseLib 3.4.8。也可以在本机配置中用
`stable_baselib_dll` 和 `baselib_dll` 指定 DLL。首次准备音频需要 FFmpeg 和 ffprobe。

成品分别位于 `.local/release/stable/` 和 `.local/release/pbe/`。选用对应游戏分支的一种音频包，
解压后得到 `mods/Volibear/`。验收流程见[双通道构建与验证](docs/PBE_CHANNEL.md)。
