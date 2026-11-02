# 两套运行音频

`open` 是默认、完整、离线可构建的音频方案：保留已批准的 **47 个声音 / 54 个 cue**。录音原料为 CC0；本项目原创声音设计按仓库的 CC BY-SA 4.0 授权，工具代码仍为 GPL-3.0-only。完整作者、下载地址和原始 SHA256 见 `../sources.json`、`../CREDITS.md`；这里没有改变仓库或第三方许可。

`riot_en` 是显式选择的私有音频方案：在同一份完整资源包中增加 **9 个英文角色发声和 2 个 Q 研发音效**，覆盖 11 个既有 cue，其余 43 个 cue 使用完整的开放音频。Riot 录音及其处理副本不进入公开 Git，也不被改标为 CC0、CC BY-SA 或 GPL。公开仓库仅保存来源、固定摘要、编辑参数和构建工具。

## 可复现命令

在仓库根目录运行；准备/验证需要 Python、NumPy、ffmpeg、ffprobe。PCK 构建沿用现有 Godot 4.5.1 Mono 和 .NET 9 配置。
完整交付入口 `tools/local_delivery.py --verify-release --audio-profile riot_en` 会按需在
`.local/build-python` 创建独立 Python 环境，不修改全局 Python；直接运行下面的准备/验证命令时，
可使用该环境的 Python（Linux：`.local/build-python/bin/python3`）。
离线源码构建须同时保留 `.local/audio-profiles/originals/` 与 `prepared/riot_en/`，仅处理后的音频
不足以通过原始来源摘要校验。已打包的玩家安装 ZIP 不需要这两份构建目录或 FFmpeg。

```bash
# 完整核对默认音源、授权记录、哈希和解码，不联网。
python tools/audio_profiles.py verify --profile open

# 普通公开 GET；已有文件必须匹配固定字节数和 SHA256，否则拒绝覆盖。
python tools/audio_profiles.py fetch --profile riot_en

# 下载缺失文件，生成私有播放副本，保留原文件。
python tools/audio_profiles.py prepare --profile riot_en
python tools/audio_profiles.py verify --profile riot_en

# 一步完成获取、处理、验证、完整 PCK 构建和私有资源安装 ZIP。
python tools/audio_profiles.py package --profile riot_en --godot /path/to/Godot_4.5.1_mono

# 默认开放方案使用相同的构建入口，完全不依赖私有媒体。
python tools/audio_profiles.py package --profile open --godot /path/to/Godot_4.5.1_mono
```

所有下载、处理副本、构建记录和 ZIP 均写入被 Git 忽略的 `.local/audio-profiles/`。下载器只访问清单中的固定公开 HTTPS 地址，校验重定向主机；访问拒绝、限流或内容改变时停止，不重试绕过。没有取得文件时不会报告下载成功。

也可用已有资源构建命令：先 `prepare`，然后 `python tools/build_assets.py --godot ... --audio-profile riot_en`；不提供参数时为 `open`。私有资源未准备好时会给出明确错误，不悄悄产出一份声称已启用原声的包。

## 安装与回退

ZIP 是**音频资源替换包**，包含 `mods/Volibear/Volibear.pck`；仍需安装匹配版本的 Volibear DLL/JSON 和 BaseLib。关闭游戏后替换这一份 PCK。`AUDIO_PACKAGE.json` 提供 ZIP 内各文件的 SHA-256；保留原 PCK 与这份清单，方便切回默认声音及按实际安装版本卸载。两个 profile 都构建完整 PCK，因此没有第二个 PCK 的加载先后问题。回到默认音频只需用 `open` 包替换同一文件。

运行时从 `res://VolibearArt/audio/profiles/runtime.json` 读取显式选择；私有媒体使用独立的 `profiles/riot_en/` 路径。没有配置、配置非法、cue 未覆盖、私有文件缺失／无法加载、真实时长不符或死亡声超过既有播放时限时，每个 cue 保留开放音频。覆盖只能改变已有一次性 cue 的音频文件、时长和衰减，不能更改 Voice/Sfx 总线、循环、默认开关、触发事件或游戏规则。

## 英文发声映射

| Mod cue | 来源文件标识 | 使用理由 |
|---|---|---|
| `voice.select` | `Volibear_Select.ogg` | 英文选角录音 |
| `voice.attack_01` / `voice.attack_02` | `Volibear_Original_BasicAttack_0/1.ogg` | 普通攻击发力声，两种变化 |
| `voice.heavy` | `Volibear_Original_BasicAttack_2.ogg` | 第三种发力声适配重击 |
| `voice.bite` | `Volibear_Original_W_4.ogg` | W / Frenzied Maul 发声类别 |
| `voice.cast` | `Volibear_Original_E_2.ogg` | E / Sky Splitter 发声类别 |
| `voice.roar` | `Volibear_Original_Q.ogg` | Q / Thundering Smash 挑战台词，适配迎战/咆哮 |
| `voice.death` | `Volibear_Original_Death_2.ogg` | 死亡类别，工作副本取 2.6 秒片段，适配既有 3 秒死亡播放租期 |
| `voice.victory` | `Volibear_Original_Kill_4.ogg` | 通用击杀回应适配本 Mod 战斗胜利；不称其为 LoL 原生 Victory 事件 |
| `voice.low_health` | **开放音频回退** | 已确认的 Original 英文集合未提供专用低血录音，不伪造一条 |
| `voice.hurt_01/02`、`voice.feral` | **开放音频回退** | 未取得对应专用录音；不以死亡声或无关英雄互动替代 |

这些是基于事件来源和现有动画入口的初始可用映射，不声称已经人工听审、完成口型同步或通过游戏内混音验收。工作副本做单声道 48 kHz 转换、首尾静音整理、峰值衰减及短淡入淡出；原始字节保持完整。私有 `build.json` 保存处理后实际 SHA256/时长，重新处理会重新生成记录。Ogg 容器序号由编码器随机生成，
因此重新处理不能保证逐字节一致；摘要属于本次产物，而非跨次固定值。复用已核验副本即可避免无谓重编码。

## Q / W / E / R 音效来源

当前 [Wiki 音频页](https://wiki.leagueoflegends.com/en-us/Volibear/Audio) 的公开索引列出了各技能 SFX 项，但本次未从这些项取得可靠的具体媒体文件链接。不能把 `Volibear_Original_W_4.ogg` 等 **VO** 文件写成 **SFX**。

Q 有额外的 Riot 官方来源：[2020-04-10 的研发文章](https://www.leagueoflegends.com/en-us/news/dev/dev-a-storm-is-brewing/)明确把以下两个嵌入音频对应到 Q 层次与撞击/施放演示：

- Q sound layers：`https://cmsassets.rgpub.io/sanity/files/dsfx7636/news_live/e999c86260813966c323c341870630a1c3466df2.mp3`
- Q impact/cast demonstration：`https://cmsassets.rgpub.io/sanity/files/dsfx7636/news_live/e93bcd6c205c3f497aad9cec5aff23be9d90b542.mp3`

分别用于可选方案的 `sfx.charge` 与 `sfx.heavy_impact`。它们是**官方研发样例**，不标称为目前客户端正式音效。W、E、R 的独立 SFX 精确下载位置继续明确标记 `unresolved_exact_media_url`，复用开放的咬击、雷击、格挡、咆哮及领域声。

后续 agent 可从 Wiki 音频页、`Category:Volibear_sound_effects` 或可靠的原始文件索引取得确切文件名后更新清单；必须保存真实 URL、事件类别、字节数、SHA256，并完成解码。[CommunityDragon 资产文档](https://www.communitydragon.org/docs/assets)明确说明完整局内音频不可用；客户端 pick/ban 是另列的例外，不能据此拼造局内音库 URL。

完整原声候选目录继续见 `../official/catalog.json`。其中历史的 153 条包括中文入口，不能不加筛选地称为英文包，也不能把历史下载报告当成当前 fresh clone 已含媒体的证据。Riot 权利说明参照[官方政策页](https://www.riotgames.com/en/legal)；这里不把“私有构建”描述为自动获得第三方再授权。
