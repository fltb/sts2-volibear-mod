# 沃利贝尔 Mod 美术 / 音频 / VFX 资产审计（StS2 v0.107.1 接入视角）

审计对象：`/home/float/g4xk7-mvbjj/Projects/fun/sts-mod` 下三个交付仓库 + 正在生成的 v6 评审包。
审计范围：**格式与契约**（尺寸、通道、图集布局、JSON 字段、命名、SHA 校验、槽位类型、事件时序），不评价画风。
只读声明：本轮未修改 `sts-mod` 下任何文件，未触碰任何生成进程。四个目录都不在 git 版本控制下（`volibear_animation_repo/.git` 是空目录，`git rev-parse HEAD` 报 not a git repository），完整性依靠各目录的 `SHA256SUMS` / `FILE_MANIFEST.json` 与清单内逐项 SHA256，而不是 git 提交号。
快照时间：2026-10-29（本机时区）。资产仍在更新，本文档以快照时刻的磁盘内容为准，见 §7.4。
配套机读清单：同目录 `asset-manifest.json`（284 KB，含 26 序列 / 40 特效 / 54 cue / 89 卡逐项路径与 SHA）。

---

## 0. 结论先行

1. **动画契约完整且自洽**：`animations/clean/` 26 序列 / 940 帧 / 512×512 RGBA8 / 24 fps / 8 列图集 / `pivot_px=[250,442]`，26 PNG + 26 JSON 齐全，`manifest.json` 为 schema_version 1，逐帧带 SHA256。可直接构造 `SpriteFrames`（离线 Godot 4.5.1 已实测）。
2. **卡图 89/89 齐全且尺寸精确匹配官方模板实测值**：STS2 导出为 1000×760 与 250×190、**RGB 不透明、不含卡框/费用/文本**；我用 ModTemplate commit `2c900a0` 的模板 PNG 实测确认同为 250×190 / 1000×760。缺口不在数量，在 **v6 评审的 60 张待重绘**。
3. **动画接入走 RitsuLib `ModAnimStateMachine` + `AnimatedSprite2DBackend` 最贴合交付**：26 个图集名可直接注册为 SpriteFrames 动画名；BaseLib `CustomAnimation` 也支持 `AnimatedSprite2D`（`SpriteFrames.HasAnimation(name)` 逐名尝试），但只有名称匹配、没有状态机与形态条件，领域/低血/兽化切换需自建。
4. **VFX 的 40 组图集不能直接当游戏命中特效路径用**：游戏 `AttackCommand.WithHitFx(string vfx, string sfx, string tmpSfx)` 的 `vfx` 是**场景资源路径**（游戏内为 `res://vfx/*.tscn`），不是 PNG。必须为每组特效包 `.tscn`（或走 `WithHitVfxNode` 挂自定义节点），且 `res://` 路径是否被游戏接受需实机验证。
5. **音频 47 OGG（48 kHz / 单声道 / Vorbis）54 cue 齐全，但 FMOD bank 缺口为真**：游戏本体只有 `Master/Music/ambience/act*.bank`；原生角色槽默认走 `event:/sfx/characters/<id>/...` FMOD 事件，没有沃利贝尔 bank → 要么做 bank，要么走 BaseLib `PlayResourcePatch` 的 `res://` Ogg 桥（源码存在，未实机验证）。
6. **没有任何东西在游戏内验证过**：`src/*.cs` 状态为 `integration_source_uncompiled`；已验证的只有「Godot 4.5.1 离线读取/构造/解码/PCK 挂载」。平台层（加载器、manifest、模型注册）由 task-1 负责，本文不重复。

---

## 1. 资产清单总表

### 1.1 分类清单

| # | 类别 | 路径（仓库内） | 数量 | 格式细节 | 命名规则 |
|---|---|---|---|---|---|
| 1 | 角色无特效图集（接入首选） | `volibear_animation_repo/animations/clean/atlases/` | 26 PNG + 26 JSON | PNG 4096×(rows·512)，RGBA8，sRGB，straight alpha；格 512×512，8 列；JSON 每帧 `rect/duration_ms/pivot_px` | `<clip>.png` / `<clip>.json`；clip ∈ 24 基础名 + `domain_roar`/`domain_storm_leap` |
| 2 | 角色逐帧 PNG（无特效源帧） | `animations/frames/<clip>/` | 940 PNG | 512×512 RGBA8，透明背景，未裁边 | `%04d.png`，从 0000 起 |
| 3 | 角色带烘焙演出图集（旧接入/预览） | `animations/atlases/` | 26 PNG + 26 JSON | 同上；内含领域染色/描边/风雷环等烘焙效果 | 同上 |
| 4 | 动画清单 | `animations/manifest.json`、`animations/clean/manifest.json` | 2 JSON | schema_version 1，含 clips/variants/motions/parts/rig/state_rules/source_integrity | — |
| 5 | 动作事件表 | `animations/EVENTS.md`、各 clip JSON 的 `events[]` | 53 事件 | 秒 + normalized + frame_index + sample_time_seconds | — |
| 6 | VFX 特效图集 | `vfx/atlases/` | 40 PNG + 40 JSON | PNG 2048×(rows·256)，RGBA8；格 256×256，8 列；straight alpha / mix | `<effect_id>.png` / `.json` |
| 7 | VFX 源帧 | `vfx/frames/<effect_id>/` | 1070 PNG | 256×256 RGBA8 | `%03d.png` |
| 8 | VFX 清单 | `vfx/manifest.json` | 1 JSON | 40 effects / 1070 帧 / canvas 256 / fps 24 / alpha_mode=straight / blend_mode=mix | — |
| 9 | 卡牌→演出绑定 | `vfx/card_vfx_bindings.json`（两仓库同一文件，SHA 相同） | 89 卡 / 219 条 cue / 10 条全局规则 | 见 §4.2 schema；`binding_kind=portable_semantic_presentation_contract_not_native_game_api` | — |
| 10 | 机制图标 | `vfx/icons/{256,128,64,32}/` + `vfx/icons/svg/` | 64 PNG + 16 SVG | PNG 各尺寸 RGBA8；SVG 可编辑矢量 | `<icon_id>.png` / `<icon_id>.svg`；16 个 id |
| 11 | 音频运行文件 | `audio/ogg/` | 47 OGG | Ogg Vorbis，48 000 Hz，**单声道**，时长 0.23–4.00 s，合计 45.254 s | `<asset_id>.ogg` |
| 12 | 音频母版 | `audio/wav/` | 47 WAV | PCM16 编辑母版（不随 PCK 分发） | 同名 |
| 13 | 音频 cue 清单 | `audio/manifest.json` | 54 cue | id/asset_id/file/duration/loop/bus/gain_db/cooldown_ms/max_voices/trigger_policy | `sfx.*` / `voice.*` |
| 14 | 动作音效时间线 | `audio/action_cues.json` | 26 clip / 53 cue 事件 + 4 条 state_entry_only | schema_version 1，`events[].time_seconds` 秒 | 与 clip 名一致 |
| 15 | 角色 UI | `ui/images/` | 14 PNG | 132×195 / 128×128 / 74×74 / 24×24 / 256×256 / 512×512 / 1920×1080；RGBA | `character_icon_volibear*.png`、`char_select_volibear*.png` … |
| 16 | 卡图母版 | `volibear_cards_repo/cards/masters/` | 89 PNG | 1429–1439 × 1086–1093，RGB，无卡框无文字，25:19 | `<ID>.png`（B01、C01、U02、R31、T01…） |
| 17 | 卡图游戏导出 | `production/sts2/Volibear/images/card_portraits/big/`、`.../card_portraits/` | 89 + 89 PNG | 1000×760、250×190，RGB 不透明 | `<asset_key 小写>.png`（b01.png…） |
| 18 | StS1 导出（本项目副产物） | `production/sts1/VolibearResources/images/cards/` | 178 PNG | `<key>_p.png` 500×380 RGBA 遮罩、`<key>.png` 250×190 RGBA | 同上 |
| 19 | 卡图辅助 | `cards/prompts/`、`cards/proofs/`、`reviews/`、`cards/gallery_previews/{gray,tiny}/` | 89 + 89 + 89 + 178 | 文本/JPG/PNG | 按卡 ID |
| 20 | 机读卡表 | `data/cards_source.json`、`data/asset_manifest.json`、`data/cards_art_briefs.json` | 3 JSON | 见 §2.2 | — |
| 21 | 离线校验工程 | `integration_sts2_v5/` | project.godot + demo.gd/tscn + 6 C# + 2 py + 1 gd | Godot 4.5.1 标准版可打开 | — |
| 22 | 运行资源包 | `exports/VolibearArt_v5.pck` | 1 PCK | 126 933 504 B，`res://VolibearArt/` 命名空间；280 个运行资源 / 153 042 977 B 暂存 | SHA 见 §1.3 |
| 23 | 研究性归档（不分发） | `audio/official/` | 153 OGG（en_us/zh_cn） | Riot 原版录音归档，**不在 47 个运行文件内**（SHA 零重叠） | — |
| 24 | v6 评审包 | `volibear_cards_art_review_v6/` | 89 current + 89 small + 89 tiny + 29 benchmarks + 60 prompts | 250×190、125×95 检查尺寸 | 按卡 ID |

### 1.2 命名规则汇总

- 动画：`<clip>` 名即 SpriteFrames 动画名；`frames/%04d.png`、`atlases/<clip>.png|json`、`previews/<clip>.gif`。
- 动画 clip 全集（24）：`idle_loop, relaxed_loop, weak_loop, attack, attack_heavy, bite, cast, hurt, block, counter, domain_enter, domain_idle, domain_exit, feral_enter, feral_idle, die, domain_attack, domain_cast, domain_hurt, domain_block, domain_weak_loop, domain_die, roar, storm_leap`；变体（2）：`domain_roar`(base_clip=`roar`)、`domain_storm_leap`(base_clip=`storm_leap`)。
- VFX：`<effect_id>`（40 个），`frames/<id>/%03d.png`；`atlases/<id>.png|json`。
- 音频：`<asset_id>.ogg`；逻辑 cue `sfx.<effect_id>` / `voice.<name>`；7 个声音文件被 2 个 cue 复用（见 §5.1）。
- 卡图：母版大写卡号 → 导出小写 asset_key（`B01` → `b01.png`），与模板 `Id.Entry.RemovePrefix().ToLowerInvariant()` 规则一致（见 §2.3）。
- UI/图标：`character_icon_<char>`、`character_icon_<char>_outline`、`char_select_<char>[_locked]`、`map_marker_<char>`、`big_energy`、`text_energy`、`energy_master`、`big_energy_empty`、`character_fallback`、`character_select_background`、`character_select_transition`。

### 1.3 版本与 SHA 校验链

四层可复核：

1. **仓库级**：`volibear_animation_repo/SHA256SUMS`（3206 行）、`volibear_cards_repo/SHA256SUMS`（2399 行）、`volibear_reference_repo/SHA256SUMS`。抽样 `sha256sum -c` 通过（`animations/clean/manifest.json`、`production/sts2/.../big/b01.png` 均 OK）。
2. **清单级**（本轮实测值，2026-10-29 快照）：

| 文件 | SHA-256 |
|---|---|
| `animations/clean/manifest.json` | `da8680ce0d2053a641f8e8e67133f7ad41dfb3159c22192427124345e92ce403` |
| `animations/manifest.json` | `1c8d1e91c57f065a6cfe14d9d5f9a30bd5b68dbe8179e120d7fc64cf004e6b4f` |
| `vfx/manifest.json` | `65eba1871f70793b79f971a38a97c8c5ba64370a7553214df9b795ca6e470b23` |
| `vfx/card_vfx_bindings.json` | `62aa07d0bae59cc8afb77878256baac942bf64bc559a888f16a32f6d3c8c37b5` |
| `audio/manifest.json` | `d22297d0713fa40042e5c3897ec191660f8876bf87e6032aa8ba2a3a27f54be6` |
| `audio/action_cues.json` | `5ccc73d0638905c188996d540c1017821de582e0b72af6620502f9fa6e213505` |
| `ui/manifest.json` | `2d24dfd2125910115adacd420b848da2798221a334695deb85e801c254b31ac3` |
| `vfx/icons/manifest.json` | `ca2e52ca1bd78b70e2eb1e220d1fd0f41ba0b4bb47c73095076c321fb37fb447` |
| `exports/VolibearArt_v5.pck` | `c655c2044a16bd56a3bf442cecc35b47c38ca96ad797734063117560ce269739` |
| `data/asset_manifest.json`（cards） | 见 §2.2 / 机器清单 |
| `data/cards_source.json`（cards） | 见 §2.2 / 机器清单 |

3. **条目级**：动画每帧 `frames[].sha256`、每图集 `atlas_sha256`；clean 每帧另有 `raw_rgba_sha256`（RGBA 逐像素哈希，供 `validate_clean_atlases_v5.py` 比对）；VFX 每帧 `sha256` + `atlas.sha256`；音频无逐文件哈希字段，靠仓库 `SHA256SUMS` 与 cue 的 `duration_seconds` 校验。
4. **构建级**：`exports/VolibearArt_v5.report.json` 记录 7 个输入清单 SHA、4 个构建脚本 SHA、280 个暂存文件 SHA、PCK SHA、`engine_verification`（`passed=true, isolated_project=true, failures=[]`）。`integration_sts2_v5/stage_assets.py` 在复制前后各算一次 SHA，输入在 staging 期间变化即失败。
- 版本字段：动画 `art_revision=joint_occlusion_v5`；VFX `asset_revision=v5`；卡片 `delivery_revision=4 / schema_version 3 / status=complete`；UI `template_commit=2c900a04dd2073872f677f4fb78ee2ad1e871009`（ModTemplate）。
- 注意：`animations/manifest.json` 与 `clean/manifest.json` 是**两套不同清单**（前者含烘焙帧路径 + `source_integrity`，后者路径相对 clean 目录），不要混用；`integration_sts2_v5/stage_assets.py` 强制只取 clean 并拒绝覆盖非空目录。

---

## 2. 卡图管线

### 2.1 链路与实测尺寸

```
cards/masters/<ID>.png           1429–1439 × 1086–1093  RGB，25:19，无卡框/费用/文本/稀有度
      │  PIL ImageOps.fit(master.convert("RGB"), size, LANCZOS)   # 先居中裁到 25:19，再缩放
      ├─ production/sts2/.../card_portraits/big/<key>.png   1000×760  RGB 不透明（89/89）
      └─ production/sts2/.../card_portraits/<key>.png        250×190  RGB 不透明（89/89）
      （另有 STS1 两套：500×380 / 250×190 RGBA + 类型遮罩，178 个，属副产物）
```

- 导出实现：`volibear_cards_repo/scripts/card_repo.py` `render()` 用 `ImageOps.fit(..., Image.Resampling.LANCZOS)`；构建前门禁要求母图 ≥1000×760 且 `|宽高比/(25/19)−1| < 0.001`，否则报 `unreviewed aspect crop`。
- 母图尺寸分布：1438×1093（46）、1439×1093（34）、1437×1092（5）、1429×1086（2）、1434×1090（1）、1433×1089（1）。比例均在 25:19 ±0.11% 内 → 裁切损失仅若干像素，不再二次构图。
- 卡图**不含卡框**：`config/export_profiles.json` 只产出插画；卡框/费用/描述/稀有度由游戏 UI 绘制（卡仓库 README 明确“卡框和效果文本由游戏 UI 负责”）。
- 数量完整性：89/89（87 主卡 + T01/T02 两张衍生牌）；金币/稀有度分布 `basic 4 / common 24 / uncommon 36 / rare 23 / token 2`；类型 `攻击 28 / 技能 44 / 能力 17`；编号前缀 `B 4 / C 24 / U 36 / R 23 / T 2`。

### 2.2 机读数据

- `data/cards_source.json`：`schema_version 1.0`、`source_version v4.1`、`card_count 89`、`main_card_count 87`、`counts_by_rarity`、`keyword_definitions`（17 条：雷伤/雷法/领域N/迎战/吸收/兽化/检索／回收/减费N/咬痕/反雷N/蓄势N/强化N/重演/汲取/留甲N/坚甲/净化消耗）。字段：`id/asset_key/name/type/rarity/cost/base_effect/upgraded_effect/source_section`。
- `data/asset_manifest.json`：`schema_version 3`、`delivery_revision 4`、`status complete`、`reviewed_card_count 89`、`revised_ids`（10 张：B02/C14/C17/U12/U13/U28/R07/R28/U41/T02）、每卡 `master/master_sha256/prompt/review/exports[4]/provenance`；`reports/technical_validation.json`：`passed=true, card_count=89, export_count=356, unique_artwork=89`。

### 2.3 与 StS2 官方模板/框架的对照（已联网实测）

**模板实测尺寸**（我从 `Alchyr/ModTemplate-StS2@2c900a0` 下载 `content/CharacterModTemplate/CharMod/images/` 的 PNG 后 `identify` 得到，非引用二手结论）：

| 模板文件 | 实测像素 | 通道/透明 | 沃利贝尔对应 |
|---|---|---|---|
| `card_portraits/card.png` | 250×190 | RGB 不透明 | `production/sts2/.../card_portraits/<key>.png` ✅ 同尺寸同模式 |
| `card_portraits/big/card.png` | 1000×760 | RGB 不透明 | `.../big/<key>.png` ✅ 同尺寸同模式 |
| `charui/char_select_char_name.png` | 132×195 | RGB 不透明 | `char_select_volibear.png`（交付为 RGBA，尺寸一致）⚠️ 模式不同 |
| `charui/char_select_char_name_locked.png` | 132×195 | RGB 不透明 | `char_select_volibear_locked.png` ⚠️ 同上 |
| `charui/character_icon_char_name.png` | 128×128 | RGBA | `character_icon_volibear.png` ✅ |
| `charui/map_marker_char_name.png` | 128×128 | RGBA | `map_marker_volibear.png` ✅ |
| `charui/big_energy.png` / `text_energy.png` | 74×74 / 24×24 | RGBA | `big_energy.png` / `text_energy.png` ✅ |
| `powers/power.png` / `powers/big/power.png` | 64×64 / 256×256 | RGBA | `vfx/icons/{64,256}/<id>.png` ✅ |
| `relics/relic.png` / `big/relic.png` | 94×94 / 256×256 | RGBA | 未制作（本设计无专属遗物，走原版） |
| `potions/potion.png` | 256×256 | RGBA | 未制作（走原版） |

**模板代码的卡图契约**（`content/CharacterModTemplate/CharModCode/Cards/CharModCard.cs`，注释原文）：
- 大卡图：`CustomPortraitPath = $"{Id.Entry.RemovePrefix().ToLowerInvariant()}.png".BigCardImagePath()`，注释写「Normal art: 1000x760；Full art: 606x852」。
- 小卡图：`PortraitPath = ... CardImagePath()`，注释写「Smaller variant of normalart: 250x190；full art: 250x350」。
- 路径函数（`Extensions/StringExtensions.cs`）：`CardImagePath → res://<ModId>/images/card_portraits/<name>`，`BigCardImagePath → res://<ModId>/images/card_portraits/big/<name>`；文件不存在时回退 `card.png` 并在日志打印 `Could not find card image path`。`MainFile.ResPath = $"res://{ModId}"`。
- 官方 wiki `Adding-Cards` 同口径：卡图放 `YourModName/images/card_portraits/big/`，1000×760（全画幅 606×852），文件名 = 卡类名小写下划线；250×190 小图可选但更省；beta 图放 `card_portraits/beta/`。

**BaseLib / RitsuLib 槽位**：
- BaseLib `CustomCardModel`：`CustomPortraitPath`、`CustomPortrait`(Texture2D)、`CustomFrame`(Texture2D)、`CustomFrameMaterial`、`CustomBannerMaterial`/`CustomBannerMaterialPath`。挂钩 `CardModel.PortraitPngPath/Portrait/PortraitPath`，因此 `CustomPortraitPath` 就是**单张卡面路径**。
- RitsuLib `CardAssetProfile`（`src/Scaffolding/Content/ContentAssetProfiles.cs` 第 356 行起）：`PortraitPath / BetaPortraitPath / FramePath / PortraitBorderPath / EnergyIconPath / OverlayScenePath / BannerTexturePath / FrameMaterialPath / …`，全部为字符串路径 + 可选 `Material` 对象 → 卡面只吃路径，卡框/描边/远古样式另有字段。
- **结论**：本项目 89 张 250×190 + 1000×760 RGB 插画**直接满足**模板与两个框架的卡面槽位；卡框/费用/稀有度/描述不需要我们提供（也不应烘焙进图里）。命名只需保证卡模型 ID 去前缀小写后等于 `asset_key`。

### 2.4 缺口

1. **v6 评审未落地**（P0，见 §7.4）：89 张中 29 张用户锁定保留，60 张判为返工；`generation_queue.json` 为 `not_started / total 60 / completed 0`，pilot 8 张。当前 `production/sts2` 的 89 张仍是 v5 母版导出，**用户已否定其中 60 张**——技术上可用，内容上待替换。
2. **无 beta 卡图、无 full-art 变体**（可选，模板支持 `beta/`）。若后续要全画幅 606×852 / 250×350，需另出一条导出 profile。
3. 卡号中存在编号空缺（无 C16/C23/U01/U09/…），`cards_source.json` 明确「不补齐编号空缺」；卡类 ID 必须与 `asset_key` 对齐，否则模板回退到 `card.png`。
4. 小卡图 250×190 与卡框叠加后的可读性只在 v6 的 `assets/small` 做过评审，**游戏内未验证**。
5. `masters` 尺寸非 1000×760 整数倍（1429–1439 宽），重导出必须走 `card_repo.py rebuild`（自带 25:19 门禁），不要手工 resize。

---

## 3. 角色动画（26 序列 / 940 帧）

### 3.1 结构

- 24 个基础 clip + 2 个领域变体 = 26 序列，合计 940 帧；每序列独立图集 + 独立 JSON。
- 画布 512×512 固定（设计坐标 768×768），**不按 bbox 裁边**，因此播放不会因 padding 抖动；`pivot_px=[250,442]`，`feet_ground_y=442`，`facing=right`。
- 图集：8 列固定，行数 = ceil(frame_count/8)，格 512×512；最大 4096×3072；坐标左上原点。各 clip 行数 2–6。
- 时长/帧数：idle/relaxed/weak/feral_idle/domain_idle/domain_weak_loop 48 帧 2.0 s 循环；attack 24 帧 1.0 s；attack_heavy/counter 32 帧 1.333 s；bite/block/domain_attack/domain_block 24 帧 1.0 s；cast/domain_cast/domain_exit/roar/domain_roar/feral_enter 36 帧 1.5 s；hurt/domain_hurt 16 帧 0.667 s；domain_enter 44 帧 1.833 s；die/domain_die 40 帧 1.667 s；storm_leap/domain_storm_leap 48 帧 2.0 s。
- JSON 字段（clean，`atlases/<clip>.json`）：顶层 `canvas_size, character_color, clip, coordinate_root, event_time_unit, events, fps, frames, image, loop, poses`；每帧 `{frame, time_seconds, rect, duration_ms, pivot_px, raw_rgba_sha256}`。**烘焙版**（`animations/atlases/`）顶层无 `character_color/coordinate_root`，每帧无 `time_seconds/raw_rgba_sha256`（只有 `frame/rect/duration_ms/pivot_px`）——两套 JSON 不同构，读取代码不能共用字段假设。
- 事件：53 条，字段 `{time, time_seconds, normalized_time, frame_index, sample_time_seconds}`；`time` 单位秒（`rig/motions.json` 的曲线 key 才是 0–1 归一化相位，勿混用）。`EVENTS.md` 有全表。
- 状态规则（`state_rules`）：低血 30% 进入 / 35% 退出（项目扩展，非原版事实）；`feral_is_temporary_card_action_pose=true`；`death_loops=false`。
- 蛇形/骨架数据：`rig/rig.json`、`rig/motions.json`、`rig/parts_manifest.json` 是自研渲染器的装配数据，**不是 Spine skeleton**，不要改扩展名冒充。

### 3.2 26 序列 → 游戏动作集映射

RitsuLib 状态机触发名（`VolibearSpriteFrames.CreateMachine`，`src/VolibearSpriteFrames.cs:179-202`）与交付 `project_animation_mapping.json` 一致：

| 游戏触发 | 普通形态 | 领域形态 | 说明 |
|---|---|---|---|
| `Idle` | `idle_loop` | `domain_idle` | 初始状态；`Revive` 走同一组待机（显式回退，无独立复活动画） |
| `Relaxed` | `relaxed_loop` | `relaxed_loop` | 商店/篝火复用 |
| `LowHealth`（项目触发） | `weak_loop` | `domain_weak_loop` | 30/35% 滞回 |
| `Attack` | `attack` | `domain_attack` | |
| `HeavyAttack`（扩展） | `attack_heavy` | `domain_attack`（别名） | 领域无专属重击 |
| `Bite`（扩展） | `bite` | `domain_attack` | 别名 |
| `Counter`（扩展） | `counter`（可切成 14–31 帧切片） | `domain_attack` | `PlayPostChallengeCounter`，C10/U28/R09 |
| `Block`（扩展） | `block` | `domain_block` | |
| `Cast` | `cast` | `domain_cast` | |
| `Hit` | `hurt` | `domain_hurt` | |
| `Dead` | `die` | `domain_die` | 非循环，停末帧；`terminal=true` |
| `DomainEnter` | — | `domain_enter` | 只 false→true 播一次；延长用 VFX 脉冲 |
| `DomainExit` | — | `domain_exit` | |
| `Roar`（扩展） | `roar` | `domain_roar`（变体） | |
| `StormLeap`（扩展） | `storm_leap` | `domain_storm_leap`（变体） | 天声震落 R31：先进领域，再播领域跳跃，不叠 `domain_enter` |
| `FeralEnter`（扩展） | `feral_enter` | `domain_cast`（别名） | 兽化是「手牌变身」，不是永久变身；播完回实际待机 |
| `FeralPose`（可选） | `feral_idle` | — | 最长 0.5 s 的 TTL 姿态，token 防旧计时器覆盖 |

- 原生动作名参考（研究仓库 `native_animation_inventory.json`，来源 Spire Codex v0.107.1 动画目录 + 反编译快照）：原版角色实际 clip 为 `idle_loop, attack, attack_heavy, cast, hurt, die, relaxed_loop, weak_loop`，`weak_loop` 在目录存在但检查到的代码未注册；`Idle/Attack/Cast/Hit/Dead/Relaxed/heavyAttack` 的映射与本包命名一致。→ 我们的命名不是自造体系，和原版命名习惯对齐。
- 方向：角色统一朝右，图集内左右不镜像；需要朝左时由宿主节点 `flip_h`（会同时翻转 pivot 语义，需按场景换算，见 §3.4）。

### 3.3 两套后端对 SpriteFrames 的要求

**(A) RitsuLib `AnimatedSprite2DBackend` + `ModAnimStateMachine`（交付主路径）**
- 要求 `AnimatedSprite2D.SpriteFrames` 中每个状态 id 存在且帧数 >0；`HasAnimation(id)`、`GetFrameCount`、`GetAnimationLoop`、`GetAnimationSpeed`、`GetFrameDuration` 被直接调用（后端源码 `AnimatedSprite2DBackend.cs`）。
- 帧时长是**相对值**：SpriteFrames 的 seconds = `duration_ms * fps / 1000`；24 fps、41.6667 ms → 必须写 **1.0**，写 0.041666 会慢 24 倍（`VolibearSpriteFrames.cs:130-132` 的注释就是此坑）。
- 循环标志以 SpriteFrames 为准，状态机可在请求时改写 `SetAnimationLoop`（后端会同步回资源）。
- 状态机构建：`ModAnimStateMachineBuilder.Create()` + `AddState(id, loop)` + `AddAnyState(trigger, toId, Func<bool>)` + `Build(backend)`；宿主重写 `ModCharacterTemplate.SetupCustomCombatAnimationStateMachine(Node visualsRoot, CharacterModel)`（RitsuLib `772f280`，`ModCharacterTemplate.cs:706-774`；旧名 `SetupCustomNonSpineAnimationStateMachine` 已 `[Obsolete]`）。
- 交付已实现：领域/低血双标记、`feral` 临时姿态 TTL、`terminal` 死亡锁定、非循环动作从 0 帧重启、完成后按真实状态回待机（不是固定 `WithNext("idle_loop")`）。
- 状态机命名空间：`STS2RitsuLib.Scaffolding.Visuals.StateMachine` / `.Backends`；状态机类型由 `STS2-RitsuLib.Runtime` 组件编译，不能只引用单文件旧 DLL。

**(B) BaseLib `CustomAnimation`（可选，代码更少但表达力弱）**
- 自动探测顺序：`AnimationTree(AnimationNodeStateMachine)` → `AnimationPlayer` → `AnimatedSprite2D`（先同节点再递归子节点）；`AnimatedSprite2D` 分支就是 `if (animSprite.SpriteFrames.HasAnimation(name)) animSprite.Play(name)`。
- 只按传入的 `tryAnimNames` 逐名尝试（wiki 列自动名：`idle/attack/cast/hurt/die` 或 `CreatureAnimator` 常量的小写形式），**没有条件分支、没有形态切换、没有完成回调**；领域/低血/兽化必须由宿主自行切 SpriteFrames 或选名。
- 结论：本项目 26 序列可用两套后端任一播放；**推荐 RitsuLib 路径**（状态机与 domain/feral 语义已写好），BaseLib 仅作为「只想最小改角色模板」的退路。两条路径不能同时控制同一个 `AnimatedSprite2D`。

### 3.4 clean vs 带内嵌特效（烘焙）版本的取舍

- `animations/clean/`：中性原角色颜色，**不含**闪电、光圈、领域描边/染色；`skin` 只是状态提示，不代表已染色。领域效果由独立 VFX/Shader 负责。
- `animations/atlas/`+`frames/`：已烘焙领域染色、雷环、尘雾等。**不可与独立 VFX 叠加**（会双绘）。
- 交付文档明确「新接入优先 clean」，`stage_assets.py` 强制取 clean 并在缺失时拒绝执行；`validate_clean_atlases_v5.py` 用 `raw_rgba_sha256` 逐格证明 clean 格 = 无特效源帧。
- 结论：接游戏用 clean；baked 仅用于旧预览/对照。若未来做领域染色，用 `ShaderMaterial` 或独立 VFX，不要回退到烘焙图集。

### 3.5 pivot / Bounds / IntentPos / CenterPos 约定

- 图内锚点：`pivot_px=[250,442]`（导出图内脚底），`feet_ground_y=442`，远侧足底略高表示透视。图集/帧都用同一 512 画布，`content_bbox` 只描述可见像素范围，**不是**裁切依据。
- 宿主节点：交付给 `AnimatedSprite2D` 的建议值是 `centered=false` + `offset=(-250,-442)`（`docs/HOST_HOOKS.md:7`），把脚底对齐到父节点原点；实际 position/scale 由战场布局决定，**不要重复应用偏移**。
- `NCreatureVisuals`（BaseLib wiki 实测，2026-10-29 抓取）根 Node2D 要求子节点：`Visuals`(Node2D, 必需)、`Bounds`(Control, 必需)、`IntentPos`(Marker2D, 必需)、`CenterPos`(Marker2D, 必需, **VFX 生成位置**，应约在角色视觉中心)、`OrbPos`(可选, 默认用 IntentPos)、`TalkPos`(可选)、`PhobiaModeVisuals`(可选)。
- `Bounds` 是交互/布局框，**不能**每帧按透明像素 bbox 改，否则命中区域随动作跳动。我们的 512 画布 + 固定 pivot 正好满足「动作不改变锚点」。
- 参考坐标换算（供搭场景时用）：画布 512×512，pivot 在 (250,442)；`CenterPos` 取内容 bbox 中心约 (≈250,≈260)（各 clip bbox 在 x 35–507 / y 33–472），`IntentPos` 取头顶偏上（约 y≈60–90），实际以场景美术对齐为准并需游戏内目视校准。

### 3.6 兽化形态与领域状态的切换后端

- **领域（Domain）**：规则层先提交领域状态，再设 `presentation.Flags.Domain`；进入播 `domain_enter`（仅 false→true 一次），常驻待机切 `domain_idle`/`domain_weak_loop`，动作切 `domain_*`；退出播 `domain_exit` 并停循环。四种领域动作 + 2 个烘焙变体（roar/storm_leap）+ 别名（heavy/bite/counter→domain_attack，feral_enter→domain_cast）。
- **兽化（Feral）**：**这是手牌机制，不是角色变身**。`feral_enter` 只是一段施放动作（源=角色施放位置，终点=被转化手牌）；完成立即回真实待机（领域/低血/普通）。可选 `feral_idle` 是 ≤0.5 s 的临时姿态（token 防覆盖），不构成永久 buff。卡牌层负责实际变身（R28/R29/R30/R43 等 6 张卡用 `feral_enter` 主动作）。
- **低血（LowHealth）**：项目扩展的表现状态，30% 进入 / 35% 退出，与领域叠加时领域弱待机优先（rest 优先级：domain+weak > domain > weak > feral pose > normal）。原版无此阈值，需宿主血量事件调用。
- 后端选择建议：领域/兽化/低血全部在 **RitsuLib 状态机条件**里表达（`AddAnyState` 的 `Func<bool>`），不要在卡牌代码里直接 `Play()` 抢动画——否则会和状态机互相打断。需要与规则严格对齐的切片（如 C10/U28/R09 的 counter 后段 14–31 帧）用 `PlayPostChallengeCounter`，领域下不 seek（直接 `domain_attack` 全段）。

### 3.7 缺口

1. **无 `.tscn` / `.tres` 成品**：交付只有 PNG/JSON + C# 构造代码。要么运行时 `VolibearSpriteFrames.Load()` 建 `SpriteFrames`，要么先在 Godot 里烘焙成 `SpriteFrames.tres` 并挂到 `AnimatedSprite2D`。**未做**。
2. **无 `NCreatureVisuals` 场景**（Visuals/Bounds/IntentPos/CenterPos 全缺），`character_fallback.png` 只是静态 Sprite2D 回退，不能冒充战斗场景（`UI_PROFILE_MAP.md` 自己也这么写）。
3. 26 序列中 `feral_idle`、`domain_weak_loop` 在原生动作集里没有对应 trigger，需要项目自定义状态；原版敌方 AI/意图系统不会自动触发 `HeavyAttack/Bite/Counter/Roar/StormLeap/DomainEnter` 等扩展触发，宿主必须在规则动作提交时显式 `SetTrigger`。
4. 无朝左图集（靠 `flip_h`），多人/镜像场景下的锚点需单独换算。
5. **v6/v7/v8 骨骼重制未批准**：`animations/skeletal_v8/manifest.json` 里 `art_approved=false`、`format` 仍为 940 帧 26 序列，`godot_export_status=source_exported_engine_unvalidated`；v8 状态为 `rejected_anatomical_partition`。**不要让接入代码切换到这个目录**，除非用户重新批准并重建合同（JSON 结构略变：顶层多 `atlas/duration/gif/input_fingerprint/technique/webp`，帧字段仍兼容 `rect/duration_ms/pivot_px`）。

---

## 4. VFX（40 组 / 1070 帧）

### 4.1 素材规格

- 画布 256×256，8 列，格 256×256；图集 PNG 2048×(rows·256)；RGBA8，`alpha_mode=straight`，`blend_mode=mix`（无 additive 依赖，符合 contract 的 "no additive overdraw requirement"）。
- 24 fps；每帧 `duration_ms` 隐含（JSON 只给 `time_seconds` 与 `fps`，无逐帧 duration 字段）。
- `pivot_px` 默认 `[128,128]`；例外：`heavy_impact [128,181]`、`domain_enter/domain_loop/domain_exit [128,180]`、`feral_aura [128,197]`（地面类贴地锚）。
- `layer_z`：地面 -20、后景 -10、命中 20–30（`domain_*` 为 -20，`lightning_all`/`domain_suppress` 为 10–20）。
- 锚点枚举（24 种）：`target_contact, target_ground, target_status, owner_front, owner_contact, owner_status, owner_ground, owner_hand, owner_energy, owner_mouth_to_targets, owner_to_target, resolved_enemy_group, source_to_target, selected_card, owner_to_selected_card, converted_attack_card, converted_other_card, draw_pile_to_hand, source_pile_to_hand, card_to_discard_pile, exhausted_card, played_card, card_cost_anchor, damaged_target_to_owner`。
- 3 个「两点」特效带 `segment_anchors_px`：`counter_release [30,128]→[224,128]`、`lightning_chain [30,128]→[224,128]`、`lifesteal` **反向** `[216,142]→[40,142]`（源=被吸者）。
- 循环特效 2 个：`domain_loop`（48 帧 2 s）、`mark_bite`（36 帧 1.5 s，咬痕持续标记）。
- 图集 JSON 字段：`id, label_zh, family, fps, frame_count, duration_seconds, loop, anchor, layer_z, blend_mode, alpha_mode, pivot_px, content_bbox, atlas{image,json,columns,rows,tile_size,sha256}, frames[{index,time_seconds,rect,path,sha256}], audio_cue, audio_policy, lifecycle, source_geometry`。

### 4.2 `card_vfx_bindings.json` schema 与语义

- 顶层：`schema_version 1`、`binding_kind=portable_semantic_presentation_contract_not_native_game_api`（明确不是游戏原生 API）、`card_count 89`、`card_source_sha256`、`mechanics_source`、`primary_motion_source`、`required_payload`、`policy{dedup,no_rules,multiplayer,death,selection_cancel,capacity,layering,audio,speed,flashes,unsupported_unknown_source}`、`global_rule_cues[]`、`cards[]`。
- `required_payload`：`battle_id, owner_id, event_id, card_entity_id, target_entity_id_or_list, resolved_result, event_order` —— 即「规则层已结算事件」的最小载荷；表现层只消费它。
- 每卡：
  - `primary_motion{clip, trigger:on_play, max_starts_per_play:1, visual_only, blocks_gameplay:false, domain_variant, end_state, interruptible_by[], marker_policy}` —— 身体动作。
  - `cues[{semantic_key, event, effect_id, anchor, guard, audio_cue, scope, order, blocks_gameplay, dedup_key[battle_id,owner_id,event_id,effect_id,target_entity_id]}]` —— 逐事件特效。
- 覆盖：89 卡 / **219 条 cue**，用 32 个不同 effect；主动作分布 `cast 34, attack 15, block 14, attack_heavy 10, feral_enter 6, counter 3, relaxed_loop 3, roar 2, bite 1, storm_leap 1`。单卡 cue 数：1 条(17 卡) / 2 条(31) / 3 条(27) / 4 条(12) / 5 条(1, R30) / 6 条(1, R31)。
- 全局规则 10 条（8 条带 effect）：`thunder_growth_committed→lightning_growth`、`domain_attack_bonus_thunder_resolved→lightning_strike`、`domain_state_changed→domain_loop`、`domain_suppression_applied→domain_suppress`、`domain_purification_committed→card_purify`、`incoming_attack_blocked→guard_hit`、`counter_thunder_resolved→counter_release`、`feral_transformation_committed→feral_aura`；另 2 条生命周期规则无 effect（`bite_mark_removed`、`owner_died_or_battle_ended`）。

### 4.3 与游戏原生入口的关系（已核到游戏程序集）

我在本机安装的 `sts2.dll`（v0.107.1）与其 XML 文档中核实到：

```
M:MegaCrit.Sts2.Core.Commands.Builders.AttackCommand.WithHitFx(System.String,System.String,System.String)
   <param name="vfx">File path of the VFX.</param>
   <param name="sfx">File path of the SFX.</param>
   <param name="tmpSfx">Temporary SFX file path. If the attack uses temporary non-FMOD SFX,
                         pass this instead of sfx using keyword args.</param>
另有 WithHitVfxNode(...) = 命中时把自定义 VFX 节点加进战斗 VFX 容器
    WithHitCount(...) = 多段命中
    DamageCmd.Attack(decimal) / Attack(CalculatedDamageVar) = 入口
```

- 官方 cookbook 用法：`DamageCmd.Attack(...).FromCard(this).Targeting(...).WithHitFx("vfx/vfx_attack_slash").Execute(ctx)`，非 FMOD 音效示例 `.WithHitFx("vfx/vfx_attack_blunt", null, "heavy_attack.mp3")`。
- 游戏内 `vfx/*` 是 **Godot 场景资源**：我在 `SlayTheSpire2.pck` 里 grep 到 `res://vfx/...` 形式的 `vfx_attack_slash`、`vfx/big_slash/vfx_big_slash_impact_core.tscn`、`vfx/cards/exhaust_vfx.tscn` 等，配合 `MegaCrit.Sts2.Core.Nodes.Vfx.*`（如 `NBolasVfx`）C# 场景与 `NCombatVfxSpawner`。→ **`WithHitFx` 的 vfx 参数期望场景/事件路径，不是 PNG 图集**。
- 因此我们的 40 组图集要落到命中事件，只有三条路：
  1. 为每组特效包一个 `Node2D`+`AnimatedSprite2D`（AtlasTexture）的 `.tscn`，把 `res://` 路径传给 `WithHitFx` —— 是否接受 Mod PCK 内任意路径**未验证**。
  2. `WithHitVfxNode(PackedScene/Node)` 直接把自定义场景挂到战斗 VFX 容器（更贴近「自定义节点」语义，**推荐**）。
  3. 完全绕开原生入口：卡牌 `OnPlay` 里结算后自行 `Spawn` 到 `CenterPos/target` 的 holder 节点（交付 `VolibearVfxPlayer` 就是这套），原生 `WithHitFx` 只填 `null` 或基础音效。
- **坐标如何传**：原生入口不接收坐标，它把 VFX 挂到已经解析的目标节点上（target_contact/target_ground 类锚点天然满足）。我们的多数锚点（`target_contact/target_ground/owner_*/selected_card/...`）都需要宿主解析成实际节点位置；两点特效必须按 `segment_anchors_px` 做二维基变换（`HOST_HOOKS.md:11,15`），`roar_wave` 另有局部偏移 +`(73,0)` 修正（pivot x=128，波前 x=55）。抽象锚点（抽/取/弃/减费/所选牌）必须绑定真实卡牌节点，不能用角色本体代替。
- 按 XML 文档措辞（`sfx`=“File path of the SFX”，`tmpSfx` 专门用于 “temporary non-FMOD SFX”）推断 `sfx` 是 FMOD 事件路径（见 §5.4）；`tmpSfx` 才是非 FMOD 文件路径——这正好是「不建 bank 时把 Ogg 绑到命中的官方口子」，但 `tmpSfx` 的路径解析规则（是否 `res://`、是否只接受内建资源）**未验证**。

### 4.4 缺口

1. **4 个特效没有任何卡牌/全局绑定行**：`domain_exit`、`feral_body`、`lightning_all`、`lightning_chain`。其中 `lightning_all`（全体雷伤）与 `lightning_chain`（连锁）是卡表确实需要的语义，需补绑定（连到 `domain_strike_all`/`雷伤` 事件）；`domain_exit` 属领域退出全局事件；`feral_body` 属兽化非攻击牌转化。
2. **无 `.tscn`**：40 组只有图集+JSON，没有一个可被 `WithHitFx`/`WithHitVfxNode` 直接吃到的场景。这是「能播」和「能被游戏命中系统调用」之间最大的缺口。
3. 循环语义不一致：VFX 里 `mark_bite` 是 loop，音频 `sfx.mark_bite` 非 loop（一次性）；音频 `sfx.feral_aura` 是 loop，但 VFX `feral_aura` 非 loop。宿主必须按 cue 维度分别处理，不能按 effect_id 一刀切。
4. `WithHitVfxNode` 是否接受 Mod 内 `PackedScene`、是否要求注册到某个容器/池，**未验证**（需在游戏内做一次最小实验）。
5. 破坏性边界：contract 明确「表现层不改规则、不等待 VFX 完成、不读 VFX 判断命中」；但 219 条 cue 的事件名（如 `physical_damage_resolved`）都是**本项目自造语义名**，需要与 task-2 的卡牌实现逐一对齐事件发出点（例如 `DamageCmd.Attack(...).Execute()` 之后/hit 回调里发）。

---

## 5. 音频（47 OGG / 54 cue）

### 5.1 文件与 cue 构成

- 47 个 OGG：Vorbis，**48 000 Hz / 单声道**，时长 0.230–4.000 s，合计 **45.254 s**；另有 47 个 PCM16 WAV 母版（不进 PCK）。
- 54 个逻辑 cue = 47 个 asset；**7 个文件被 2 个 cue 复用**：`charge`(sfx.charge/sfx.strength)、`domain_suppress`(sfx.domain_suppress/sfx.weakness)、`energy_gain`(sfx.energy_gain/sfx.cost_reduce)、`guard_gain`(sfx.guard_gain/sfx.armor_retain)、`guard_hit`(sfx.guard_hit/sfx.armor_iron)、`lightning_growth`(sfx.lightning_growth/sfx.thunder_armor)、`mark_bite`(sfx.mark_bite/sfx.wound)。
- 按文件：13 个角色发声 + 34 个音效/环境；按 cue：Voice 13 / Sfx 39 / Ambience 2。
- 循环 2 个：`sfx.domain_loop`（Ambience，4.0 s，max_voices 1）、`sfx.feral_aura`（Ambience，4.0 s，1）。
- 限流：SFX `cooldown_ms 60`（`lightning_growth/domain_suppress/card_draw/thunder_armor` 为 250，`footstep` 90）、`max_voices 4`；Voice `cooldown 200`（`low_health` 1800）、`max_voices 1`；`gain_db` 除 `footstep=-3` 外均为 0。
- 混音规则（`mix_rules`）：voice -3、sfx -3、ambience -6、headroom 6 dB、master soft limit -1 dBTP、loop 淡出 140 ms、随机化用「独立装饰性计数器，绝不消耗游戏 RNG」。

### 5.2 `action_cues.json` 时序契约

- `schema_version 1`、`animation_motion_sha256`（绑定 `rig/motions.json`）、`purpose` 明确「离线时序预览与适配示例；实际伤害/VFX 以已结算游戏事件为准」。
- 26 条 clip，每条：`events[{time_seconds, cue, reason}]`、`state_entry_only[cue]`、`replay_loop_behavior`、`cancel_policy`。
- 关键点：
  - **一次性事件按秒触发，不在每帧重播**；循环动作只在进入时触发 `state_entry_only`（`weak_loop→voice.low_health`、`domain_idle→sfx.domain_loop`、`domain_weak_loop→voice.low_health + sfx.domain_loop`），循环回绕不重播。
  - 攻击类：`attack` 0.08 `voice.attack_01` + 0.54 `sfx.claw_slash`；`attack_heavy` 0.08/0.80；`bite` 0.08/0.53；`cast` 0.08/0.90；`hurt` 0.08/0.12；`block` 0.28/0.48；`counter` 0.35/0.52/0.84；`roar` 0.36/0.52；`storm_leap` 0.08/0.46/1.44/1.63；`domain_enter` 0.08/0.88；`domain_exit` 0.90；`die` 0.08/1.22；`domain_die` 0.08/1.12/1.22；`feral_enter` 0.08/0.92。
  - 取消策略：中断时取消**未来** cue；已开始的非循环尾音自然结束；状态循环在退出/死亡/清场时停。新动作取消旧时间线的未来 cue。
  - 与事件表对齐示例：`attack` 的 `impact` 在 0.540 s（`EVENTS.md`）与 `sfx.claw_slash` 0.54 s 一致；`storm_leap` 的 `takeoff/apex/landing_impact/aftershock` = 0.46/0.92/1.44/1.63 与 4 个 cue 对齐。
  - 9 个 cue 不出现在 action_cues 也不在卡牌绑定里：`voice.select`、`voice.victory`（原生角色槽用）、`sfx.footstep`（环境）、`voice.attack_02`/`voice.hurt_02`（备选变体）、`sfx.domain_suppress`/`sfx.feral_aura`（全局规则按 `sfx.<effect_id>` 约定解析）、`sfx.feral_body`/`sfx.lightning_chain`（需补所有权）。

### 5.3 5 个原生角色音效槽与去重策略

- RitsuLib `CharacterAudioAssetSet`（`CharacterAssetProfile.cs:187-193`）正好 5 个：`CharacterSelectSfx / CharacterTransitionSfx / AttackSfx / CastSfx / DeathSfx`，全部为字符串。
- BaseLib `CustomCharacterModel` 只有 3 个：`CustomAttackSfx / CustomCastSfx / CustomDeathSfx`（`CustomCharacterModel.cs:107-109`）；选择/转场若要换，得靠 RitsuLib 的 5 槽。**受伤音没有原生槽**，必须从受击事件走自己的 cue（不要捏造 `CustomHurtSfx`）。
- 默认回退是**原版 ironclad 的 FMOD 事件路径**（`CharacterAssetProfiles.cs:15-68`：`DefaultPlaceholderCharacterId="ironclad"`，`event:/sfx/characters/ironclad/ironclad_attack` 等；`PlaceholderCharacterId` 在 `ModCharacterTemplate.cs:526`，空/null 不等于静音）。
- 交付建议（`VolibearNativeAudioAssets.CharacterSlots()`）：5 槽填 `res://VolibearArt/audio/ogg/voice_select.ogg / cast_charge.ogg / voice_attack_01.ogg / voice_cast.ogg / voice_death.ogg`；BaseLib `PlayResourcePatch` 会把 `NAudioManager.PlayOneShot` 的合法 `res://` 路径转进 `ModAudio`（源码存在；**未实机验证**）。
- **去重原则**：同一事件只能有一个所有者。若用原生槽接管 attack/cast/death/select/transition，则必须从自定义 cue 时间线中移除这 5 个事件（对应 `voice.attack_01`、`voice.cast`、`voice.death`、`voice.select`，以及 transition 用的 `cast_charge`）；受伤（`voice.hurt_01/02`）、低血、咆哮、兽化、胜利等仍走时间线。
- 循环去重：`sfx.domain_loop`/`sfx.feral_aura` 同 ID 不重复创建，退出/死亡/清场必须显式停（不能靠下一张牌顺带停），`EndCombat()` 提前清理。

### 5.4 FMOD bank 缺口

- 游戏本体确实用 FMOD：安装目录有 `libfmod.so`/`libfmodstudio.so`，PCK 内有 `Master.bank / Music.bank / ambience.bank / act1_a1.bank …`；RitsuLib 原生槽默认值确实是 `event:/...` FMOD 事件；`WithHitFx` 的 `sfx` 参数按 XML 文档（与 `tmpSfx` 的 “non-FMOD” 对照）推断同为 FMOD 事件路径，工程上应视为未验证。
- **没有沃利贝尔的 `.bank`**，也没有 FMOD 工程；47 个 Ogg **不能**直接当 `event:/` 事件用。RitsuLib 有 `FmodStudioDeferredBankRegistration.RegisterBank` 能力，但本轮未制作 bank。
- 因此当前只有两条可行路线：①（不建 bank）`res://` Ogg + 原生 `AudioStreamPlayer`/BaseLib 资源桥 + 自有 cue 时间线；②（要 FMOD 事件）先做 bank 再注册。`tmpSfx` 参数给了第③条「命中时播非 FMOD 文件」的口子，但解析规则未验证。
- 音量桥：`VolibearCueAudio` 用原生 `AudioStreamPlayer`，宿主必须提供 `currentGameVolume(bus)`（返回尚未乘进 Master 总线的增益，0–1）并 `RefreshGameVolume()`；若框架已同步 Master 主音量，回调只返回残余 SFX/Voice 增益，避免乘两次。
- `audio/official/` 里 153 个 Riot 原版录音（en_us/zh_cn）是**研究归档**：与 47 个运行文件 SHA 零重叠、`manifest.official_character_voice=false`；许可与 IP 归属独立记录（`official/CREDITS.md`），**不应打进 Mod 分发**。

### 5.5 缺口

1. 无 FMOD bank（若产品要求 FMOD 事件则必须补；否则固定走原生 Ogg 路线并在文档声明）。
2. 与 VFX 循环语义不一致（mark_bite / feral_aura），需宿主按 cue 分别处理。
3. `voice.attack_02`、`voice.hurt_02` 两个变体无人引用（可做随机变体，需固定「不消耗游戏 RNG」的装饰随机）。
4. 无 `CustomHurtSfx` 之类原生槽 → 受伤音必须由项目事件发，不能等游戏自动播。
5. 全部声音只在 Godot 离线自检中解码验证（54 个入口），**未在游戏 FMOD/总线环境下验证音量与并发**。

---

## 6. UI 与机制图标

### 6.1 14 张角色 UI（`ui/images/`，实测通道）

| 文件 | 实测 | 建议槽位（RitsuLib `CharacterUiAssetSet` / 其他） | 槽位类型 | 状态 |
|---|---|---|---|---|
| `character_icon_volibear.png` | 128×128 RGBA | `Ui.IconTexturePath` | Texture2D（png 路径） | 可直接接 |
| `character_icon_volibear_outline.png` | 128×128 RGBA | `Ui.IconOutlineTexturePath` | Texture2D | 可直接接 |
| `char_select_volibear.png` | 132×195 RGBA | `Ui.CharacterSelectIconPath` | Texture2D | 可直接接（模板图为 RGB 不透明，建议导出前去 alpha 或确认渲染无黑边） |
| `char_select_volibear_locked.png` | 132×195 RGBA | `Ui.CharacterSelectLockedIconPath` | Texture2D | 同上 |
| `char_select_volibear_master.png` | 528×780 RGBA | 编辑母版 | — | **不运行**，仅编辑源 |
| `char_select_volibear_locked_master.png` | 528×780 RGBA | 编辑母版 | — | **不运行** |
| `map_marker_volibear.png` | 128×128 RGBA | `Ui.MapMarkerPath` | Texture2D | 可直接接 |
| `big_energy.png` | 74×74 RGBA | 卡池/遗物池/药水池 `BigEnergyIconPath` | Texture2D 路径 | 可直接接 |
| `text_energy.png` | 24×24 RGBA | 同名 `TextEnergyIconPath` | Texture2D 路径 | 可直接接 |
| `big_energy_empty.png` | 74×74 RGBA | 能量计数器场景的空状态贴图 | 输入素材（非槽位） | 需场景 |
| `energy_master.png` | 256×256 RGBA | 能量图标母版 | 输入素材 | 需场景 |
| `character_fallback.png` | 512×512 RGBA | 静态 Sprite2D 回退 | 仅回退 | **不能**当战斗场景 |
| `character_select_background.png` | 1920×1080 RGBA | `Ui.CharacterSelectBgPath`（当前 RitsuLib 工厂：先找 PackedScene，找不到再包 Texture2D 成全屏 TextureRect） | Scene 优先 / Texture2D 回退 | 可回退接，但**换版本可能失效** |
| `character_select_transition.png` | 1920×1080 RGBA（含透明） | `Ui.CharacterSelectTransitionPath` **要求 Material** | **Material** | ❌ 不能直接填 PNG；需 `.tres` 材质包装，未完成 → 原版回退 |

补充槽位（未交付，必须原版回退或自建）：`Scenes.VisualsPath`（战斗场景，必需）、`Scenes.EnergyCounterPath`（**PackedScene**，交付只有贴图）、`Scenes.MerchantAnimPath` / `RestSiteAnimPath`（场景；RitsuLib 当前支持静态纹理回退，可用 `relaxed_loop` 包装）、`Vfx.TrailPath`（**场景**，需满足拖尾节点结构，单图不行）、`Ui.IconPath`（可选场景）。

### 6.2 16 组机制图标（`vfx/icons/`）

- 16 个 id × 4 尺寸（256/128/64/32）= 64 PNG（`png_count=64`）+ 16 SVG；`manifest.json` 每尺寸带 SHA，SVG 标可编辑矢量、无字体字形/官方图标入 PNG。
- 到框架的映射：Power/状态图标 → RitsuLib `PowerAssetProfile.IconPath`(64×64) / `BigIconPath`(256×256)（模板实测 64/256）；遗物 → `RelicAssetProfile`（模板 94/256，未制作）；药水 → `PotionAssetProfile`（256，未制作）。
- 16 个 id：`thunder_growth, domain, feral, bite_mark, counter_thunder, charge, enhance, retain_armor, iron_armor, purify, thunder_armor, replay, lifesteal, cost_reduce, energy, domain_suppress`。
- **与 17 条关键词的覆盖缺口**：`雷伤`/`雷法`（雷电伤害类型）、`迎战`、`吸收`、`检索／回收` 没有对应图标（`energy`=返能、`domain_suppress`=领域压制属机制状态而非关键词）。要么补 4 个图标，要么在 UI 层显式声明复用（如 雷伤 复用 `thunder_growth`、迎战/吸收 复用 `counter_thunder`）。
- 数值叠层、本地化文本、能力 ID 由规则/UI 层注册，图标 PNG 不含文字（正确）。

### 6.3 必须原版回退（本轮不制作，`ui/manifest.json.reuse_decisions` 已声明）

`merchant`/`rest_site` = `relaxed_loop` 复用；`revive` = 显式回待机；`card_frames` = 原版 UI 框 + 89 张自家插画；`background_music` = 原版；`multiplayer_point_and_rps` = 原版手势；`yummy_cookie_relic` = 原版；`phobia_mode` = 不适用；台词/主题曲 = 不做。

---

## 7. 接入清单、缺口与验证状态

### 7.1 资源 → 目标 `res://` → 注册位置

命名空间沿用交付 PCK：`res://VolibearArt/`（由 `stage_assets.py` 强制目录名 `VolibearArt`，吃掉 `animations/vfx/audio/ui` 四个清单及其条目）。

| 资源 | 目标 `res://` 路径 | 注册位置 / 代码 | 类型 |
|---|---|---|---|
| 动画清单 | `res://VolibearArt/animations/manifest.json` | `VolibearSpriteFrames.Load(path)`（须在 PCK 里保留 JSON，非 Godot 资源） | JSON（FileAccess） |
| 26 角色图集 | `res://VolibearArt/animations/atlases/<clip>.png` + `.json` | 同上 → `AtlasTexture{Region=rect, FilterClip=true}` → `SpriteFrames.AddFrame`；last: `SetAnimationSpeed(clip, fps)`、`SetAnimationLoop` | Texture2D + JSON |
| 角色 SpriteFrames | 运行时构建，或离线烘焙成 `res://Volibear/animations/volibear_spriteframes.tres` | `AnimatedSprite2D.SpriteFrames` | SpriteFrames |
| 战斗场景 | `res://Volibear/scenes/creature_visuals/volibear.tscn`（**待建**） | `CharacterAssetProfile.Scenes.VisualsPath`；或 BaseLib `CustomVisualsPath` | PackedScene（NCreatureVisuals） |
| 状态机 | 代码注册 | 重写 `ModCharacterTemplate.SetupCustomCombatAnimationStateMachine(Node, CharacterModel)` → 返回 `VolibearSpriteFrames.CreateMachine(sprite, flags)` | C# |
| VFX 清单 | `res://VolibearArt/vfx/manifest.json` | `VolibearVfxPlayer` 加载 | JSON |
| 40 特效图集 | `res://VolibearArt/vfx/atlases/<id>.png` + `.json` | `VolibearVfxPlayer`（AtlasTexture + 源/目标锚点 + layer_z + token 停止） | Texture2D + JSON |
| 特效场景（待建） | `res://Volibear/vfx/<id>.tscn` | `WithHitVfxNode(...)` 或 `WithHitFx("res://…/<id>.tscn")`（路径接受性未验证） | PackedScene（Node2D） |
| 卡牌→VFX 绑定 | `res://VolibearArt/vfx/card_vfx_bindings.json` | `VolibearPresentationController` + 卡牌 `OnPlay`/伤害事件；全局规则订阅 | JSON |
| 音频清单 | `res://VolibearArt/audio/manifest.json` | `VolibearCueAudio` | JSON |
| 47 OGG | `res://VolibearArt/audio/ogg/<asset>.ogg` | `VolibearCueAudio.Play(cueId)`；或 5 个原生槽 | AudioStreamOggVorbis |
| 动作音效时间线 | `res://VolibearArt/audio/action_cues.json` | `VolibearPresentationController.Present(clip, committedSeq, cues)` | JSON |
| 声音 bus/音量 | 代码（宿主回调） | `currentGameVolume(bus)` + `RefreshGameVolume()` | C# |
| 角色 UI 纹理 | `res://VolibearArt/ui/images/*.png` | `VolibearUiAssets.Textures()` → `CharacterAssetProfile.Ui` | Texture2D |
| 能量图标 | `res://VolibearArt/ui/images/big_energy.png`、`text_energy.png` | 卡池/遗物池/药水池 `BigEnergyIconPath`/`TextEnergyIconPath` | string |
| 转场材质（缺） | `res://Volibear/materials/volibear_transition_mat.tres` | `Ui.CharacterSelectTransitionPath` | **Material** |
| 能量计数器（缺） | `res://Volibear/scenes/combat/volibear_energy_counter.tscn` | `Scenes.EnergyCounterPath` | **PackedScene** |
| 商店/篝火（缺/回退） | `res://Volibear/scenes/merchant/volibear_merchant.tscn` | `MerchantAnimPath`；或静态纹理回退 | PackedScene |
| 机制图标 | `res://VolibearArt/vfx/icons/{64,256}/<id>.png` | `PowerAssetProfile.IconPath`/`BigIconPath` | string |
| 卡图 大/小 | `res://Volibear/images/card_portraits/big/<asset_key>.png`、`res://Volibear/images/card_portraits/<asset_key>.png` | BaseLib `CustomPortraitPath`（单图）；RitsuLib `CardAssetProfile.PortraitPath`；文件名规则 = 卡类 ID 去前缀小写 | Texture2D 路径 |
| 卡图（可选 beta） | `res://Volibear/images/card_portraits/beta/<key>.png` | `BetaPortraitPath` | 未制作 |
| 卡框/遮罩 | 原版 / `CardAssetProfile.FramePath` | 原版回退 | — |
| 原生 5 槽声音 | `res://VolibearArt/audio/ogg/voice_*.ogg` 等 | `CharacterAssetProfile.Audio`（RitsuLib 5 槽）或 BaseLib 3 槽 | string |
| 模组 manifest / 程序集 | `mods/Volibear/…` | 平台层，见 task-1 | — |

### 7.2 缺口清单（按优先级）

**P0 — 不做就无法在游戏里跑起来**
1. 无编译程序集、无 Mod manifest、无 `[ModInitializer]` 入口（平台层任务）。
2. 无 `NCreatureVisuals` 战斗场景（Visuals/Bounds/IntentPos/CenterPos）；无 SpriteFrames `.tres` 或运行时构建接线。
3. VFX 只有图集，无 40 个 `.tscn`；`WithHitFx` 需要场景路径/事件路径。
4. `EnergyCounterPath` 需要 PackedScene，只有贴图。
5. `CharacterSelectTransitionPath` 需要 Material，只有 PNG。
6. 事件发射点未实现：219 条 cue 的 `event` 是自造语义名，须在卡牌/能力实现中真实发出（否则绑定表空转）。

**P1 — 影响完整度/正确性**
7. 4 个 VFX 无绑定：`domain_exit`、`feral_body`、`lightning_all`、`lightning_chain`。
8. 4 个关键词无图标：雷伤/雷法、迎战、吸收、检索／回收（或显式声明复用）。
9. FMOD bank 缺失；需在原生 Ogg 路线与 FMOD 路线间做一次拍板并写进发布说明。
10. 循环语义 VFX/音频不一致（mark_bite、feral_aura）；`voice.attack_02`/`hurt_02` 未接线。
11. 卡类 ID 与 `asset_key` 必须严格一致，否则模板静默回退 `card.png`（89 张会全变默认图）。

**P2 — 表现力/可选**
12. 无 beta 卡图、无 full-art（606×852/250×350）变体。
13. 无复活/胜利独立动画（已声明回退）；无多人手势。
14. 商店/篝火用 `relaxed_loop` 包装，未做独立坐姿。
15. `char_select_volibear*.png` 交付 RGBA（模板为 RGB 不透明），需确认合成无黑边或去 alpha。
16. `char_select_volibear_master.png` / `locked_master` 是 528×780 编辑母版，别打进运行时。

**P0-内容 — v6 卡图（见 §7.4）**
17. 89 张中 60 张用户判返工，0 张已重绘；当前游戏导出仍是 v5 母版。

### 7.3 验证状态矩阵（关键区分）

| 项目 | 离线 Godot 4.5.1 已验证 | 游戏内（v0.107.1）未验证 |
|---|---|---|
| 26 角色图集 / 940 帧可构造 SpriteFrames、帧区合法 | ✅ `godot_self_test.json passed=true` + `validation_report.json passed=true`（26 图集/940 帧/53 事件/26 GIF） | ❌ 未注册角色、未播动作 |
| 40 特效图集 / 1070 帧可解码、两点锚点映射、循环去重与释放 | ✅ 自检通过（端点误差 <0.01 px） | ❌ 未与 `WithHitFx`/`WithHitVfxNode` 联调 |
| 54 个声音入口可解码、循环/停止/释放 | ✅ 自检通过（47 个不同 Ogg） | ❌ 未在 FMOD/总线环境验证音量与并发 |
| 14 张 UI PNG + 16 组图标（64 PNG + 16 SVG）可加载 | ✅ PCK 隔离挂载解码通过 | ❌ 未注册到任何角色槽 |
| `res://VolibearArt/` PCK | ✅ 126 933 504 B，隔离空工程挂载 `passed=true` | ❌ 不等于已注册 Mod |
| C# 接入样例（6 个文件） | ❌ 未编译（`integration_source_uncompiled`，本机无 .NET SDK，只有 runtime） | ❌ |
| 卡图尺寸/通道/数量 | ✅ 89×2（STS2）+89×2（STS1）像素与 SHA 校验通过；与模板实测尺寸一致 | ❌ 未进游戏卡面/牌库界面 |
| 卡框、费用、稀有度、描述 | 由游戏 UI 负责（模板/wiki 口径） | ❌ |
| 角色 UI 槽位类型 | 部分 ✅（Texture2D 槽按源码核对） | ❌ 选角/顶栏/地图/转场均未实机 |

### 7.4 v6 卡图评审进度（正在生成的包）

`volibear_cards_art_review_v6/`（2026-10-27 23:29–2026-10-28 01:12）是**审查 + 设计交接包，不是重绘产物**：

- 覆盖：89 张逐张审查（`reviews/audit_bc|rt|u`、`REVIEW_AND_REDESIGN.md` 170 KB）；29 张用户固定保留（`assets/benchmarks/`，原字节）；60 张返工方案 + 60 份提示词（`prompts/`）；`assets/current/`=89 张当前原图（供比对，不覆盖）；`assets/small/` 89 张 250×190、`assets/tiny/` 89 张 125×95。
- 队列：`data/generation_queue.json` = `status not_started / total 60 / completed 0 / pilot_ids 8`；`data/redesign_plan.json` 60 条。
- 结论：**本轮新绘制图片数 0**。卡仓库与 v6 包都没有 2026-10-28 之后的新卡图（`volibear_cards_repo` 无 >10-28 的文件）；因此**当前可用于接入的卡图仍是 v5 的 89 张**，60 张属「技术可用、内容待替换」。
- 动画侧同期更新：`reports/animation_revision_v6/v7/v8` + `animations/skeletal_v6/v7/v8` + `exports/Volibear_V7_editable_animation.zip`（482 793 371 B，10-28 02:14）。v6 状态 `superseded_by_v7`、v7 `user_rejected_joint_motion_and_layering`、v8 `rejected_anatomical_partition`、`art_approved=false`、`complete=false`。→ **接入继续以 `animations/clean/`（v5）为唯一合同**，不要指向 skeletal_v*。

---

## 附录 A：证据与出处

**本仓库文件（行号为快照）**
- `volibear_animation_repo/animations/README.md:21-30`（交付文件表）、`:77-85`（骨骼/素材规格、pivot、8 列）、`:96-108`（时序/事件）、`:110-120`（状态选择与接入方式）、`:163-169`（校验范围）。
- `animations/EVENTS.md`（53 事件全表）。
- `vfx/card_vfx_bindings.json`（policy 11 条、required_payload、global_rule_cues 10 条）。
- `vfx/CARD_BINDINGS.md`（89 卡逐卡语义与时序注意）。
- `audio/manifest.json`（mix_rules、cue 字段）、`audio/action_cues.json`（26 clip 时间线）、`audio/CREDITS.md`。
- `integration_sts2_v5/docs/HOST_HOOKS.md:7,11-13,15,17,23,36,42,44,46,50,52`（场景/锚点/事件/领域/兽化/音量/去重/联机边界）。
- `integration_sts2_v5/src/VolibearSpriteFrames.cs:44-52,97-132,155-206`（26 序列、帧时长相对值、状态机条件、terminal、feral TTL）。
- `integration_sts2_v5/src/VolibearUiAssets.cs`、`VolibearNativeAudioAssets.cs`（槽位映射与 5 槽路径）。
- `integration_sts2_v5/reports/VERIFICATION_STATUS.md`、`reports/godot_self_test.json`、`exports/VolibearArt_v5.report.json`。
- `volibear_cards_repo/README.md`（四套导出尺寸/无卡框/89 张）、`config/export_profiles.json`、`scripts/card_repo.py:73-84`（25:19 门禁 + `ImageOps.fit` LANCZOS）、`data/*`。
- `volibear_cards_art_review_v6/README.md`、`00_GOAL.md`、`data/generation_queue.json`。
- `volibear_reference_repo/research/{STS2_SUPPORT_V5.md, UI_PROFILE_MAP.md, ART_ASSET_COMPLETENESS_CHECKLIST.md, ASSET_SCOPE_TR.md, CHARACTER_ASSET_SCOPE.md, ANIMATION_RESEARCH.md, native_animation_inventory.json, project_animation_mapping.json}`。

**外部（本轮实测/抓取，2026-10-29）**
- ModTemplate-StS2 `@2c900a04dd2073872f677f4fb78ee2ad1e871009`：`content/CharacterModTemplate/CharMod/images/**` PNG 实测尺寸（250×190、1000×760、132×195、128×128、74×74、24×24、64×64、256×256、94×94）；`CharModCode/Cards/CharModCard.cs`（1000×760/606×852、250×190/250×350、beta）；`CharModCode/Extensions/StringExtensions.cs`（`res://<ModId>/images/card_portraits[/big]`）；`CharModCode/MainFile.cs`（`ResPath=res://CharMod`）；wiki `Adding-Cards`（同名规则、可选小图）；wiki `Common-Commands-Cookbook`（`WithHitFx("vfx/vfx_attack_slash")`、`.WithHitFx(..., null, "heavy_attack.mp3")`）。
- BaseLib-StS2 `@c070755d11ec062f6c97c4dda1a205d975ed066a`：`Abstracts/CustomCardModel.cs`（CustomPortraitPath/CustomFrame/CustomFrameMaterial/BannerMaterial 与 Harmony 补丁点）、`Abstracts/CustomCharacterModel.cs:107-109`（3 个 Sfx 槽）、`Utils/CustomAnimation.cs:14-19,102-115`（探测顺序与 AnimatedSprite2D 支持）。
- RitsuLib `@772f280964f2efc7c7e2f29fc59844e68616dd57`：`src/Scaffolding/Characters/CharacterAssetProfile.cs`（Scene/Ui/Vfx/Audio/Multiplayer 槽位类型，含 `CharacterSelectTransitionPath`=Material 注释）、`CharacterAssetProfiles.cs:15-68`（ironclad 默认回退 + FMOD 事件路径）、`ModCharacterTemplate.cs:706-774`（`SetupCustomCombatAnimationStateMachine` 与 obsolete 别名）、`src/Scaffolding/Content/ContentAssetProfiles.cs:356`（`CardAssetProfile` 字段）、`src/Scaffolding/Visuals/StateMachine/Backends/AnimatedSprite2DBackend.cs`。
- BaseLib wiki `docs/scenes/creature-visuals.html`（NCreatureVisuals 必需节点表：Visuals/Bounds/IntentPos/CenterPos/OrbPos/TalkPos/PhobiaModeVisuals；自动动画名 idle/attack/cast/hurt/die）。
- 本机游戏 `data_sts2_linuxbsd_x86_64/sts2.xml`：`AttackCommand.WithHitFx(string vfx, string sfx, string tmpSfx)` 及参数说明；`DamageCmd.Attack(...)`；`SlayTheSpire2.pck` 内 `res://vfx/*.tscn` 路径与 `Master.bank/Music.bank/ambience.bank/act*.bank`；`libfmod*.so`。

## 附录 B：`asset-manifest.json` 结构

顶层：`audit`（快照日期、三仓库 git HEAD/干净状态）、`verification`（离线已验证 / C# 未编译 / 游戏内 UNVERIFIED）、`animation`（画布/pivot/fps/state_rules/24 clips+2 variants 明细，每项含帧数、时长、循环、图集网格、bbox、事件）、`animation.newer_experimental`（v6/v7/v8 状态，勿用）、`vfx`（40 特效明细 + `card_bindings` 89 卡/219 cue/10 全局规则）、`audio`（47 文件 ffprobe 实测 + 54 cue + action_cues + research_only）、`ui`（14 资产 + 16 图标 + reuse_decisions）、`cards`（89 卡逐项 master/STS2 大图/小图/STS1 两套路径+尺寸+模式+SHA，导出规则）、`cards_v6_review`（进度）、`runtime_pack`（PCK 大小/SHA/引擎验证计数）、`pipeline_scripts`（5 个脚本/配置 SHA）。所有 SHA 均为 2026-10-29 快照重算值。
