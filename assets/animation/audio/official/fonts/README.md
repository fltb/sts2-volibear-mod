# 官方音频目录专用字体

`official_audio_ui.woff` 是本目录使用的本地字库子集，由项目已取得的 `NotoSansCJKsc-Regular.otf` 生成，遵循随附的 SIL Open Font License 1.1。衍生字体使用独立名称 **Volibear Official Audio UI**；原始版权与许可元数据保留在字体中。本目录没有修改动画包原有字体。

字形覆盖 `index.html` 的全部可打印字符、ASCII，以及当前 `catalog.json` 的文件名、ID、分类、语言和皮肤字段。浏览器直接从本目录加载 WOFF，不需要联网或另外安装中文字体。源文件与产物 SHA、覆盖范围、构建器版本及绑定输入见 `manifest.json`。

如改动页面中文或目录标签，使用记录的原字体重新生成子集：

```bash
python3 audio/official/fonts/build_subset.py --source-font /path/to/NotoSansCJKsc-Regular.otf --source-license /path/to/OFL.txt
```

生成器只读取原字体和许可文件，使用 `fonttools`，并保留生成所需的源 SHA 校验。原字体 SHA 必须为 `2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b`。
