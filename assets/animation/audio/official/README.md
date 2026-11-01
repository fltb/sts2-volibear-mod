# 沃利贝尔官方原始音频 · V5.1

这是按用户个人使用要求整理的官方录音来源目录。公开 Git 保存清单与历史检查记录，不包含 Riot 录音二进制；以下“已取得”描述原始私人采集批次，不代表 fresh clone 自带这些文件。实际下载后，打开 `index.html` 可离线搜索、按用途和语言筛选、逐条播放并下载原文件。

当前可运行的英文私有方案及 agent 可用的 `fetch / prepare / verify / package` 入口见 [../profiles/README.md](../profiles/README.md)。它复用本目录的英文文件标识/固定 SHA256，并补充 Riot 官方研发文章中的 Q 音效；默认安装仍使用完整开放音频。

## 已取得的内容

| 来源 | 数量 | 内容 |
|---|---:|---|
| League of Legends Wiki 独立媒体 CDN | 150 | 默认沃利贝尔英文语音：选择、禁用、移动、首次遭遇、攻击、技能、击杀、表情、回城、死亡和复活 |
| 同一 Wiki 媒体 CDN | 1 | 选择角色音效 `Volibear_Select_SFX.ogg` |
| 腾讯国服官方英雄资料中的音频地址 | 2 | 选择和禁用录音 |
| **合计** | **153** | **11,873,857 字节，约 16 分 39 秒** |

153 个文件具有 153 个不同的 SHA-256；原始 OGG 字节完整保留。目录显示每条录音的时长、采样率、声道、原文件名、来源和 SHA。

英文部分以当前默认 Original 文件为范围，未混入 Inkshadow、重做前的 `_old` 文件、LoR 或 Wild Rift。腾讯两条是当前官方英雄记录指向的国服入口；未将其 HTTP 更新时间当作录音制作年代。

## 完整性范围

`inventory.json` 中的 **153 项均已实际下载并完整解码**。分类索引的可见第一页与同事件皮肤命名提供了文件发现线索，最终以独立媒体 CDN 实际返回的 Ogg 文件确认存在；来源证据级别逐项保留。

当前独立 Wiki 主站和 Fandom 分类后续分页在本环境无法正常访问，因此没有宣称这些文件穷尽当前 Wiki 的全部录音。新站音频页另外显示多个战斗 SFX 播放项，但未取得其完整的真实文件名映射；本目录已下载的独立 SFX 是上述选择音效。具体证据与范围记录在 `sources/`。

## 与当前动画的关系

本目录是已交付、可试听的官方原文件库。V5 的运行音频仍由 `../manifest.json` 和 `../action_cues.json` 定义，已有 47 个声音、54 个 cue；组合视频与 PCK 继续使用这一版本。

`action_mapping_proposal.json` 保留原来的参考方案，`active=false`；新的可选运行映射独立位于 `../profiles/riot_en.json`，不把这份历史提案追写成已经激活。普通攻击参考 BasicAttack 发力声，技能发声按 Q/W/E/R 单独归类；其他英雄互动、移动长对白、回城和禁用语音不混进通用战斗 cue。没有合适的专用受伤或低血量录音时使用开放声音回退。

原始录音常有较长的自然尾音和静音，不能把文件总时长直接当成人物的开口时长。后续选声时需要按动作开口窗口和实际听感处理工作副本，再更新运行映射；本目录保留原文件。

## 文件与验证

- `files/`：153 个原始 OGG 文件。
- `catalog.json` / `catalog.js`：离线目录数据；后者支持直接以 `file://` 打开。
- `inventory.json`：本次下载范围与来源。
- `reports/download_report.json`：实际下载状态、大小及 SHA。
- `reports/technical_validation.json`：全部文件完整解码、实际 PCM、非静音和有限数值检查。
- `reports/browser_validation.json`：实际浏览器的查询、筛选、播放、切换、停止、原文件下载和手机布局检查。
- `reports/independent_review.json`：独立清单与来源一致性审查。

核验现有原文件和目录：

```bash
python3 audio/official/scripts/build_catalog.py --check
```

确实需要重新获取本目录列出的源文件时，运行：

```bash
python3 audio/official/scripts/download_official.py
python3 audio/official/scripts/build_catalog.py
```

下载器使用普通公开 GET，正确的已有文件按 SHA 复用；遇到访问拒绝或限流停止新增请求。它保护已有不同内容的文件。目录构建需要仓库已有的 NumPy，以及 `ffmpeg` / `ffprobe`。

音频来源和版权归属见 `CREDITS.md`。技术解码与播放检查没有被写成人工听音验收。
