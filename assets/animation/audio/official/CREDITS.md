# 官方原始音频来源

录音及角色音频版权归 **Riot Games, Inc.** 所有。本目录按用户要求用于个人资产收集，保持取得时的原始文件字节。

| 内容 | 来源 |
|---|---|
| 英文默认角色语音与选择音效 | [League of Legends Wiki — Volibear/Audio](https://wiki.leagueoflegends.com/en-us/Volibear/Audio)；实际文件来自其历史独立媒体 CDN `static.wikia.nocookie.net/leagueoflegends/images/` |
| 文件发现与历史分类 | [Volibear voice-overs](https://leagueoflegends.fandom.com/wiki/Category:Volibear_voice-overs)；逐项文件名线索及实际下载 URL 留在 `inventory.json` 与 `sources/` |
| 国服选择／禁用录音 | [腾讯官方英雄元数据](https://game.gtimg.cn/images/lol/act/img/js/heroList/hero_list.js)中的 Volibear、heroId 106，分别使用记录内的 `selectAudio` 与 `banAudio` |

每个文件的实际下载 URL、原文件名、原始大小、SHA-256、语言来源与编解码信息都在 `catalog.json`。默认英文和国服入口单独存放，未进行克隆、合成、变声或重新编码。

Wiki 页面文字的社区许可与 Riot 录音的版权归属分别记录；这里的官方录音未标为 CC0。原 V5 声音的 CC0 来源仍见上一级 `../CREDITS.md`。
