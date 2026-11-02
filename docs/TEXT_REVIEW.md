# 当前 Mod 全部游戏文本审核

> 初次导出快照；实施期间冻结。所有实施结束后由 Lead 统一执行一次最终再导出。

仅填写“修改”栏；空白表示尚未提出修改。稳定 ID 用于后续人工回填，工具不修改生产文本。
原文来自当前生产源码，不用设计卡表或旧资产预览替代。占位符、条件分支、富文本标记原样保留；表格中的 HTML 实体仅作 Markdown 转义。
基础/升级均独立列出：模板相同仍保留两行；数值、费用、关键词与 IfUpgraded 上下文见各卡。升级名称的原生“+”、原版类型/关键词翻译由游戏追加，不伪造为 Mod 原文。
状态以 C# 类名作稳定审核 ID（不是推测的原生 ModelId）；其它项优先用定位表/键。未归类中文字符串自动收入补充项，匹配用词单独列出。

## 覆盖与计数

- 卡牌：89；基础/升级牌面：178；牌面标题/描述字段：356。
- 审核字段合计：559；扫描生产源文件：183。
- 两件遗物含初始遗物兼容别名、升级遗物；另收角色专属海玻璃名称。剧情为当前实际新增的建筑师三句对话。
- 扫描 src/Volibear 下 C#、GDScript、场景、资源与 JSON；排除 bin/obj。原生游戏通用文案、日志/异常、注释、验收探针英文诊断、未打包设计/资产预览不作为游戏文本。
- 能量 UI 动态数值由原生 Label 提供；此处收入场景初始文本。音频媒体无 Mod 字幕，不将语音目录元数据充当屏幕文本。
- 文本表合并入口：[VolibearLoc.cs](<../src/Volibear/Content/VolibearLoc.cs>)、[InlineModelLocalization.cs](<../src/Volibear/Content/InlineModelLocalization.cs>)；资源打包入口：[build_assets.py](<../tools/build_assets.py>)。

| 分类 | 字段数 |
| --- | ---: |
| additional | 1 |
| ancients | 3 |
| card-faces | 356 |
| cards | 14 |
| characters | 14 |
| keyword-match | 26 |
| keywords | 42 |
| metadata | 4 |
| mod-menu | 4 |
| powers | 76 |
| relics | 10 |
| text-reference | 5 |
| ui | 4 |

## 卡牌：89 卡 / 178 牌面

### VOLIBEAR_B01

模型来源：[Basic.cs:12](<../src/Volibear/Content/Cards/Basic.cs#L12>)

#### 基础 · VOLIBEAR_B01.base

- 费用：1；类型：Attack；稀有度：Basic；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 6, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B01.base.description` | [VolibearLoc.cs:20](<../src/Volibear/Content/VolibearLoc.cs#L20>) | 造成{Damage}伤害。 |  |
| `cards:VOLIBEAR_B01.base.title` | [VolibearLoc.cs:19](<../src/Volibear/Content/VolibearLoc.cs#L19>) | 打击 |  |

#### 升级 · VOLIBEAR_B01.upgrade

- 费用：1；类型：Attack；稀有度：Basic；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 9, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B01.upgrade.description` | [VolibearLoc.cs:20](<../src/Volibear/Content/VolibearLoc.cs#L20>) | 造成{Damage}伤害。 |  |
| `cards:VOLIBEAR_B01.upgrade.title` | [VolibearLoc.cs:19](<../src/Volibear/Content/VolibearLoc.cs#L19>) | 打击 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(6m, Move)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_B02

模型来源：[Basic2.cs:13](<../src/Volibear/Content/Cards/Basic2.cs#L13>)

#### 基础 · VOLIBEAR_B02.base

- 费用：1；类型：Skill；稀有度：Basic；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 5, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B02.base.description` | [VolibearLoc.cs:22](<../src/Volibear/Content/VolibearLoc.cs#L22>) | 获得{Block}格挡。 |  |
| `cards:VOLIBEAR_B02.base.title` | [VolibearLoc.cs:21](<../src/Volibear/Content/VolibearLoc.cs#L21>) | 防御 |  |

#### 升级 · VOLIBEAR_B02.upgrade

- 费用：1；类型：Skill；稀有度：Basic；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 8, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B02.upgrade.description` | [VolibearLoc.cs:22](<../src/Volibear/Content/VolibearLoc.cs#L22>) | 获得{Block}格挡。 |  |
| `cards:VOLIBEAR_B02.upgrade.title` | [VolibearLoc.cs:21](<../src/Volibear/Content/VolibearLoc.cs#L21>) | 防御 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(5m, Move)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_B03

模型来源：[Basic2.cs:34](<../src/Volibear/Content/Cards/Basic2.cs#L34>)

#### 基础 · VOLIBEAR_B03.base

- 费用：1；类型：Attack；稀有度：Basic；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 8, "IfUpgraded": false, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B03.base.description` | [VolibearLoc.cs:24](<../src/Volibear/Content/VolibearLoc.cs#L24>) | 造成{Damage}伤害。对全体造成{Lightning}雷伤。 |  |
| `cards:VOLIBEAR_B03.base.title` | [VolibearLoc.cs:23](<../src/Volibear/Content/VolibearLoc.cs#L23>) | 霆爪 |  |

#### 升级 · VOLIBEAR_B03.upgrade

- 费用：1；类型：Attack；稀有度：Basic；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 11, "IfUpgraded": true, "Lightning": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B03.upgrade.description` | [VolibearLoc.cs:24](<../src/Volibear/Content/VolibearLoc.cs#L24>) | 造成{Damage}伤害。对全体造成{Lightning}雷伤。 |  |
| `cards:VOLIBEAR_B03.upgrade.title` | [VolibearLoc.cs:23](<../src/Volibear/Content/VolibearLoc.cs#L23>) | 霆爪 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(8m, Move), new DynamicVar("Lightning", 3m)]
UpgradeVar("Damage", 3m);
        UpgradeVar("Lightning", 2m);
```

</details>

### VOLIBEAR_B04

模型来源：[Basic2.cs:61](<../src/Volibear/Content/Cards/Basic2.cs#L61>)

#### 基础 · VOLIBEAR_B04.base

- 费用：1；类型：Attack；稀有度：Basic；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 8, "Damage": 6, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B04.base.description` | [VolibearLoc.cs:26](<../src/Volibear/Content/VolibearLoc.cs#L26>) | 获得{Block}格挡。造成{Damage}伤害。迎战。 |  |
| `cards:VOLIBEAR_B04.base.title` | [VolibearLoc.cs:25](<../src/Volibear/Content/VolibearLoc.cs#L25>) | 挺身迎战 |  |

#### 升级 · VOLIBEAR_B04.upgrade

- 费用：1；类型：Attack；稀有度：Basic；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 11, "Damage": 9, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_B04.upgrade.description` | [VolibearLoc.cs:26](<../src/Volibear/Content/VolibearLoc.cs#L26>) | 获得{Block}格挡。造成{Damage}伤害。迎战。 |  |
| `cards:VOLIBEAR_B04.upgrade.title` | [VolibearLoc.cs:25](<../src/Volibear/Content/VolibearLoc.cs#L25>) | 挺身迎战 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(6m, Move), new BlockVar(8m, Move)]
UpgradeVar("Damage", 3m);
        UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_C01

模型来源：[DirectEffects.cs:49](<../src/Volibear/Content/Cards/DirectEffects.cs#L49>)

#### 基础 · VOLIBEAR_C01.base

- 费用：0；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 6, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C01.base.description` | [DirectEffects.cs:52](<../src/Volibear/Content/Cards/DirectEffects.cs#L52>) | 造成{Damage:diff()}伤害。 |  |
| `cards:VOLIBEAR_C01.base.title` | [DirectEffects.cs:52](<../src/Volibear/Content/Cards/DirectEffects.cs#L52>) | 逼近 |  |

#### 升级 · VOLIBEAR_C01.upgrade

- 费用：0；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 9, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C01.upgrade.description` | [DirectEffects.cs:52](<../src/Volibear/Content/Cards/DirectEffects.cs#L52>) | 造成{Damage:diff()}伤害。 |  |
| `cards:VOLIBEAR_C01.upgrade.title` | [DirectEffects.cs:52](<../src/Volibear/Content/Cards/DirectEffects.cs#L52>) | 逼近 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(6m, Move)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_C02

模型来源：[DirectEffects.cs:59](<../src/Volibear/Content/Cards/DirectEffects.cs#L59>)

#### 基础 · VOLIBEAR_C02.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 5, "Hits": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C02.base.description` | [DirectEffects.cs:62](<../src/Volibear/Content/Cards/DirectEffects.cs#L62>) | 造成{Damage:diff()}伤害，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_C02.base.title` | [DirectEffects.cs:62](<../src/Volibear/Content/Cards/DirectEffects.cs#L62>) | 双爪 |  |

#### 升级 · VOLIBEAR_C02.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 7, "Hits": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C02.upgrade.description` | [DirectEffects.cs:62](<../src/Volibear/Content/Cards/DirectEffects.cs#L62>) | 造成{Damage:diff()}伤害，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_C02.upgrade.title` | [DirectEffects.cs:62](<../src/Volibear/Content/Cards/DirectEffects.cs#L62>) | 双爪 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(5m, Move), new DynamicVar("Hits", 2m)]
 UpgradeVar("Damage", 2m);
```

</details>

### VOLIBEAR_C03

模型来源：[DirectEffects.cs:69](<../src/Volibear/Content/Cards/DirectEffects.cs#L69>)

#### 基础 · VOLIBEAR_C03.base

- 费用：2；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 20, "IfUpgraded": false, "Lightning": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C03.base.description` | [DirectEffects.cs:72](<../src/Volibear/Content/Cards/DirectEffects.cs#L72>) | 造成{Damage:diff()}伤害。对全体造成{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_C03.base.title` | [DirectEffects.cs:72](<../src/Volibear/Content/Cards/DirectEffects.cs#L72>) | 轰雷重击 |  |

#### 升级 · VOLIBEAR_C03.upgrade

- 费用：2；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 26, "IfUpgraded": true, "Lightning": 7}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C03.upgrade.description` | [DirectEffects.cs:72](<../src/Volibear/Content/Cards/DirectEffects.cs#L72>) | 造成{Damage:diff()}伤害。对全体造成{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_C03.upgrade.title` | [DirectEffects.cs:72](<../src/Volibear/Content/Cards/DirectEffects.cs#L72>) | 轰雷重击 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(20m, Move), new DynamicVar("Lightning", 5m)]
UpgradeVar("Damage", 6m); UpgradeVar("Lightning", 2m);
```

</details>

### VOLIBEAR_C04

模型来源：[ControlledEffects.cs:141](<../src/Volibear/Content/Cards/ControlledEffects.cs#L141>)

#### 基础 · VOLIBEAR_C04.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 9, "IfUpgraded": false, "Weak": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C04.base.description` | [ControlledEffects.cs:144](<../src/Volibear/Content/Cards/ControlledEffects.cs#L144>) | 造成{Damage:diff()}伤害。施加{Weak:diff()}虚弱。迎战。 |  |
| `cards:VOLIBEAR_C04.base.title` | [ControlledEffects.cs:144](<../src/Volibear/Content/Cards/ControlledEffects.cs#L144>) | 擂首一击 |  |

#### 升级 · VOLIBEAR_C04.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 12, "IfUpgraded": true, "Weak": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C04.upgrade.description` | [ControlledEffects.cs:144](<../src/Volibear/Content/Cards/ControlledEffects.cs#L144>) | 造成{Damage:diff()}伤害。施加{Weak:diff()}虚弱。迎战。 |  |
| `cards:VOLIBEAR_C04.upgrade.title` | [ControlledEffects.cs:144](<../src/Volibear/Content/Cards/ControlledEffects.cs#L144>) | 擂首一击 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(9m, Move), new PowerVar<WeakPower>("Weak", 1m)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_C05

模型来源：[DirectEffects.cs:83](<../src/Volibear/Content/Cards/DirectEffects.cs#L83>)

#### 基础 · VOLIBEAR_C05.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 6, "Domain": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C05.base.description` | [DirectEffects.cs:86](<../src/Volibear/Content/Cards/DirectEffects.cs#L86>) | 领域{Domain:diff()}。造成{Damage:diff()}伤害。 |  |
| `cards:VOLIBEAR_C05.base.title` | [DirectEffects.cs:86](<../src/Volibear/Content/Cards/DirectEffects.cs#L86>) | 雷霆爪击 |  |

#### 升级 · VOLIBEAR_C05.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 9, "Domain": 1, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C05.upgrade.description` | [DirectEffects.cs:86](<../src/Volibear/Content/Cards/DirectEffects.cs#L86>) | 领域{Domain:diff()}。造成{Damage:diff()}伤害。 |  |
| `cards:VOLIBEAR_C05.upgrade.title` | [DirectEffects.cs:86](<../src/Volibear/Content/Cards/DirectEffects.cs#L86>) | 雷霆爪击 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(6m, Move), new DynamicVar("Domain", 1m)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_C06

模型来源：[ControlledEffects.cs:157](<../src/Volibear/Content/Cards/ControlledEffects.cs#L157>)

#### 基础 · VOLIBEAR_C06.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 6, "Cards": 1, "Damage": 8, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C06.base.description` | [ControlledEffects.cs:160](<../src/Volibear/Content/Cards/ControlledEffects.cs#L160>) | 造成{Damage:diff()}伤害。目标意图含攻击时，获得{Block:diff()}格挡；否则抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C06.base.title` | [ControlledEffects.cs:160](<../src/Volibear/Content/Cards/ControlledEffects.cs#L160>) | 进逼 |  |

#### 升级 · VOLIBEAR_C06.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 8, "Cards": 1, "Damage": 11, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C06.upgrade.description` | [ControlledEffects.cs:160](<../src/Volibear/Content/Cards/ControlledEffects.cs#L160>) | 造成{Damage:diff()}伤害。目标意图含攻击时，获得{Block:diff()}格挡；否则抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C06.upgrade.title` | [ControlledEffects.cs:160](<../src/Volibear/Content/Cards/ControlledEffects.cs#L160>) | 进逼 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(8m, Move), new BlockVar(6m, Move), new CardsVar(1)]
UpgradeVar("Damage", 3m); UpgradeVar("Block", 2m);
```

</details>

### VOLIBEAR_C07

模型来源：[ControlledEffects.cs:174](<../src/Volibear/Content/Cards/ControlledEffects.cs#L174>)

#### 基础 · VOLIBEAR_C07.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 8, "IfUpgraded": false, "Search": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C07.base.description` | [ControlledEffects.cs:177](<../src/Volibear/Content/Cards/ControlledEffects.cs#L177>) | 造成{Damage:diff()}伤害。检索{Search:diff()}张攻击。 |  |
| `cards:VOLIBEAR_C07.base.title` | [ControlledEffects.cs:177](<../src/Volibear/Content/Cards/ControlledEffects.cs#L177>) | 追嗅 |  |

#### 升级 · VOLIBEAR_C07.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 11, "IfUpgraded": true, "Search": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C07.upgrade.description` | [ControlledEffects.cs:177](<../src/Volibear/Content/Cards/ControlledEffects.cs#L177>) | 造成{Damage:diff()}伤害。检索{Search:diff()}张攻击。 |  |
| `cards:VOLIBEAR_C07.upgrade.title` | [ControlledEffects.cs:177](<../src/Volibear/Content/Cards/ControlledEffects.cs#L177>) | 追嗅 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(8m, Move), new DynamicVar("Search", 1m)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_C08

模型来源：[DirectEffects.cs:97](<../src/Volibear/Content/Cards/DirectEffects.cs#L97>)

#### 基础 · VOLIBEAR_C08.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 8, "IfUpgraded": false, "Vulnerable": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C08.base.description` | [DirectEffects.cs:100](<../src/Volibear/Content/Cards/DirectEffects.cs#L100>) | 造成{Damage:diff()}伤害。施加{Vulnerable:diff()}易伤。 |  |
| `cards:VOLIBEAR_C08.base.title` | [DirectEffects.cs:100](<../src/Volibear/Content/Cards/DirectEffects.cs#L100>) | 撕开伤口 |  |

#### 升级 · VOLIBEAR_C08.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 10, "IfUpgraded": true, "Vulnerable": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C08.upgrade.description` | [DirectEffects.cs:100](<../src/Volibear/Content/Cards/DirectEffects.cs#L100>) | 造成{Damage:diff()}伤害。施加{Vulnerable:diff()}易伤。 |  |
| `cards:VOLIBEAR_C08.upgrade.title` | [DirectEffects.cs:100](<../src/Volibear/Content/Cards/DirectEffects.cs#L100>) | 撕开伤口 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(8m, Move), new PowerVar<VulnerablePower>("Vulnerable", 1m)]
UpgradeVar("Damage", 2m); UpgradeVar("Vulnerable", 1m);
```

</details>

### VOLIBEAR_C09

模型来源：[DirectEffects.cs:112](<../src/Volibear/Content/Cards/DirectEffects.cs#L112>)

#### 基础 · VOLIBEAR_C09.base

- 费用：1；类型：Attack；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Damage": 6, "IfUpgraded": false, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C09.base.description` | [DirectEffects.cs:115](<../src/Volibear/Content/Cards/DirectEffects.cs#L115>) | 对全体造成{Damage:diff()}伤害和{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_C09.base.title` | [DirectEffects.cs:115](<../src/Volibear/Content/Cards/DirectEffects.cs#L115>) | 雷霆横扫 |  |

#### 升级 · VOLIBEAR_C09.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Damage": 8, "IfUpgraded": true, "Lightning": 4}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C09.upgrade.description` | [DirectEffects.cs:115](<../src/Volibear/Content/Cards/DirectEffects.cs#L115>) | 对全体造成{Damage:diff()}伤害和{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_C09.upgrade.title` | [DirectEffects.cs:115](<../src/Volibear/Content/Cards/DirectEffects.cs#L115>) | 雷霆横扫 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(6m, Move), new DynamicVar("Lightning", 3m)]
UpgradeVar("Damage", 2m); UpgradeVar("Lightning", 1m);
```

</details>

### VOLIBEAR_C10

模型来源：[DirectEffects.cs:126](<../src/Volibear/Content/Cards/DirectEffects.cs#L126>)

#### 基础 · VOLIBEAR_C10.base

- 费用：2；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 8, "Damage": 6, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C10.base.description` | [DirectEffects.cs:129](<../src/Volibear/Content/Cards/DirectEffects.cs#L129>) | 获得{Block:diff()}格挡。迎战。造成{Damage:diff()}＋吸收的伤害。 |  |
| `cards:VOLIBEAR_C10.base.title` | [DirectEffects.cs:129](<../src/Volibear/Content/Cards/DirectEffects.cs#L129>) | 以牙还牙 |  |

#### 升级 · VOLIBEAR_C10.upgrade

- 费用：2；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 11, "Damage": 9, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C10.upgrade.description` | [DirectEffects.cs:129](<../src/Volibear/Content/Cards/DirectEffects.cs#L129>) | 获得{Block:diff()}格挡。迎战。造成{Damage:diff()}＋吸收的伤害。 |  |
| `cards:VOLIBEAR_C10.upgrade.title` | [DirectEffects.cs:129](<../src/Volibear/Content/Cards/DirectEffects.cs#L129>) | 以牙还牙 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(8m, Move), new DamageVar(6m, Move)]
UpgradeVar("Block", 3m); UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_C11

模型来源：[DirectEffects.cs:142](<../src/Volibear/Content/Cards/DirectEffects.cs#L142>)

#### 基础 · VOLIBEAR_C11.base

- 费用：1；类型：Skill；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 8, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C11.base.description` | [DirectEffects.cs:145](<../src/Volibear/Content/Cards/DirectEffects.cs#L145>) | 获得{Block:diff()}格挡。迎战。 |  |
| `cards:VOLIBEAR_C11.base.title` | [DirectEffects.cs:145](<../src/Volibear/Content/Cards/DirectEffects.cs#L145>) | 正面迎敌 |  |

#### 升级 · VOLIBEAR_C11.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 11, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C11.upgrade.description` | [DirectEffects.cs:145](<../src/Volibear/Content/Cards/DirectEffects.cs#L145>) | 获得{Block:diff()}格挡。迎战。 |  |
| `cards:VOLIBEAR_C11.upgrade.title` | [DirectEffects.cs:145](<../src/Volibear/Content/Cards/DirectEffects.cs#L145>) | 正面迎敌 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(8m, Move)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_C12

模型来源：[DirectEffects.cs:156](<../src/Volibear/Content/Cards/DirectEffects.cs#L156>)

#### 基础 · VOLIBEAR_C12.base

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 10, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C12.base.description` | [DirectEffects.cs:159](<../src/Volibear/Content/Cards/DirectEffects.cs#L159>) | 获得{Block:diff()}＋力量的格挡。 |  |
| `cards:VOLIBEAR_C12.base.title` | [DirectEffects.cs:159](<../src/Volibear/Content/Cards/DirectEffects.cs#L159>) | 厚重皮毛 |  |

#### 升级 · VOLIBEAR_C12.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 13, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C12.upgrade.description` | [DirectEffects.cs:159](<../src/Volibear/Content/Cards/DirectEffects.cs#L159>) | 获得{Block:diff()}＋力量的格挡。 |  |
| `cards:VOLIBEAR_C12.upgrade.title` | [DirectEffects.cs:159](<../src/Volibear/Content/Cards/DirectEffects.cs#L159>) | 厚重皮毛 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(10m, Move)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_C13

模型来源：[ControlledEffects.cs:190](<../src/Volibear/Content/Cards/ControlledEffects.cs#L190>)

#### 基础 · VOLIBEAR_C13.base

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 3, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C13.base.description` | [ControlledEffects.cs:193](<../src/Volibear/Content/Cards/ControlledEffects.cs#L193>) | 消耗1张手牌，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C13.base.title` | [ControlledEffects.cs:193](<../src/Volibear/Content/Cards/ControlledEffects.cs#L193>) | 呼吸 |  |

#### 升级 · VOLIBEAR_C13.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 4, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C13.upgrade.description` | [ControlledEffects.cs:193](<../src/Volibear/Content/Cards/ControlledEffects.cs#L193>) | 消耗1张手牌，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C13.upgrade.title` | [ControlledEffects.cs:193](<../src/Volibear/Content/Cards/ControlledEffects.cs#L193>) | 呼吸 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(3)]
 UpgradeVar("Cards", 1m);
```

</details>

### VOLIBEAR_C14

模型来源：[PreparedEffects.cs:19](<../src/Volibear/Content/Cards/PreparedEffects.cs#L19>)

#### 基础 · VOLIBEAR_C14.base

- 费用：2；类型：Skill；稀有度：Common；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Block": 8, "Domain": 1, "IfUpgraded": false, "Retaliation": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C14.base.description` | [PreparedEffects.cs:22](<../src/Volibear/Content/Cards/PreparedEffects.cs#L22>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。反雷{Retaliation:diff()}。 |  |
| `cards:VOLIBEAR_C14.base.title` | [PreparedEffects.cs:22](<../src/Volibear/Content/Cards/PreparedEffects.cs#L22>) | 雷霆护身 |  |

#### 升级 · VOLIBEAR_C14.upgrade

- 费用：2；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 11, "Domain": 1, "IfUpgraded": true, "Retaliation": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C14.upgrade.description` | [PreparedEffects.cs:22](<../src/Volibear/Content/Cards/PreparedEffects.cs#L22>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。反雷{Retaliation:diff()}。 |  |
| `cards:VOLIBEAR_C14.upgrade.title` | [PreparedEffects.cs:22](<../src/Volibear/Content/Cards/PreparedEffects.cs#L22>) | 雷霆护身 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(8m, Move), new DynamicVar("Domain", 1m), new DynamicVar("Retaliation", 3m)]
UpgradeVar("Block", 3m); UpgradeVar("Retaliation", 2m);
        RemoveKeyword(CardKeyword.Exhaust);
```

</details>

### VOLIBEAR_C15

模型来源：[ControlledEffects.cs:204](<../src/Volibear/Content/Cards/ControlledEffects.cs#L204>)

#### 基础 · VOLIBEAR_C15.base

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C15.base.description` | [ControlledEffects.cs:207](<../src/Volibear/Content/Cards/ControlledEffects.cs#L207>) | 回收1张攻击或雷法，减费1。 |  |
| `cards:VOLIBEAR_C15.base.title` | [ControlledEffects.cs:207](<../src/Volibear/Content/Cards/ControlledEffects.cs#L207>) | 重整爪牙 |  |

#### 升级 · VOLIBEAR_C15.upgrade

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C15.upgrade.description` | [ControlledEffects.cs:207](<../src/Volibear/Content/Cards/ControlledEffects.cs#L207>) | 回收1张攻击或雷法，减费1。 |  |
| `cards:VOLIBEAR_C15.upgrade.title` | [ControlledEffects.cs:207](<../src/Volibear/Content/Cards/ControlledEffects.cs#L207>) | 重整爪牙 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
// 无额外 CanonicalVars
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_C17

模型来源：[ControlledEffects.cs:217](<../src/Volibear/Content/Cards/ControlledEffects.cs#L217>)

#### 基础 · VOLIBEAR_C17.base

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Strength": 4}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C17.base.description` | [ControlledEffects.cs:220](<../src/Volibear/Content/Cards/ControlledEffects.cs#L220>) | 本回合获得{Strength:diff()}力量。 |  |
| `cards:VOLIBEAR_C17.base.title` | [ControlledEffects.cs:220](<../src/Volibear/Content/Cards/ControlledEffects.cs#L220>) | 蓄力 |  |

#### 升级 · VOLIBEAR_C17.upgrade

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Strength": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C17.upgrade.description` | [ControlledEffects.cs:220](<../src/Volibear/Content/Cards/ControlledEffects.cs#L220>) | 本回合获得{Strength:diff()}力量。 |  |
| `cards:VOLIBEAR_C17.upgrade.title` | [ControlledEffects.cs:220](<../src/Volibear/Content/Cards/ControlledEffects.cs#L220>) | 蓄力 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new PowerVar<StrengthPower>("Strength", 4m)]
 UpgradeVar("Strength", 2m);
```

</details>

### VOLIBEAR_C18

模型来源：[DirectEffects.cs:167](<../src/Volibear/Content/Cards/DirectEffects.cs#L167>)

#### 基础 · VOLIBEAR_C18.base

- 费用：1；类型：Skill；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Domain": 1, "IfUpgraded": false, "Weak": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C18.base.description` | [DirectEffects.cs:170](<../src/Volibear/Content/Cards/DirectEffects.cs#L170>) | 领域{Domain:diff()}。对全体施加{Weak:diff()}虚弱。 |  |
| `cards:VOLIBEAR_C18.base.title` | [DirectEffects.cs:170](<../src/Volibear/Content/Cards/DirectEffects.cs#L170>) | 显圣 |  |

#### 升级 · VOLIBEAR_C18.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Domain": 1, "IfUpgraded": true, "Weak": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C18.upgrade.description` | [DirectEffects.cs:170](<../src/Volibear/Content/Cards/DirectEffects.cs#L170>) | 领域{Domain:diff()}。对全体施加{Weak:diff()}虚弱。 |  |
| `cards:VOLIBEAR_C18.upgrade.title` | [DirectEffects.cs:170](<../src/Volibear/Content/Cards/DirectEffects.cs#L170>) | 显圣 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Domain", 1m), new PowerVar<WeakPower>("Weak", 2m)]
 UpgradeVar("Weak", 1m);
```

</details>

### VOLIBEAR_C19

模型来源：[PreparedEffects.cs:40](<../src/Volibear/Content/Cards/PreparedEffects.cs#L40>)

#### 基础 · VOLIBEAR_C19.base

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Prepared": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C19.base.description` | [PreparedEffects.cs:43](<../src/Volibear/Content/Cards/PreparedEffects.cs#L43>) | 使1张手牌攻击获得保留与蓄势{Prepared:diff()}。 |  |
| `cards:VOLIBEAR_C19.base.title` | [PreparedEffects.cs:43](<../src/Volibear/Content/Cards/PreparedEffects.cs#L43>) | 追猎准备 |  |

#### 升级 · VOLIBEAR_C19.upgrade

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Prepared": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C19.upgrade.description` | [PreparedEffects.cs:43](<../src/Volibear/Content/Cards/PreparedEffects.cs#L43>) | 使1张手牌攻击获得保留与蓄势{Prepared:diff()}。 |  |
| `cards:VOLIBEAR_C19.upgrade.title` | [PreparedEffects.cs:43](<../src/Volibear/Content/Cards/PreparedEffects.cs#L43>) | 追猎准备 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Prepared", 3m)]
 UpgradeVar("Prepared", 2m);
```

</details>

### VOLIBEAR_C20

模型来源：[HistoryEffects.cs:30](<../src/Volibear/Content/Cards/HistoryEffects.cs#L30>)

#### 基础 · VOLIBEAR_C20.base

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Cards": 2, "Damage": 10, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C20.base.description` | [HistoryEffects.cs:33](<../src/Volibear/Content/Cards/HistoryEffects.cs#L33>) | 造成{Damage:diff()}伤害。本回合此前打出过攻击时，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C20.base.title` | [HistoryEffects.cs:33](<../src/Volibear/Content/Cards/HistoryEffects.cs#L33>) | 乘势追击 |  |

#### 升级 · VOLIBEAR_C20.upgrade

- 费用：1；类型：Attack；稀有度：Common；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Cards": 2, "Damage": 14, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C20.upgrade.description` | [HistoryEffects.cs:33](<../src/Volibear/Content/Cards/HistoryEffects.cs#L33>) | 造成{Damage:diff()}伤害。本回合此前打出过攻击时，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C20.upgrade.title` | [HistoryEffects.cs:33](<../src/Volibear/Content/Cards/HistoryEffects.cs#L33>) | 乘势追击 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(10m, Move), new CardsVar(2)]
 UpgradeVar("Damage", 4m);
```

</details>

### VOLIBEAR_C21

模型来源：[DirectEffects.cs:181](<../src/Volibear/Content/Cards/DirectEffects.cs#L181>)

#### 基础 · VOLIBEAR_C21.base

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 5, "Cards": 2, "Domain": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C21.base.description` | [DirectEffects.cs:184](<../src/Volibear/Content/Cards/DirectEffects.cs#L184>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C21.base.title` | [DirectEffects.cs:184](<../src/Volibear/Content/Cards/DirectEffects.cs#L184>) | 稳住阵脚 |  |

#### 升级 · VOLIBEAR_C21.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 8, "Cards": 2, "Domain": 1, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C21.upgrade.description` | [DirectEffects.cs:184](<../src/Volibear/Content/Cards/DirectEffects.cs#L184>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C21.upgrade.title` | [DirectEffects.cs:184](<../src/Volibear/Content/Cards/DirectEffects.cs#L184>) | 稳住阵脚 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(5m, Move), new DynamicVar("Domain", 1m), new CardsVar(2)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_C22

模型来源：[DirectEffects.cs:196](<../src/Volibear/Content/Cards/DirectEffects.cs#L196>)

#### 基础 · VOLIBEAR_C22.base

- 费用：2；类型：Attack；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Damage": 5, "Hits": 2, "IfUpgraded": false, "Lightning": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C22.base.description` | [DirectEffects.cs:199](<../src/Volibear/Content/Cards/DirectEffects.cs#L199>) | 对全体造成{Damage:diff()}伤害和{Lightning:diff()}雷伤，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_C22.base.title` | [DirectEffects.cs:199](<../src/Volibear/Content/Cards/DirectEffects.cs#L199>) | 雷震 |  |

#### 升级 · VOLIBEAR_C22.upgrade

- 费用：2；类型：Attack；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Damage": 7, "Hits": 2, "IfUpgraded": true, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C22.upgrade.description` | [DirectEffects.cs:199](<../src/Volibear/Content/Cards/DirectEffects.cs#L199>) | 对全体造成{Damage:diff()}伤害和{Lightning:diff()}雷伤，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_C22.upgrade.title` | [DirectEffects.cs:199](<../src/Volibear/Content/Cards/DirectEffects.cs#L199>) | 雷震 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(5m, Move), new DynamicVar("Lightning", 2m), new DynamicVar("Hits", 2m)]
UpgradeVar("Damage", 2m); UpgradeVar("Lightning", 1m);
```

</details>

### VOLIBEAR_C24

模型来源：[DirectEffects.cs:214](<../src/Volibear/Content/Cards/DirectEffects.cs#L214>)

#### 基础 · VOLIBEAR_C24.base

- 费用：1；类型：Skill；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": false, "Lightning": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C24.base.description` | [DirectEffects.cs:217](<../src/Volibear/Content/Cards/DirectEffects.cs#L217>) | 对全体造成{Lightning:diff()}雷伤。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C24.base.title` | [DirectEffects.cs:217](<../src/Volibear/Content/Cards/DirectEffects.cs#L217>) | 霹雳 |  |

#### 升级 · VOLIBEAR_C24.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": true, "Lightning": 9}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C24.upgrade.description` | [DirectEffects.cs:217](<../src/Volibear/Content/Cards/DirectEffects.cs#L217>) | 对全体造成{Lightning:diff()}雷伤。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_C24.upgrade.title` | [DirectEffects.cs:217](<../src/Volibear/Content/Cards/DirectEffects.cs#L217>) | 霹雳 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 6m), new CardsVar(1)]
 UpgradeVar("Lightning", 3m);
```

</details>

### VOLIBEAR_C25

模型来源：[PreparedEffects.cs:59](<../src/Volibear/Content/Cards/PreparedEffects.cs#L59>)

#### 基础 · VOLIBEAR_C25.base

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Charge": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C25.base.description` | [PreparedEffects.cs:62](<../src/Volibear/Content/Cards/PreparedEffects.cs#L62>) | 获得{Charge:diff()}雷势。本回合下一张攻击减费1。 |  |
| `cards:VOLIBEAR_C25.base.title` | [PreparedEffects.cs:62](<../src/Volibear/Content/Cards/PreparedEffects.cs#L62>) | 雷引 |  |

#### 升级 · VOLIBEAR_C25.upgrade

- 费用：1；类型：Skill；稀有度：Common；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Charge": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C25.upgrade.description` | [PreparedEffects.cs:62](<../src/Volibear/Content/Cards/PreparedEffects.cs#L62>) | 获得{Charge:diff()}雷势。本回合下一张攻击减费1。 |  |
| `cards:VOLIBEAR_C25.upgrade.title` | [PreparedEffects.cs:62](<../src/Volibear/Content/Cards/PreparedEffects.cs#L62>) | 雷引 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Charge", 1m)]
 UpgradeVar("Charge", 1m);
```

</details>

### VOLIBEAR_C26

模型来源：[DirectEffects.cs:228](<../src/Volibear/Content/Cards/DirectEffects.cs#L228>)

#### 基础 · VOLIBEAR_C26.base

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Energy": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C26.base.description` | [DirectEffects.cs:231](<../src/Volibear/Content/Cards/DirectEffects.cs#L231>) | 若本回合造成过雷伤，获得{Energy:diff()}能量。 |  |
| `cards:VOLIBEAR_C26.base.title` | [DirectEffects.cs:231](<../src/Volibear/Content/Cards/DirectEffects.cs#L231>) | 接地 |  |

#### 升级 · VOLIBEAR_C26.upgrade

- 费用：0；类型：Skill；稀有度：Common；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Energy": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C26.upgrade.description` | [DirectEffects.cs:231](<../src/Volibear/Content/Cards/DirectEffects.cs#L231>) | 若本回合造成过雷伤，获得{Energy:diff()}能量。 |  |
| `cards:VOLIBEAR_C26.upgrade.title` | [DirectEffects.cs:231](<../src/Volibear/Content/Cards/DirectEffects.cs#L231>) | 接地 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new EnergyVar(2)]
 UpgradeVar("Energy", 1m);
```

</details>

### VOLIBEAR_R01

模型来源：[DirectEffects.cs:416](<../src/Volibear/Content/Cards/DirectEffects.cs#L416>)

#### 基础 · VOLIBEAR_R01.base

- 费用：3；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 10, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R01.base.description` | [DirectEffects.cs:419](<../src/Volibear/Content/Cards/DirectEffects.cs#L419>) | 获得{Block:diff()}格挡。永久领域。 |  |
| `cards:VOLIBEAR_R01.base.title` | [DirectEffects.cs:419](<../src/Volibear/Content/Cards/DirectEffects.cs#L419>) | 风暴形态 |  |

#### 升级 · VOLIBEAR_R01.upgrade

- 费用：2；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 14, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R01.upgrade.description` | [DirectEffects.cs:419](<../src/Volibear/Content/Cards/DirectEffects.cs#L419>) | 获得{Block:diff()}格挡。永久领域。 |  |
| `cards:VOLIBEAR_R01.upgrade.title` | [DirectEffects.cs:419](<../src/Volibear/Content/Cards/DirectEffects.cs#L419>) | 风暴形态 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(10m, Move)]
EnergyCost.UpgradeBy(-1); UpgradeVar("Block", 4m);
```

</details>

### VOLIBEAR_R02

模型来源：[PersistentEffects.cs:146](<../src/Volibear/Content/Cards/PersistentEffects.cs#L146>)

#### 基础 · VOLIBEAR_R02.base

- 费用：2；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 10, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R02.base.description` | [PersistentEffects.cs:149](<../src/Volibear/Content/Cards/PersistentEffects.cs#L149>) | 获得{Block:diff()}格挡。坚甲。 |  |
| `cards:VOLIBEAR_R02.base.title` | [PersistentEffects.cs:149](<../src/Volibear/Content/Cards/PersistentEffects.cs#L149>) | 不动神躯 |  |

#### 升级 · VOLIBEAR_R02.upgrade

- 费用：2；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 15, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R02.upgrade.description` | [PersistentEffects.cs:149](<../src/Volibear/Content/Cards/PersistentEffects.cs#L149>) | 获得{Block:diff()}格挡。坚甲。 |  |
| `cards:VOLIBEAR_R02.upgrade.title` | [PersistentEffects.cs:149](<../src/Volibear/Content/Cards/PersistentEffects.cs#L149>) | 不动神躯 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(10m, Move)]
 UpgradeVar("Block", 5m);
```

</details>

### VOLIBEAR_R05

模型来源：[ControlledEffects.cs:304](<../src/Volibear/Content/Cards/ControlledEffects.cs#L304>)

#### 基础 · VOLIBEAR_R05.base

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Multiplier": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R05.base.description` | [ControlledEffects.cs:308](<../src/Volibear/Content/Cards/ControlledEffects.cs#L308>) | 格挡变为{Multiplier:diff()}倍。 |  |
| `cards:VOLIBEAR_R05.base.title` | [ControlledEffects.cs:308](<../src/Volibear/Content/Cards/ControlledEffects.cs#L308>) | 全身之力 |  |

#### 升级 · VOLIBEAR_R05.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Multiplier": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R05.upgrade.description` | [ControlledEffects.cs:308](<../src/Volibear/Content/Cards/ControlledEffects.cs#L308>) | 格挡变为{Multiplier:diff()}倍。 |  |
| `cards:VOLIBEAR_R05.upgrade.title` | [ControlledEffects.cs:308](<../src/Volibear/Content/Cards/ControlledEffects.cs#L308>) | 全身之力 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Multiplier", 3m)]
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_R06

模型来源：[PreparedEffects.cs:170](<../src/Volibear/Content/Cards/PreparedEffects.cs#L170>)

#### 基础 · VOLIBEAR_R06.base

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Block": 10, "IfUpgraded": false, "Strength": 3, "Training": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R06.base.description` | [PreparedEffects.cs:173](<../src/Volibear/Content/Cards/PreparedEffects.cs#L173>) | 获得{Strength:diff()}力量和{Block:diff()}格挡。本战攻击与雷法强化{Training:diff()}。 |  |
| `cards:VOLIBEAR_R06.base.title` | [PreparedEffects.cs:173](<../src/Volibear/Content/Cards/PreparedEffects.cs#L173>) | 天人合一 |  |

#### 升级 · VOLIBEAR_R06.upgrade

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Block": 14, "IfUpgraded": true, "Strength": 4, "Training": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R06.upgrade.description` | [PreparedEffects.cs:173](<../src/Volibear/Content/Cards/PreparedEffects.cs#L173>) | 获得{Strength:diff()}力量和{Block:diff()}格挡。本战攻击与雷法强化{Training:diff()}。 |  |
| `cards:VOLIBEAR_R06.upgrade.title` | [PreparedEffects.cs:173](<../src/Volibear/Content/Cards/PreparedEffects.cs#L173>) | 天人合一 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new PowerVar<StrengthPower>("Strength", 3m), new BlockVar(10m, Move), new DynamicVar("Training", 3m)]
UpgradeVar("Strength", 1m); UpgradeVar("Block", 4m);
```

</details>

### VOLIBEAR_R07

模型来源：[DirectEffects.cs:430](<../src/Volibear/Content/Cards/DirectEffects.cs#L430>)

#### 基础 · VOLIBEAR_R07.base

- 费用：2；类型：Skill；稀有度：Rare；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R07.base.description` | [DirectEffects.cs:433](<../src/Volibear/Content/Cards/DirectEffects.cs#L433>) | 对全体造成等同当前格挡的雷伤。 |  |
| `cards:VOLIBEAR_R07.base.title` | [DirectEffects.cs:433](<../src/Volibear/Content/Cards/DirectEffects.cs#L433>) | 天崩地裂 |  |

#### 升级 · VOLIBEAR_R07.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R07.upgrade.description` | [DirectEffects.cs:433](<../src/Volibear/Content/Cards/DirectEffects.cs#L433>) | 对全体造成等同当前格挡的雷伤。 |  |
| `cards:VOLIBEAR_R07.upgrade.title` | [DirectEffects.cs:433](<../src/Volibear/Content/Cards/DirectEffects.cs#L433>) | 天崩地裂 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
// 无额外 CanonicalVars
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_R08

模型来源：[ControlledEffects.cs:321](<../src/Volibear/Content/Cards/ControlledEffects.cs#L321>)

#### 基础 · VOLIBEAR_R08.base

- 费用：3；类型：Attack；稀有度：Rare；目标：RandomEnemy；原生关键词：无。
- 模板变量：`{"Damage": 10, "Hits": 4, "IfUpgraded": false, "Lightning": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R08.base.description` | [ControlledEffects.cs:324](<../src/Volibear/Content/Cards/ControlledEffects.cs#L324>) | 随机攻击{Hits:diff()}次，每次造成{Damage:diff()}伤害和{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_R08.base.title` | [ControlledEffects.cs:324](<../src/Volibear/Content/Cards/ControlledEffects.cs#L324>) | 雷霆万钧 |  |

#### 升级 · VOLIBEAR_R08.upgrade

- 费用：3；类型：Attack；稀有度：Rare；目标：RandomEnemy；原生关键词：无。
- 模板变量：`{"Damage": 13, "Hits": 4, "IfUpgraded": true, "Lightning": 8}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R08.upgrade.description` | [ControlledEffects.cs:324](<../src/Volibear/Content/Cards/ControlledEffects.cs#L324>) | 随机攻击{Hits:diff()}次，每次造成{Damage:diff()}伤害和{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_R08.upgrade.title` | [ControlledEffects.cs:324](<../src/Volibear/Content/Cards/ControlledEffects.cs#L324>) | 雷霆万钧 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Hits", 4m), new DamageVar(10m, Move), new DynamicVar("Lightning", 5m)]
UpgradeVar("Damage", 3m); UpgradeVar("Lightning", 3m);
```

</details>

### VOLIBEAR_R09

模型来源：[DirectEffects.cs:439](<../src/Volibear/Content/Cards/DirectEffects.cs#L439>)

#### 基础 · VOLIBEAR_R09.base

- 费用：2；类型：Skill；稀有度：Rare；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Block": 15, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R09.base.description` | [DirectEffects.cs:442](<../src/Volibear/Content/Cards/DirectEffects.cs#L442>) | 获得{Block:diff()}格挡。迎战全体。对全体造成等同吸收的雷伤。 |  |
| `cards:VOLIBEAR_R09.base.title` | [DirectEffects.cs:442](<../src/Volibear/Content/Cards/DirectEffects.cs#L442>) | 众敌皆来 |  |

#### 升级 · VOLIBEAR_R09.upgrade

- 费用：2；类型：Skill；稀有度：Rare；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Block": 21, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R09.upgrade.description` | [DirectEffects.cs:442](<../src/Volibear/Content/Cards/DirectEffects.cs#L442>) | 获得{Block:diff()}格挡。迎战全体。对全体造成等同吸收的雷伤。 |  |
| `cards:VOLIBEAR_R09.upgrade.title` | [DirectEffects.cs:442](<../src/Volibear/Content/Cards/DirectEffects.cs#L442>) | 众敌皆来 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(15m, Move)]
 UpgradeVar("Block", 6m);
```

</details>

### VOLIBEAR_R10

模型来源：[ControlledEffects.cs:343](<../src/Volibear/Content/Cards/ControlledEffects.cs#L343>)

#### 基础 · VOLIBEAR_R10.base

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Recover": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R10.base.description` | [ControlledEffects.cs:346](<../src/Volibear/Content/Cards/ControlledEffects.cs#L346>) | 回收至多{Recover:diff()}张攻击，减费1。 |  |
| `cards:VOLIBEAR_R10.base.title` | [ControlledEffects.cs:346](<../src/Volibear/Content/Cards/ControlledEffects.cs#L346>) | 这场战斗尚未结束 |  |

#### 升级 · VOLIBEAR_R10.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Recover": 4}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R10.upgrade.description` | [ControlledEffects.cs:346](<../src/Volibear/Content/Cards/ControlledEffects.cs#L346>) | 回收至多{Recover:diff()}张攻击，减费1。 |  |
| `cards:VOLIBEAR_R10.upgrade.title` | [ControlledEffects.cs:346](<../src/Volibear/Content/Cards/ControlledEffects.cs#L346>) | 这场战斗尚未结束 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Recover", 3m)]
 UpgradeVar("Recover", 1m);
```

</details>

### VOLIBEAR_R12

模型来源：[DirectEffects.cs:456](<../src/Volibear/Content/Cards/DirectEffects.cs#L456>)

#### 基础 · VOLIBEAR_R12.base

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"HandSize": 7, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R12.base.description` | [DirectEffects.cs:459](<../src/Volibear/Content/Cards/DirectEffects.cs#L459>) | 抽牌至手牌达到{HandSize:diff()}张。 |  |
| `cards:VOLIBEAR_R12.base.title` | [DirectEffects.cs:459](<../src/Volibear/Content/Cards/DirectEffects.cs#L459>) | 解放本能 |  |

#### 升级 · VOLIBEAR_R12.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"HandSize": 9, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R12.upgrade.description` | [DirectEffects.cs:459](<../src/Volibear/Content/Cards/DirectEffects.cs#L459>) | 抽牌至手牌达到{HandSize:diff()}张。 |  |
| `cards:VOLIBEAR_R12.upgrade.title` | [DirectEffects.cs:459](<../src/Volibear/Content/Cards/DirectEffects.cs#L459>) | 解放本能 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("HandSize", 7m)]
 UpgradeVar("HandSize", 2m);
```

</details>

### VOLIBEAR_R13

模型来源：[DirectEffects.cs:472](<../src/Volibear/Content/Cards/DirectEffects.cs#L472>)

#### 基础 · VOLIBEAR_R13.base

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Domain": 1, "Heal": 4, "IfUpgraded": false, "Strength": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R13.base.description` | [DirectEffects.cs:475](<../src/Volibear/Content/Cards/DirectEffects.cs#L475>) | 领域内恢复{Heal:diff()}生命；领域外获得领域{Domain:diff()}。获得{Strength:diff()}力量。 |  |
| `cards:VOLIBEAR_R13.base.title` | [DirectEffects.cs:475](<../src/Volibear/Content/Cards/DirectEffects.cs#L475>) | 重返蛮荒 |  |

#### 升级 · VOLIBEAR_R13.upgrade

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Domain": 1, "Heal": 6, "IfUpgraded": true, "Strength": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R13.upgrade.description` | [DirectEffects.cs:475](<../src/Volibear/Content/Cards/DirectEffects.cs#L475>) | 领域内恢复{Heal:diff()}生命；领域外获得领域{Domain:diff()}。获得{Strength:diff()}力量。 |  |
| `cards:VOLIBEAR_R13.upgrade.title` | [DirectEffects.cs:475](<../src/Volibear/Content/Cards/DirectEffects.cs#L475>) | 重返蛮荒 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Heal", 4m), new DynamicVar("Domain", 1m), new PowerVar<StrengthPower>("Strength", 2m)]
UpgradeVar("Heal", 2m); UpgradeVar("Strength", 1m);
```

</details>

### VOLIBEAR_R14

模型来源：[HistoryEffects.cs:98](<../src/Volibear/Content/Cards/HistoryEffects.cs#L98>)

#### 基础 · VOLIBEAR_R14.base

- 费用：1；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 0, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R14.base.description` | [HistoryEffects.cs:101](<../src/Volibear/Content/Cards/HistoryEffects.cs#L101>) | {Cards:cond:&gt;0?抽{Cards:diff()}张牌。&#124;}每打出1张攻击后，本回合对同一目标的攻击费用−1。 |  |
| `cards:VOLIBEAR_R14.base.title` | [HistoryEffects.cs:101](<../src/Volibear/Content/Cards/HistoryEffects.cs#L101>) | 不休之猎 |  |

#### 升级 · VOLIBEAR_R14.upgrade

- 费用：1；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R14.upgrade.description` | [HistoryEffects.cs:101](<../src/Volibear/Content/Cards/HistoryEffects.cs#L101>) | {Cards:cond:&gt;0?抽{Cards:diff()}张牌。&#124;}每打出1张攻击后，本回合对同一目标的攻击费用−1。 |  |
| `cards:VOLIBEAR_R14.upgrade.title` | [HistoryEffects.cs:101](<../src/Volibear/Content/Cards/HistoryEffects.cs#L101>) | 不休之猎 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(0)]
 UpgradeVar("Cards", 1m);
```

</details>

### VOLIBEAR_R16

模型来源：[PersistentEffects.cs:161](<../src/Volibear/Content/Cards/PersistentEffects.cs#L161>)

#### 基础 · VOLIBEAR_R16.base

- 费用：1；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 0, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R16.base.description` | [PersistentEffects.cs:164](<../src/Volibear/Content/Cards/PersistentEffects.cs#L164>) | {IfUpgraded:show:获得{Block:diff()}格挡。}每打出1张攻击后，获得1力量；该牌提供格挡时，再获得1敏捷。 |  |
| `cards:VOLIBEAR_R16.base.title` | [PersistentEffects.cs:164](<../src/Volibear/Content/Cards/PersistentEffects.cs#L164>) | 愈战神躯 |  |

#### 升级 · VOLIBEAR_R16.upgrade

- 费用：1；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 8, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R16.upgrade.description` | [PersistentEffects.cs:164](<../src/Volibear/Content/Cards/PersistentEffects.cs#L164>) | {IfUpgraded:show:获得{Block:diff()}格挡。}每打出1张攻击后，获得1力量；该牌提供格挡时，再获得1敏捷。 |  |
| `cards:VOLIBEAR_R16.upgrade.title` | [PersistentEffects.cs:164](<../src/Volibear/Content/Cards/PersistentEffects.cs#L164>) | 愈战神躯 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(0m, Move)]
 UpgradeVar("Block", 8m);
```

</details>

### VOLIBEAR_R17

模型来源：[ControlledEffects.cs:356](<../src/Volibear/Content/Cards/ControlledEffects.cs#L356>)

#### 基础 · VOLIBEAR_R17.base

- 费用：X；类型：Skill；稀有度：Rare；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Bonus": 0, "IfUpgraded": false, "Lightning": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R17.base.description` | [ControlledEffects.cs:360](<../src/Volibear/Content/Cards/ControlledEffects.cs#L360>) | 获得X{IfUpgraded:show:＋1}雷势。造成{Lightning:diff()}雷伤，重复X{IfUpgraded:show:＋1}次。 |  |
| `cards:VOLIBEAR_R17.base.title` | [ControlledEffects.cs:360](<../src/Volibear/Content/Cards/ControlledEffects.cs#L360>) | 天雷决 |  |

#### 升级 · VOLIBEAR_R17.upgrade

- 费用：X；类型：Skill；稀有度：Rare；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Bonus": 1, "IfUpgraded": true, "Lightning": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R17.upgrade.description` | [ControlledEffects.cs:360](<../src/Volibear/Content/Cards/ControlledEffects.cs#L360>) | 获得X{IfUpgraded:show:＋1}雷势。造成{Lightning:diff()}雷伤，重复X{IfUpgraded:show:＋1}次。 |  |
| `cards:VOLIBEAR_R17.upgrade.title` | [ControlledEffects.cs:360](<../src/Volibear/Content/Cards/ControlledEffects.cs#L360>) | 天雷决 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 6m), new DynamicVar("Bonus", 0m)]
 UpgradeVar("Bonus", 1m);
```

</details>

### VOLIBEAR_R18

模型来源：[PersistentEffects.cs:175](<../src/Volibear/Content/Cards/PersistentEffects.cs#L175>)

#### 基础 · VOLIBEAR_R18.base

- 费用：2；类型：Power；稀有度：Rare；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Lightning": 6, "Pool": 4}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R18.base.description` | [PersistentEffects.cs:183](<../src/Volibear/Content/Cards/PersistentEffects.cs#L183>) | 对全体造成{Lightning:diff()}雷伤。回合结束及每回合首次迎战后，对全体造成{Pool:diff()}雷伤。 |  |
| `cards:VOLIBEAR_R18.base.title` | [PersistentEffects.cs:183](<../src/Volibear/Content/Cards/PersistentEffects.cs#L183>) | 雷池 |  |

#### 升级 · VOLIBEAR_R18.upgrade

- 费用：2；类型：Power；稀有度：Rare；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Lightning": 9, "Pool": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R18.upgrade.description` | [PersistentEffects.cs:183](<../src/Volibear/Content/Cards/PersistentEffects.cs#L183>) | 对全体造成{Lightning:diff()}雷伤。回合结束及每回合首次迎战后，对全体造成{Pool:diff()}雷伤。 |  |
| `cards:VOLIBEAR_R18.upgrade.title` | [PersistentEffects.cs:183](<../src/Volibear/Content/Cards/PersistentEffects.cs#L183>) | 雷池 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 6m), new DynamicVar("Pool", 4m)]
UpgradeVar("Lightning", 3m); UpgradeVar("Pool", 2m);
```

</details>

### VOLIBEAR_R21

模型来源：[DirectEffects.cs:490](<../src/Volibear/Content/Cards/DirectEffects.cs#L490>)

#### 基础 · VOLIBEAR_R21.base

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"BlockPerStrike": 4, "Cards": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R21.base.description` | [DirectEffects.cs:494](<../src/Volibear/Content/Cards/DirectEffects.cs#L494>) | 获得本回合雷伤次数×{BlockPerStrike:diff()}的格挡。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_R21.base.title` | [DirectEffects.cs:494](<../src/Volibear/Content/Cards/DirectEffects.cs#L494>) | 雷霆化身 |  |

#### 升级 · VOLIBEAR_R21.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"BlockPerStrike": 5, "Cards": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R21.upgrade.description` | [DirectEffects.cs:494](<../src/Volibear/Content/Cards/DirectEffects.cs#L494>) | 获得本回合雷伤次数×{BlockPerStrike:diff()}的格挡。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_R21.upgrade.title` | [DirectEffects.cs:494](<../src/Volibear/Content/Cards/DirectEffects.cs#L494>) | 雷霆化身 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("BlockPerStrike", 4m), new CardsVar(2)]
 UpgradeVar("BlockPerStrike", 1m);
```

</details>

### VOLIBEAR_R23

模型来源：[DirectEffects.cs:506](<../src/Volibear/Content/Cards/DirectEffects.cs#L506>)

#### 基础 · VOLIBEAR_R23.base

- 费用：2；类型：Skill；稀有度：Rare；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Hits": 3, "IfUpgraded": false, "Lightning": 8}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R23.base.description` | [DirectEffects.cs:509](<../src/Volibear/Content/Cards/DirectEffects.cs#L509>) | 造成{Lightning:diff()}雷伤，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_R23.base.title` | [DirectEffects.cs:509](<../src/Volibear/Content/Cards/DirectEffects.cs#L509>) | 裂天 |  |

#### 升级 · VOLIBEAR_R23.upgrade

- 费用：2；类型：Skill；稀有度：Rare；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Hits": 3, "IfUpgraded": true, "Lightning": 11}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R23.upgrade.description` | [DirectEffects.cs:509](<../src/Volibear/Content/Cards/DirectEffects.cs#L509>) | 造成{Lightning:diff()}雷伤，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_R23.upgrade.title` | [DirectEffects.cs:509](<../src/Volibear/Content/Cards/DirectEffects.cs#L509>) | 裂天 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 8m), new DynamicVar("Hits", 3m)]
 UpgradeVar("Lightning", 3m);
```

</details>

### VOLIBEAR_R24

模型来源：[DirectEffects.cs:521](<../src/Volibear/Content/Cards/DirectEffects.cs#L521>)

#### 基础 · VOLIBEAR_R24.base

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Cards": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R24.base.description` | [DirectEffects.cs:524](<../src/Volibear/Content/Cards/DirectEffects.cs#L524>) | 获得等同本回合雷伤次数的能量。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_R24.base.title` | [DirectEffects.cs:524](<../src/Volibear/Content/Cards/DirectEffects.cs#L524>) | 雷涌 |  |

#### 升级 · VOLIBEAR_R24.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Cards": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R24.upgrade.description` | [DirectEffects.cs:524](<../src/Volibear/Content/Cards/DirectEffects.cs#L524>) | 获得等同本回合雷伤次数的能量。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_R24.upgrade.title` | [DirectEffects.cs:524](<../src/Volibear/Content/Cards/DirectEffects.cs#L524>) | 雷涌 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(2)]
 UpgradeVar("Cards", 1m);
```

</details>

### VOLIBEAR_R25

模型来源：[ControlledEffects.cs:377](<../src/Volibear/Content/Cards/ControlledEffects.cs#L377>)

#### 基础 · VOLIBEAR_R25.base

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Domain": 2, "IfUpgraded": false, "Search": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R25.base.description` | [ControlledEffects.cs:380](<../src/Volibear/Content/Cards/ControlledEffects.cs#L380>) | 领域{Domain:diff()}。检索至多{Search:diff()}张技能。 |  |
| `cards:VOLIBEAR_R25.base.title` | [ControlledEffects.cs:380](<../src/Volibear/Content/Cards/ControlledEffects.cs#L380>) | 风暴重临 |  |

#### 升级 · VOLIBEAR_R25.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Domain": 2, "IfUpgraded": true, "Search": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R25.upgrade.description` | [ControlledEffects.cs:380](<../src/Volibear/Content/Cards/ControlledEffects.cs#L380>) | 领域{Domain:diff()}。检索至多{Search:diff()}张技能。 |  |
| `cards:VOLIBEAR_R25.upgrade.title` | [ControlledEffects.cs:380](<../src/Volibear/Content/Cards/ControlledEffects.cs#L380>) | 风暴重临 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Domain", 2m), new DynamicVar("Search", 2m)]
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_R27

模型来源：[BeastEffects.cs:126](<../src/Volibear/Content/Cards/BeastEffects.cs#L126>)

#### 基础 · VOLIBEAR_R27.base

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Convert": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R27.base.description` | [BeastEffects.cs:130](<../src/Volibear/Content/Cards/BeastEffects.cs#L130>) | 兽化至多{Convert:diff()}张手牌。每张爪形本回合下次打出时设为0费；每张躯形使你获得4格挡。 |  |
| `cards:VOLIBEAR_R27.base.title` | [BeastEffects.cs:130](<../src/Volibear/Content/Cards/BeastEffects.cs#L130>) | 旧日重临 |  |

#### 升级 · VOLIBEAR_R27.upgrade

- 费用：1；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Convert": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R27.upgrade.description` | [BeastEffects.cs:130](<../src/Volibear/Content/Cards/BeastEffects.cs#L130>) | 兽化至多{Convert:diff()}张手牌。每张爪形本回合下次打出时设为0费；每张躯形使你获得4格挡。 |  |
| `cards:VOLIBEAR_R27.upgrade.title` | [BeastEffects.cs:130](<../src/Volibear/Content/Cards/BeastEffects.cs#L130>) | 旧日重临 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Convert", 2m)]
 UpgradeVar("Convert", 1m);
```

</details>

### VOLIBEAR_R28

模型来源：[BeastEffects.cs:140](<../src/Volibear/Content/Cards/BeastEffects.cs#L140>)

#### 基础 · VOLIBEAR_R28.base

- 费用：1；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R28.base.description` | [BeastEffects.cs:143](<../src/Volibear/Content/Cards/BeastEffects.cs#L143>) | 打出及每回合开始，可选兽化1张手牌。每回合首次兽化后，抽{Cards:diff()}张牌。每回合首次打出兽形时，获得1雷势。 |  |
| `cards:VOLIBEAR_R28.base.title` | [BeastEffects.cs:143](<../src/Volibear/Content/Cards/BeastEffects.cs#L143>) | 熊灵侵染 |  |

#### 升级 · VOLIBEAR_R28.upgrade

- 费用：1；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R28.upgrade.description` | [BeastEffects.cs:143](<../src/Volibear/Content/Cards/BeastEffects.cs#L143>) | 打出及每回合开始，可选兽化1张手牌。每回合首次兽化后，抽{Cards:diff()}张牌。每回合首次打出兽形时，获得1雷势。 |  |
| `cards:VOLIBEAR_R28.upgrade.title` | [BeastEffects.cs:143](<../src/Volibear/Content/Cards/BeastEffects.cs#L143>) | 熊灵侵染 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(1)]
 UpgradeVar("Cards", 1m);
```

</details>

### VOLIBEAR_R29

模型来源：[BeastEffects.cs:158](<../src/Volibear/Content/Cards/BeastEffects.cs#L158>)

#### 基础 · VOLIBEAR_R29.base

- 费用：3；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R29.base.description` | [BeastEffects.cs:161](<../src/Volibear/Content/Cards/BeastEffects.cs#L161>) | 兽化所有手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_R29.base.title` | [BeastEffects.cs:161](<../src/Volibear/Content/Cards/BeastEffects.cs#L161>) | 不再为人 |  |

#### 升级 · VOLIBEAR_R29.upgrade

- 费用：2；类型：Skill；稀有度：Rare；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R29.upgrade.description` | [BeastEffects.cs:161](<../src/Volibear/Content/Cards/BeastEffects.cs#L161>) | 兽化所有手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_R29.upgrade.title` | [BeastEffects.cs:161](<../src/Volibear/Content/Cards/BeastEffects.cs#L161>) | 不再为人 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
// 无额外 CanonicalVars
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_R30

模型来源：[BeastEffects.cs:169](<../src/Volibear/Content/Cards/BeastEffects.cs#L169>)

#### 基础 · VOLIBEAR_R30.base

- 费用：2；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 6, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R30.base.description` | [BeastEffects.cs:172](<../src/Volibear/Content/Cards/BeastEffects.cs#L172>) | 兽化1张手牌，其本回合下次打出时设为0费。每回合首次打出爪形时，获得{Block:diff()}格挡；每次打出躯形时，获得1能量。 |  |
| `cards:VOLIBEAR_R30.base.title` | [BeastEffects.cs:172](<../src/Volibear/Content/Cards/BeastEffects.cs#L172>) | 我即荒野 |  |

#### 升级 · VOLIBEAR_R30.upgrade

- 费用：2；类型：Power；稀有度：Rare；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 9, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R30.upgrade.description` | [BeastEffects.cs:172](<../src/Volibear/Content/Cards/BeastEffects.cs#L172>) | 兽化1张手牌，其本回合下次打出时设为0费。每回合首次打出爪形时，获得{Block:diff()}格挡；每次打出躯形时，获得1能量。 |  |
| `cards:VOLIBEAR_R30.upgrade.title` | [BeastEffects.cs:172](<../src/Volibear/Content/Cards/BeastEffects.cs#L172>) | 我即荒野 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(6m, Move)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_R31

模型来源：[ControlledEffects.cs:394](<../src/Volibear/Content/Cards/ControlledEffects.cs#L394>)

#### 基础 · VOLIBEAR_R31.base

- 费用：2；类型：Attack；稀有度：Rare；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Block": 8, "Damage": 20, "Domain": 1, "IfUpgraded": false, "Lightning": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R31.base.description` | [ControlledEffects.cs:397](<../src/Volibear/Content/Cards/ControlledEffects.cs#L397>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。移除目标格挡。造成{Damage:diff()}伤害，对所有敌人造成{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_R31.base.title` | [ControlledEffects.cs:397](<../src/Volibear/Content/Cards/ControlledEffects.cs#L397>) | 天声震落 |  |

#### 升级 · VOLIBEAR_R31.upgrade

- 费用：2；类型：Attack；稀有度：Rare；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Block": 12, "Damage": 28, "Domain": 2, "IfUpgraded": true, "Lightning": 9}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_R31.upgrade.description` | [ControlledEffects.cs:397](<../src/Volibear/Content/Cards/ControlledEffects.cs#L397>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。移除目标格挡。造成{Damage:diff()}伤害，对所有敌人造成{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_R31.upgrade.title` | [ControlledEffects.cs:397](<../src/Volibear/Content/Cards/ControlledEffects.cs#L397>) | 天声震落 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(8m, Move), new DynamicVar("Domain", 1m), new DamageVar(20m, Move), new DynamicVar("Lightning", 6m)]
UpgradeVar("Block", 4m); UpgradeVar("Domain", 1m);
        UpgradeVar("Damage", 8m); UpgradeVar("Lightning", 3m);
```

</details>

### VOLIBEAR_T01

模型来源：[BeastTokens.cs:17](<../src/Volibear/Content/Cards/BeastTokens.cs#L17>)

#### 基础 · VOLIBEAR_T01.base

- 费用：1；类型：Attack；稀有度：Token；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Damage": 7, "Hits": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_T01.base.description` | [BeastTokens.cs:20](<../src/Volibear/Content/Cards/BeastTokens.cs#L20>) | 造成{Damage:diff()}伤害{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_T01.base.title` | [BeastTokens.cs:20](<../src/Volibear/Content/Cards/BeastTokens.cs#L20>) | 裂骨之爪 |  |

#### 升级 · VOLIBEAR_T01.upgrade

- 费用：1；类型：Attack；稀有度：Token；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Damage": 11, "Hits": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_T01.upgrade.description` | [BeastTokens.cs:20](<../src/Volibear/Content/Cards/BeastTokens.cs#L20>) | 造成{Damage:diff()}伤害{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_T01.upgrade.title` | [BeastTokens.cs:20](<../src/Volibear/Content/Cards/BeastTokens.cs#L20>) | 裂骨之爪 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(7m, Move), new DynamicVar("Hits", 2m)]
 UpgradeVar("Damage", 4m);
```

</details>

### VOLIBEAR_T02

模型来源：[BeastTokens.cs:31](<../src/Volibear/Content/Cards/BeastTokens.cs#L31>)

#### 基础 · VOLIBEAR_T02.base

- 费用：1；类型：Skill；稀有度：Token；目标：AllEnemies；原生关键词：Exhaust。
- 模板变量：`{"Block": 9, "IfUpgraded": false, "Lightning": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_T02.base.description` | [BeastTokens.cs:34](<../src/Volibear/Content/Cards/BeastTokens.cs#L34>) | 获得{Block:diff()}格挡。对全体造成{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_T02.base.title` | [BeastTokens.cs:34](<../src/Volibear/Content/Cards/BeastTokens.cs#L34>) | 风暴之躯 |  |

#### 升级 · VOLIBEAR_T02.upgrade

- 费用：1；类型：Skill；稀有度：Token；目标：AllEnemies；原生关键词：Exhaust。
- 模板变量：`{"Block": 12, "IfUpgraded": true, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_T02.upgrade.description` | [BeastTokens.cs:34](<../src/Volibear/Content/Cards/BeastTokens.cs#L34>) | 获得{Block:diff()}格挡。对全体造成{Lightning:diff()}雷伤。 |  |
| `cards:VOLIBEAR_T02.upgrade.title` | [BeastTokens.cs:34](<../src/Volibear/Content/Cards/BeastTokens.cs#L34>) | 风暴之躯 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(9m, Move), new DynamicVar("Lightning", 2m)]
UpgradeVar("Block", 3m); UpgradeVar("Lightning", 1m);
```

</details>

### VOLIBEAR_U02

模型来源：[PersistentEffects.cs:22](<../src/Volibear/Content/Cards/PersistentEffects.cs#L22>)

#### 基础 · VOLIBEAR_U02.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Conduction": 3, "IfUpgraded": false, "Lightning": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U02.base.description` | [PersistentEffects.cs:25](<../src/Volibear/Content/Cards/PersistentEffects.cs#L25>) | 对全体造成{Lightning:diff()}雷伤。每段普通攻击结算后，对全体造成{Conduction:diff()}雷伤。 |  |
| `cards:VOLIBEAR_U02.base.title` | [PersistentEffects.cs:25](<../src/Volibear/Content/Cards/PersistentEffects.cs#L25>) | 狂雷渐起 |  |

#### 升级 · VOLIBEAR_U02.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Conduction": 4, "IfUpgraded": true, "Lightning": 9}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U02.upgrade.description` | [PersistentEffects.cs:25](<../src/Volibear/Content/Cards/PersistentEffects.cs#L25>) | 对全体造成{Lightning:diff()}雷伤。每段普通攻击结算后，对全体造成{Conduction:diff()}雷伤。 |  |
| `cards:VOLIBEAR_U02.upgrade.title` | [PersistentEffects.cs:25](<../src/Volibear/Content/Cards/PersistentEffects.cs#L25>) | 狂雷渐起 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 6m), new DynamicVar("Conduction", 3m)]
UpgradeVar("Lightning", 3m); UpgradeVar("Conduction", 1m);
```

</details>

### VOLIBEAR_U03

模型来源：[PersistentEffects.cs:36](<../src/Volibear/Content/Cards/PersistentEffects.cs#L36>)

#### 基础 · VOLIBEAR_U03.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 8, "Decay": 6, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U03.base.description` | [PersistentEffects.cs:39](<../src/Volibear/Content/Cards/PersistentEffects.cs#L39>) | 获得{Block:diff()}格挡。留甲{Decay:diff()}。 |  |
| `cards:VOLIBEAR_U03.base.title` | [PersistentEffects.cs:39](<../src/Volibear/Content/Cards/PersistentEffects.cs#L39>) | 屹立 |  |

#### 升级 · VOLIBEAR_U03.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 12, "Decay": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U03.upgrade.description` | [PersistentEffects.cs:39](<../src/Volibear/Content/Cards/PersistentEffects.cs#L39>) | 获得{Block:diff()}格挡。留甲{Decay:diff()}。 |  |
| `cards:VOLIBEAR_U03.upgrade.title` | [PersistentEffects.cs:39](<../src/Volibear/Content/Cards/PersistentEffects.cs#L39>) | 屹立 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(8m, Move), new DynamicVar("Decay", 6m)]
UpgradeVar("Block", 4m); UpgradeVar("Decay", -3m);
```

</details>

### VOLIBEAR_U04

模型来源：[PersistentEffects.cs:50](<../src/Volibear/Content/Cards/PersistentEffects.cs#L50>)

#### 基础 · VOLIBEAR_U04.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 6, "IfUpgraded": false, "Strength": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U04.base.description` | [PersistentEffects.cs:53](<../src/Volibear/Content/Cards/PersistentEffects.cs#L53>) | 获得{Block:diff()}格挡。每回合首次迎战后，获得{Strength:diff()}力量和1雷势。 |  |
| `cards:VOLIBEAR_U04.base.title` | [PersistentEffects.cs:53](<../src/Volibear/Content/Cards/PersistentEffects.cs#L53>) | 战痕 |  |

#### 升级 · VOLIBEAR_U04.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 9, "IfUpgraded": true, "Strength": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U04.upgrade.description` | [PersistentEffects.cs:53](<../src/Volibear/Content/Cards/PersistentEffects.cs#L53>) | 获得{Block:diff()}格挡。每回合首次迎战后，获得{Strength:diff()}力量和1雷势。 |  |
| `cards:VOLIBEAR_U04.upgrade.title` | [PersistentEffects.cs:53](<../src/Volibear/Content/Cards/PersistentEffects.cs#L53>) | 战痕 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(6m, Move), new DynamicVar("Strength", 1m)]
UpgradeVar("Block", 3m); UpgradeVar("Strength", 1m);
```

</details>

### VOLIBEAR_U05

模型来源：[DirectEffects.cs:240](<../src/Volibear/Content/Cards/DirectEffects.cs#L240>)

#### 基础 · VOLIBEAR_U05.base

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"CalculationBase": 0, "ExtraDamage": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U05.base.description` | [DirectEffects.cs:243](<../src/Volibear/Content/Cards/DirectEffects.cs#L243>) | 造成等同当前格挡的伤害。 |  |
| `cards:VOLIBEAR_U05.base.title` | [DirectEffects.cs:243](<../src/Volibear/Content/Cards/DirectEffects.cs#L243>) | 挟山 |  |

#### 升级 · VOLIBEAR_U05.upgrade

- 费用：0；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"CalculationBase": 0, "ExtraDamage": 1, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U05.upgrade.description` | [DirectEffects.cs:243](<../src/Volibear/Content/Cards/DirectEffects.cs#L243>) | 造成等同当前格挡的伤害。 |  |
| `cards:VOLIBEAR_U05.upgrade.title` | [DirectEffects.cs:243](<../src/Volibear/Content/Cards/DirectEffects.cs#L243>) | 挟山 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CalculationBaseVar(0m), new ExtraDamageVar(1m),
         new CalculatedDamageVar(Move).WithMultiplier((card, _) => card.Owner.Creature.Block)]
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_U06

模型来源：[DirectEffects.cs:256](<../src/Volibear/Content/Cards/DirectEffects.cs#L256>)

#### 基础 · VOLIBEAR_U06.base

- 费用：2；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 8, "Hits": 3, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U06.base.description` | [DirectEffects.cs:259](<../src/Volibear/Content/Cards/DirectEffects.cs#L259>) | 造成{Damage:diff()}伤害，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_U06.base.title` | [DirectEffects.cs:259](<../src/Volibear/Content/Cards/DirectEffects.cs#L259>) | 三重撕裂 |  |

#### 升级 · VOLIBEAR_U06.upgrade

- 费用：2；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 11, "Hits": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U06.upgrade.description` | [DirectEffects.cs:259](<../src/Volibear/Content/Cards/DirectEffects.cs#L259>) | 造成{Damage:diff()}伤害，重复{Hits:diff()}次。 |  |
| `cards:VOLIBEAR_U06.upgrade.title` | [DirectEffects.cs:259](<../src/Volibear/Content/Cards/DirectEffects.cs#L259>) | 三重撕裂 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(8m, Move), new DynamicVar("Hits", 3m)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_U07

模型来源：[HistoryEffects.cs:45](<../src/Volibear/Content/Cards/HistoryEffects.cs#L45>)

#### 基础 · VOLIBEAR_U07.base

- 费用：3；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 28, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U07.base.description` | [HistoryEffects.cs:48](<../src/Volibear/Content/Cards/HistoryEffects.cs#L48>) | 造成{Damage:diff()}伤害。本回合每对该目标打出过1张攻击牌，本牌费用−1。 |  |
| `cards:VOLIBEAR_U07.base.title` | [HistoryEffects.cs:48](<../src/Volibear/Content/Cards/HistoryEffects.cs#L48>) | 崩山 |  |

#### 升级 · VOLIBEAR_U07.upgrade

- 费用：3；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 36, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U07.upgrade.description` | [HistoryEffects.cs:48](<../src/Volibear/Content/Cards/HistoryEffects.cs#L48>) | 造成{Damage:diff()}伤害。本回合每对该目标打出过1张攻击牌，本牌费用−1。 |  |
| `cards:VOLIBEAR_U07.upgrade.title` | [HistoryEffects.cs:48](<../src/Volibear/Content/Cards/HistoryEffects.cs#L48>) | 崩山 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(28m, Move)]
 UpgradeVar("Damage", 8m);
```

</details>

### VOLIBEAR_U08

模型来源：[PreparedEffects.cs:74](<../src/Volibear/Content/Cards/PreparedEffects.cs#L74>)

#### 基础 · VOLIBEAR_U08.base

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Bite": 6, "Block": 6, "Damage": 10, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U08.base.description` | [PreparedEffects.cs:77](<../src/Volibear/Content/Cards/PreparedEffects.cs#L77>) | 获得{Block:diff()}格挡。造成{Damage:diff()}伤害，对咬痕目标追加{Bite:diff()}伤害。施加咬痕。 |  |
| `cards:VOLIBEAR_U08.base.title` | [PreparedEffects.cs:77](<../src/Volibear/Content/Cards/PreparedEffects.cs#L77>) | 暴怒撕咬 |  |

#### 升级 · VOLIBEAR_U08.upgrade

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Bite": 9, "Block": 9, "Damage": 14, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U08.upgrade.description` | [PreparedEffects.cs:77](<../src/Volibear/Content/Cards/PreparedEffects.cs#L77>) | 获得{Block:diff()}格挡。造成{Damage:diff()}伤害，对咬痕目标追加{Bite:diff()}伤害。施加咬痕。 |  |
| `cards:VOLIBEAR_U08.upgrade.title` | [PreparedEffects.cs:77](<../src/Volibear/Content/Cards/PreparedEffects.cs#L77>) | 暴怒撕咬 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(6m, Move), new DamageVar(10m, Move), new DynamicVar("Bite", 6m)]
UpgradeVar("Block", 3m); UpgradeVar("Damage", 4m); UpgradeVar("Bite", 3m);
```

</details>

### VOLIBEAR_U10

模型来源：[PreparedEffects.cs:96](<../src/Volibear/Content/Cards/PreparedEffects.cs#L96>)

#### 基础 · VOLIBEAR_U10.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": false, "Training": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U10.base.description` | [PreparedEffects.cs:99](<../src/Volibear/Content/Cards/PreparedEffects.cs#L99>) | 抽{Cards:diff()}张牌。下一张攻击强化{Training:diff()}。 |  |
| `cards:VOLIBEAR_U10.base.title` | [PreparedEffects.cs:99](<../src/Volibear/Content/Cards/PreparedEffects.cs#L99>) | 磨砺爪牙 |  |

#### 升级 · VOLIBEAR_U10.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 2, "IfUpgraded": true, "Training": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U10.upgrade.description` | [PreparedEffects.cs:99](<../src/Volibear/Content/Cards/PreparedEffects.cs#L99>) | 抽{Cards:diff()}张牌。下一张攻击强化{Training:diff()}。 |  |
| `cards:VOLIBEAR_U10.upgrade.title` | [PreparedEffects.cs:99](<../src/Volibear/Content/Cards/PreparedEffects.cs#L99>) | 磨砺爪牙 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(1), new DynamicVar("Training", 3m)]
UpgradeVar("Cards", 1m); UpgradeVar("Training", 2m);
```

</details>

### VOLIBEAR_U11

模型来源：[PreparedEffects.cs:110](<../src/Volibear/Content/Cards/PreparedEffects.cs#L110>)

#### 基础 · VOLIBEAR_U11.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U11.base.description` | [PreparedEffects.cs:113](<../src/Volibear/Content/Cards/PreparedEffects.cs#L113>) | 本回合下一张攻击获得重演。 |  |
| `cards:VOLIBEAR_U11.base.title` | [PreparedEffects.cs:113](<../src/Volibear/Content/Cards/PreparedEffects.cs#L113>) | 暴风再临 |  |

#### 升级 · VOLIBEAR_U11.upgrade

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U11.upgrade.description` | [PreparedEffects.cs:113](<../src/Volibear/Content/Cards/PreparedEffects.cs#L113>) | 本回合下一张攻击获得重演。 |  |
| `cards:VOLIBEAR_U11.upgrade.title` | [PreparedEffects.cs:113](<../src/Volibear/Content/Cards/PreparedEffects.cs#L113>) | 暴风再临 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
// 无额外 CanonicalVars
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_U12

模型来源：[PreparedEffects.cs:122](<../src/Volibear/Content/Cards/PreparedEffects.cs#L122>)

#### 基础 · VOLIBEAR_U12.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Cards": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U12.base.description` | [PreparedEffects.cs:125](<../src/Volibear/Content/Cards/PreparedEffects.cs#L125>) | 本轮雷伤增加当前力量。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U12.base.title` | [PreparedEffects.cs:125](<../src/Volibear/Content/Cards/PreparedEffects.cs#L125>) | 原始力量 |  |

#### 升级 · VOLIBEAR_U12.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Cards": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U12.upgrade.description` | [PreparedEffects.cs:125](<../src/Volibear/Content/Cards/PreparedEffects.cs#L125>) | 本轮雷伤增加当前力量。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U12.upgrade.title` | [PreparedEffects.cs:125](<../src/Volibear/Content/Cards/PreparedEffects.cs#L125>) | 原始力量 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(1)]
 UpgradeVar("Cards", 1m);
```

</details>

### VOLIBEAR_U13

模型来源：[ControlledEffects.cs:232](<../src/Volibear/Content/Cards/ControlledEffects.cs#L232>)

#### 基础 · VOLIBEAR_U13.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Strength": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U13.base.description` | [ControlledEffects.cs:235](<../src/Volibear/Content/Cards/ControlledEffects.cs#L235>) | 获得{Strength:diff()}力量。将临时力量转为力量。 |  |
| `cards:VOLIBEAR_U13.base.title` | [ControlledEffects.cs:235](<../src/Volibear/Content/Cards/ControlledEffects.cs#L235>) | 力量归身 |  |

#### 升级 · VOLIBEAR_U13.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Strength": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U13.upgrade.description` | [ControlledEffects.cs:235](<../src/Volibear/Content/Cards/ControlledEffects.cs#L235>) | 获得{Strength:diff()}力量。将临时力量转为力量。 |  |
| `cards:VOLIBEAR_U13.upgrade.title` | [ControlledEffects.cs:235](<../src/Volibear/Content/Cards/ControlledEffects.cs#L235>) | 力量归身 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new PowerVar<StrengthPower>("Strength", 2m)]
 UpgradeVar("Strength", 1m);
```

</details>

### VOLIBEAR_U14

模型来源：[PreparedEffects.cs:139](<../src/Volibear/Content/Cards/PreparedEffects.cs#L139>)

#### 基础 · VOLIBEAR_U14.base

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Block": 5, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U14.base.description` | [PreparedEffects.cs:142](<../src/Volibear/Content/Cards/PreparedEffects.cs#L142>) | 获得{Block:diff()}格挡。本回合下一张迎战牌减费1。 |  |
| `cards:VOLIBEAR_U14.base.title` | [PreparedEffects.cs:142](<../src/Volibear/Content/Cards/PreparedEffects.cs#L142>) | 迎战准备 |  |

#### 升级 · VOLIBEAR_U14.upgrade

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 8, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U14.upgrade.description` | [PreparedEffects.cs:142](<../src/Volibear/Content/Cards/PreparedEffects.cs#L142>) | 获得{Block:diff()}格挡。本回合下一张迎战牌减费1。 |  |
| `cards:VOLIBEAR_U14.upgrade.title` | [PreparedEffects.cs:142](<../src/Volibear/Content/Cards/PreparedEffects.cs#L142>) | 迎战准备 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(5m, Move)]
UpgradeVar("Block", 3m); RemoveKeyword(CardKeyword.Exhaust);
```

</details>

### VOLIBEAR_U15

模型来源：[ControlledEffects.cs:255](<../src/Volibear/Content/Cards/ControlledEffects.cs#L255>)

#### 基础 · VOLIBEAR_U15.base

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U15.base.description` | [ControlledEffects.cs:258](<../src/Volibear/Content/Cards/ControlledEffects.cs#L258>) | 消耗1张手牌，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U15.base.title` | [ControlledEffects.cs:258](<../src/Volibear/Content/Cards/ControlledEffects.cs#L258>) | 暴风换气 |  |

#### 升级 · VOLIBEAR_U15.upgrade

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U15.upgrade.description` | [ControlledEffects.cs:258](<../src/Volibear/Content/Cards/ControlledEffects.cs#L258>) | 消耗1张手牌，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U15.upgrade.title` | [ControlledEffects.cs:258](<../src/Volibear/Content/Cards/ControlledEffects.cs#L258>) | 暴风换气 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new CardsVar(2)]
 UpgradeVar("Cards", 1m);
```

</details>

### VOLIBEAR_U17

模型来源：[ControlledEffects.cs:269](<../src/Volibear/Content/Cards/ControlledEffects.cs#L269>)

#### 基础 · VOLIBEAR_U17.base

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": false, "Scry": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U17.base.description` | [ControlledEffects.cs:272](<../src/Volibear/Content/Cards/ControlledEffects.cs#L272>) | 预见{Scry:diff()}。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U17.base.title` | [ControlledEffects.cs:272](<../src/Volibear/Content/Cards/ControlledEffects.cs#L272>) | 古老直觉 |  |

#### 升级 · VOLIBEAR_U17.upgrade

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Cards": 1, "IfUpgraded": true, "Scry": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U17.upgrade.description` | [ControlledEffects.cs:272](<../src/Volibear/Content/Cards/ControlledEffects.cs#L272>) | 预见{Scry:diff()}。抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U17.upgrade.title` | [ControlledEffects.cs:272](<../src/Volibear/Content/Cards/ControlledEffects.cs#L272>) | 古老直觉 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Scry", 3m), new CardsVar(1)]
 UpgradeVar("Scry", 2m);
```

</details>

### VOLIBEAR_U19

模型来源：[PersistentEffects.cs:64](<../src/Volibear/Content/Cards/PersistentEffects.cs#L64>)

#### 基础 · VOLIBEAR_U19.base

- 费用：2；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Draw": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U19.base.description` | [PersistentEffects.cs:67](<../src/Volibear/Content/Cards/PersistentEffects.cs#L67>) | 抽{Draw:diff()}张牌。领域1。每次迎战后，抽1张牌并获得领域1。 |  |
| `cards:VOLIBEAR_U19.base.title` | [PersistentEffects.cs:67](<../src/Volibear/Content/Cards/PersistentEffects.cs#L67>) | 风暴不散 |  |

#### 升级 · VOLIBEAR_U19.upgrade

- 费用：2；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Draw": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U19.upgrade.description` | [PersistentEffects.cs:67](<../src/Volibear/Content/Cards/PersistentEffects.cs#L67>) | 抽{Draw:diff()}张牌。领域1。每次迎战后，抽1张牌并获得领域1。 |  |
| `cards:VOLIBEAR_U19.upgrade.title` | [PersistentEffects.cs:67](<../src/Volibear/Content/Cards/PersistentEffects.cs#L67>) | 风暴不散 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Draw", 1m)]
 UpgradeVar("Draw", 1m);
```

</details>

### VOLIBEAR_U20

模型来源：[HistoryEffects.cs:63](<../src/Volibear/Content/Cards/HistoryEffects.cs#L63>)

#### 基础 · VOLIBEAR_U20.base

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Damage": 10, "Energy": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U20.base.description` | [HistoryEffects.cs:66](<../src/Volibear/Content/Cards/HistoryEffects.cs#L66>) | 造成{Damage:diff()}伤害。若上一张打出的是攻击牌，获得{Energy:diff()}能量。 |  |
| `cards:VOLIBEAR_U20.base.title` | [HistoryEffects.cs:66](<../src/Volibear/Content/Cards/HistoryEffects.cs#L66>) | 势不可挡 |  |

#### 升级 · VOLIBEAR_U20.upgrade

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Damage": 14, "Energy": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U20.upgrade.description` | [HistoryEffects.cs:66](<../src/Volibear/Content/Cards/HistoryEffects.cs#L66>) | 造成{Damage:diff()}伤害。若上一张打出的是攻击牌，获得{Energy:diff()}能量。 |  |
| `cards:VOLIBEAR_U20.upgrade.title` | [HistoryEffects.cs:66](<../src/Volibear/Content/Cards/HistoryEffects.cs#L66>) | 势不可挡 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(10m, Move), new DynamicVar("Energy", 2m)]
UpgradeVar("Damage", 4m); UpgradeVar("Energy", 1m);
```

</details>

### VOLIBEAR_U21

模型来源：[PersistentEffects.cs:79](<../src/Volibear/Content/Cards/PersistentEffects.cs#L79>)

#### 基础 · VOLIBEAR_U21.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U21.base.description` | [PersistentEffects.cs:82](<../src/Volibear/Content/Cards/PersistentEffects.cs#L82>) | 本回合每累计2次雷伤，获得1能量。部署时本回合已有至少2次雷伤，立即获得1能量。 |  |
| `cards:VOLIBEAR_U21.base.title` | [PersistentEffects.cs:82](<../src/Volibear/Content/Cards/PersistentEffects.cs#L82>) | 雷霆余威 |  |

#### 升级 · VOLIBEAR_U21.upgrade

- 费用：0；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U21.upgrade.description` | [PersistentEffects.cs:82](<../src/Volibear/Content/Cards/PersistentEffects.cs#L82>) | 本回合每累计2次雷伤，获得1能量。部署时本回合已有至少2次雷伤，立即获得1能量。 |  |
| `cards:VOLIBEAR_U21.upgrade.title` | [PersistentEffects.cs:82](<../src/Volibear/Content/Cards/PersistentEffects.cs#L82>) | 雷霆余威 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
// 无额外 CanonicalVars
 EnergyCost.UpgradeBy(-1);
```

</details>

### VOLIBEAR_U23

模型来源：[DirectEffects.cs:266](<../src/Volibear/Content/Cards/DirectEffects.cs#L266>)

#### 基础 · VOLIBEAR_U23.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Block": 9, "IfUpgraded": false, "Weak": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U23.base.description` | [DirectEffects.cs:269](<../src/Volibear/Content/Cards/DirectEffects.cs#L269>) | 对全体施加{Weak:diff()}虚弱。获得{Block:diff()}格挡。 |  |
| `cards:VOLIBEAR_U23.base.title` | [DirectEffects.cs:269](<../src/Volibear/Content/Cards/DirectEffects.cs#L269>) | 迎风咆哮 |  |

#### 升级 · VOLIBEAR_U23.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Block": 12, "IfUpgraded": true, "Weak": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U23.upgrade.description` | [DirectEffects.cs:269](<../src/Volibear/Content/Cards/DirectEffects.cs#L269>) | 对全体施加{Weak:diff()}虚弱。获得{Block:diff()}格挡。 |  |
| `cards:VOLIBEAR_U23.upgrade.title` | [DirectEffects.cs:269](<../src/Volibear/Content/Cards/DirectEffects.cs#L269>) | 迎风咆哮 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new PowerVar<WeakPower>("Weak", 1m), new BlockVar(9m, Move)]
UpgradeVar("Weak", 1m); UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_U24

模型来源：[DirectEffects.cs:280](<../src/Volibear/Content/Cards/DirectEffects.cs#L280>)

#### 基础 · VOLIBEAR_U24.base

- 费用：2；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Damage": 21, "IfUpgraded": false, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U24.base.description` | [DirectEffects.cs:283](<../src/Volibear/Content/Cards/DirectEffects.cs#L283>) | 造成{Damage:diff()}伤害，再造成{Lightning:diff()}雷伤，恢复造成雷伤的生命。 |  |
| `cards:VOLIBEAR_U24.base.title` | [DirectEffects.cs:283](<../src/Volibear/Content/Cards/DirectEffects.cs#L283>) | 饮血而战 |  |

#### 升级 · VOLIBEAR_U24.upgrade

- 费用：2；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：Exhaust。
- 模板变量：`{"Damage": 28, "IfUpgraded": true, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U24.upgrade.description` | [DirectEffects.cs:283](<../src/Volibear/Content/Cards/DirectEffects.cs#L283>) | 造成{Damage:diff()}伤害，再造成{Lightning:diff()}雷伤，恢复造成雷伤的生命。 |  |
| `cards:VOLIBEAR_U24.upgrade.title` | [DirectEffects.cs:283](<../src/Volibear/Content/Cards/DirectEffects.cs#L283>) | 饮血而战 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(21m, Move), new DynamicVar("Lightning", 3m)]
 UpgradeVar("Damage", 7m);
```

</details>

### VOLIBEAR_U25

模型来源：[PersistentEffects.cs:88](<../src/Volibear/Content/Cards/PersistentEffects.cs#L88>)

#### 基础 · VOLIBEAR_U25.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Draw": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U25.base.description` | [PersistentEffects.cs:91](<../src/Volibear/Content/Cards/PersistentEffects.cs#L91>) | 抽1张牌。每回合首次对同一目标打出第2张单体攻击后，抽{Draw:diff()}张牌，其中的攻击减费1。 |  |
| `cards:VOLIBEAR_U25.base.title` | [PersistentEffects.cs:91](<../src/Volibear/Content/Cards/PersistentEffects.cs#L91>) | 猎物未倒 |  |

#### 升级 · VOLIBEAR_U25.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Draw": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U25.upgrade.description` | [PersistentEffects.cs:91](<../src/Volibear/Content/Cards/PersistentEffects.cs#L91>) | 抽1张牌。每回合首次对同一目标打出第2张单体攻击后，抽{Draw:diff()}张牌，其中的攻击减费1。 |  |
| `cards:VOLIBEAR_U25.upgrade.title` | [PersistentEffects.cs:91](<../src/Volibear/Content/Cards/PersistentEffects.cs#L91>) | 猎物未倒 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Draw", 1m)]
 UpgradeVar("Draw", 1m);
```

</details>

### VOLIBEAR_U26

模型来源：[PersistentEffects.cs:102](<../src/Volibear/Content/Cards/PersistentEffects.cs#L102>)

#### 基础 · VOLIBEAR_U26.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": false, "Storm": 1, "Strength": 1}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U26.base.description` | [PersistentEffects.cs:105](<../src/Volibear/Content/Cards/PersistentEffects.cs#L105>) | 获得1力量。每回合打出第2张攻击时，获得{Strength:diff()}力量和{Storm:diff()}雷势。 |  |
| `cards:VOLIBEAR_U26.base.title` | [PersistentEffects.cs:105](<../src/Volibear/Content/Cards/PersistentEffects.cs#L105>) | 愈战愈烈 |  |

#### 升级 · VOLIBEAR_U26.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"IfUpgraded": true, "Storm": 2, "Strength": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U26.upgrade.description` | [PersistentEffects.cs:105](<../src/Volibear/Content/Cards/PersistentEffects.cs#L105>) | 获得1力量。每回合打出第2张攻击时，获得{Strength:diff()}力量和{Storm:diff()}雷势。 |  |
| `cards:VOLIBEAR_U26.upgrade.title` | [PersistentEffects.cs:105](<../src/Volibear/Content/Cards/PersistentEffects.cs#L105>) | 愈战愈烈 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Strength", 1m), new DynamicVar("Storm", 1m)]
UpgradeVar("Strength", 1m); UpgradeVar("Storm", 1m);
```

</details>

### VOLIBEAR_U27

模型来源：[DirectEffects.cs:315](<../src/Volibear/Content/Cards/DirectEffects.cs#L315>)

#### 基础 · VOLIBEAR_U27.base

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"BlockPerStrike": 2, "Damage": 8, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U27.base.description` | [DirectEffects.cs:319](<../src/Volibear/Content/Cards/DirectEffects.cs#L319>) | 造成{Damage:diff()}伤害。获得本回合雷伤次数×{BlockPerStrike:diff()}的格挡。 |  |
| `cards:VOLIBEAR_U27.base.title` | [DirectEffects.cs:319](<../src/Volibear/Content/Cards/DirectEffects.cs#L319>) | 淬躯爪击 |  |

#### 升级 · VOLIBEAR_U27.upgrade

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"BlockPerStrike": 2, "Damage": 11, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U27.upgrade.description` | [DirectEffects.cs:319](<../src/Volibear/Content/Cards/DirectEffects.cs#L319>) | 造成{Damage:diff()}伤害。获得本回合雷伤次数×{BlockPerStrike:diff()}的格挡。 |  |
| `cards:VOLIBEAR_U27.upgrade.title` | [DirectEffects.cs:319](<../src/Volibear/Content/Cards/DirectEffects.cs#L319>) | 淬躯爪击 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(8m, Move), new DynamicVar("BlockPerStrike", 2m)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_U28

模型来源：[DirectEffects.cs:331](<../src/Volibear/Content/Cards/DirectEffects.cs#L331>)

#### 基础 · VOLIBEAR_U28.base

- 费用：2；类型：Skill；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 12, "IfUpgraded": false, "Lightning": 4}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U28.base.description` | [DirectEffects.cs:334](<../src/Volibear/Content/Cards/DirectEffects.cs#L334>) | 获得{Block:diff()}格挡。迎战。对全体造成{Lightning:diff()}＋吸收的雷伤。 |  |
| `cards:VOLIBEAR_U28.base.title` | [DirectEffects.cs:334](<../src/Volibear/Content/Cards/DirectEffects.cs#L334>) | 雷霆反扑 |  |

#### 升级 · VOLIBEAR_U28.upgrade

- 费用：2；类型：Skill；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 17, "IfUpgraded": true, "Lightning": 6}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U28.upgrade.description` | [DirectEffects.cs:334](<../src/Volibear/Content/Cards/DirectEffects.cs#L334>) | 获得{Block:diff()}格挡。迎战。对全体造成{Lightning:diff()}＋吸收的雷伤。 |  |
| `cards:VOLIBEAR_U28.upgrade.title` | [DirectEffects.cs:334](<../src/Volibear/Content/Cards/DirectEffects.cs#L334>) | 雷霆反扑 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(12m, Move), new DynamicVar("Lightning", 4m)]
UpgradeVar("Block", 5m); UpgradeVar("Lightning", 2m);
```

</details>

### VOLIBEAR_U29

模型来源：[DirectEffects.cs:346](<../src/Volibear/Content/Cards/DirectEffects.cs#L346>)

#### 基础 · VOLIBEAR_U29.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Charge": 2, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U29.base.description` | [DirectEffects.cs:349](<../src/Volibear/Content/Cards/DirectEffects.cs#L349>) | 获得{Charge:diff()}雷势。 |  |
| `cards:VOLIBEAR_U29.base.title` | [DirectEffects.cs:349](<../src/Volibear/Content/Cards/DirectEffects.cs#L349>) | 雷霆渐盛 |  |

#### 升级 · VOLIBEAR_U29.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Charge": 3, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U29.upgrade.description` | [DirectEffects.cs:349](<../src/Volibear/Content/Cards/DirectEffects.cs#L349>) | 获得{Charge:diff()}雷势。 |  |
| `cards:VOLIBEAR_U29.upgrade.title` | [DirectEffects.cs:349](<../src/Volibear/Content/Cards/DirectEffects.cs#L349>) | 雷霆渐盛 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Charge", 2m)]
 UpgradeVar("Charge", 1m);
```

</details>

### VOLIBEAR_U31

模型来源：[ControlledEffects.cs:284](<../src/Volibear/Content/Cards/ControlledEffects.cs#L284>)

#### 基础 · VOLIBEAR_U31.base

- 费用：X；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 5, "IfUpgraded": false, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U31.base.description` | [ControlledEffects.cs:288](<../src/Volibear/Content/Cards/ControlledEffects.cs#L288>) | 造成{Damage:diff()}伤害和{Lightning:diff()}全体雷伤，重复X次。 |  |
| `cards:VOLIBEAR_U31.base.title` | [ControlledEffects.cs:288](<../src/Volibear/Content/Cards/ControlledEffects.cs#L288>) | 万钧连踏 |  |

#### 升级 · VOLIBEAR_U31.upgrade

- 费用：X；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 7, "IfUpgraded": true, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U31.upgrade.description` | [ControlledEffects.cs:288](<../src/Volibear/Content/Cards/ControlledEffects.cs#L288>) | 造成{Damage:diff()}伤害和{Lightning:diff()}全体雷伤，重复X次。 |  |
| `cards:VOLIBEAR_U31.upgrade.title` | [ControlledEffects.cs:288](<../src/Volibear/Content/Cards/ControlledEffects.cs#L288>) | 万钧连踏 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(5m, Move), new DynamicVar("Lightning", 3m)]
 UpgradeVar("Damage", 2m);
```

</details>

### VOLIBEAR_U32

模型来源：[PersistentEffects.cs:117](<../src/Volibear/Content/Cards/PersistentEffects.cs#L117>)

#### 基础 · VOLIBEAR_U32.base

- 费用：2；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Discount": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U32.base.description` | [PersistentEffects.cs:120](<../src/Volibear/Content/Cards/PersistentEffects.cs#L120>) | 领域1。本回合下一张攻击减费{Discount:diff()}。每回合首次迎战后，下一张攻击减费{Discount:diff()}。 |  |
| `cards:VOLIBEAR_U32.base.title` | [PersistentEffects.cs:120](<../src/Volibear/Content/Cards/PersistentEffects.cs#L120>) | 迎雷 |  |

#### 升级 · VOLIBEAR_U32.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Discount": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U32.upgrade.description` | [PersistentEffects.cs:120](<../src/Volibear/Content/Cards/PersistentEffects.cs#L120>) | 领域1。本回合下一张攻击减费{Discount:diff()}。每回合首次迎战后，下一张攻击减费{Discount:diff()}。 |  |
| `cards:VOLIBEAR_U32.upgrade.title` | [PersistentEffects.cs:120](<../src/Volibear/Content/Cards/PersistentEffects.cs#L120>) | 迎雷 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Discount", 1m)]
EnergyCost.UpgradeBy(-1); UpgradeVar("Discount", 1m);
```

</details>

### VOLIBEAR_U34

模型来源：[PersistentEffects.cs:132](<../src/Volibear/Content/Cards/PersistentEffects.cs#L132>)

#### 基础 · VOLIBEAR_U34.base

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Armor": 3, "Block": 4, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U34.base.description` | [PersistentEffects.cs:135](<../src/Volibear/Content/Cards/PersistentEffects.cs#L135>) | 获得{Block:diff()}格挡。每造成1次雷伤，获得{Armor:diff()}格挡。 |  |
| `cards:VOLIBEAR_U34.base.title` | [PersistentEffects.cs:135](<../src/Volibear/Content/Cards/PersistentEffects.cs#L135>) | 雷甲 |  |

#### 升级 · VOLIBEAR_U34.upgrade

- 费用：1；类型：Power；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Armor": 4, "Block": 7, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U34.upgrade.description` | [PersistentEffects.cs:135](<../src/Volibear/Content/Cards/PersistentEffects.cs#L135>) | 获得{Block:diff()}格挡。每造成1次雷伤，获得{Armor:diff()}格挡。 |  |
| `cards:VOLIBEAR_U34.upgrade.title` | [PersistentEffects.cs:135](<../src/Volibear/Content/Cards/PersistentEffects.cs#L135>) | 雷甲 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(4m, Move), new DynamicVar("Armor", 3m)]
UpgradeVar("Block", 3m); UpgradeVar("Armor", 1m);
```

</details>

### VOLIBEAR_U35

模型来源：[DirectEffects.cs:356](<../src/Volibear/Content/Cards/DirectEffects.cs#L356>)

#### 基础 · VOLIBEAR_U35.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 8, "IfUpgraded": false, "Lightning": 3}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U35.base.description` | [DirectEffects.cs:359](<../src/Volibear/Content/Cards/DirectEffects.cs#L359>) | 获得{Block:diff()}格挡。对全体造成{Lightning:diff()}雷伤。迎战。 |  |
| `cards:VOLIBEAR_U35.base.title` | [DirectEffects.cs:359](<../src/Volibear/Content/Cards/DirectEffects.cs#L359>) | 霹天雳地 |  |

#### 升级 · VOLIBEAR_U35.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Block": 11, "IfUpgraded": true, "Lightning": 5}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U35.upgrade.description` | [DirectEffects.cs:359](<../src/Volibear/Content/Cards/DirectEffects.cs#L359>) | 获得{Block:diff()}格挡。对全体造成{Lightning:diff()}雷伤。迎战。 |  |
| `cards:VOLIBEAR_U35.upgrade.title` | [DirectEffects.cs:359](<../src/Volibear/Content/Cards/DirectEffects.cs#L359>) | 霹天雳地 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(8m, Move), new DynamicVar("Lightning", 3m)]
UpgradeVar("Block", 3m); UpgradeVar("Lightning", 2m);
```

</details>

### VOLIBEAR_U36

模型来源：[DirectEffects.cs:371](<../src/Volibear/Content/Cards/DirectEffects.cs#L371>)

#### 基础 · VOLIBEAR_U36.base

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Cards": 1, "Energy": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U36.base.description` | [DirectEffects.cs:374](<../src/Volibear/Content/Cards/DirectEffects.cs#L374>) | 获得{Energy:diff()}能量。本回合此前造成过雷伤时，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U36.base.title` | [DirectEffects.cs:374](<../src/Volibear/Content/Cards/DirectEffects.cs#L374>) | 奔雷 |  |

#### 升级 · VOLIBEAR_U36.upgrade

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"Cards": 1, "Energy": 2, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U36.upgrade.description` | [DirectEffects.cs:374](<../src/Volibear/Content/Cards/DirectEffects.cs#L374>) | 获得{Energy:diff()}能量。本回合此前造成过雷伤时，抽{Cards:diff()}张牌。 |  |
| `cards:VOLIBEAR_U36.upgrade.title` | [DirectEffects.cs:374](<../src/Volibear/Content/Cards/DirectEffects.cs#L374>) | 奔雷 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new EnergyVar(1), new CardsVar(1)]
 UpgradeVar("Energy", 1m);
```

</details>

### VOLIBEAR_U37

模型来源：[DirectEffects.cs:387](<../src/Volibear/Content/Cards/DirectEffects.cs#L387>)

#### 基础 · VOLIBEAR_U37.base

- 费用：2；类型：Skill；稀有度：Uncommon；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Domain": 1, "IfUpgraded": false, "Lightning": 12}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U37.base.description` | [DirectEffects.cs:390](<../src/Volibear/Content/Cards/DirectEffects.cs#L390>) | 对全体造成{Lightning:diff()}雷伤。领域{Domain:diff()}。 |  |
| `cards:VOLIBEAR_U37.base.title` | [DirectEffects.cs:390](<../src/Volibear/Content/Cards/DirectEffects.cs#L390>) | 风暴汇聚 |  |

#### 升级 · VOLIBEAR_U37.upgrade

- 费用：2；类型：Skill；稀有度：Uncommon；目标：AllEnemies；原生关键词：无。
- 模板变量：`{"Domain": 1, "IfUpgraded": true, "Lightning": 16}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U37.upgrade.description` | [DirectEffects.cs:390](<../src/Volibear/Content/Cards/DirectEffects.cs#L390>) | 对全体造成{Lightning:diff()}雷伤。领域{Domain:diff()}。 |  |
| `cards:VOLIBEAR_U37.upgrade.title` | [DirectEffects.cs:390](<../src/Volibear/Content/Cards/DirectEffects.cs#L390>) | 风暴汇聚 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 12m), new DynamicVar("Domain", 1m)]
 UpgradeVar("Lightning", 4m);
```

</details>

### VOLIBEAR_U38

模型来源：[HistoryEffects.cs:81](<../src/Volibear/Content/Cards/HistoryEffects.cs#L81>)

#### 基础 · VOLIBEAR_U38.base

- 费用：3；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 18, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U38.base.description` | [HistoryEffects.cs:84](<../src/Volibear/Content/Cards/HistoryEffects.cs#L84>) | 造成{Damage:diff()}伤害。本回合每造成1次雷伤，本牌费用−1。 |  |
| `cards:VOLIBEAR_U38.base.title` | [HistoryEffects.cs:84](<../src/Volibear/Content/Cards/HistoryEffects.cs#L84>) | 雷势奔袭 |  |

#### 升级 · VOLIBEAR_U38.upgrade

- 费用：3；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 24, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U38.upgrade.description` | [HistoryEffects.cs:84](<../src/Volibear/Content/Cards/HistoryEffects.cs#L84>) | 造成{Damage:diff()}伤害。本回合每造成1次雷伤，本牌费用−1。 |  |
| `cards:VOLIBEAR_U38.upgrade.title` | [HistoryEffects.cs:84](<../src/Volibear/Content/Cards/HistoryEffects.cs#L84>) | 雷势奔袭 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(18m, Move)]
 UpgradeVar("Damage", 6m);
```

</details>

### VOLIBEAR_U39

模型来源：[PreparedEffects.cs:154](<../src/Volibear/Content/Cards/PreparedEffects.cs#L154>)

#### 基础 · VOLIBEAR_U39.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 4, "Domain": 1, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U39.base.description` | [PreparedEffects.cs:157](<../src/Volibear/Content/Cards/PreparedEffects.cs#L157>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。检索1张雷法。 |  |
| `cards:VOLIBEAR_U39.base.title` | [PreparedEffects.cs:157](<../src/Volibear/Content/Cards/PreparedEffects.cs#L157>) | 雷暴先兆 |  |

#### 升级 · VOLIBEAR_U39.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 7, "Domain": 1, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U39.upgrade.description` | [PreparedEffects.cs:157](<../src/Volibear/Content/Cards/PreparedEffects.cs#L157>) | 获得{Block:diff()}格挡。领域{Domain:diff()}。检索1张雷法。 |  |
| `cards:VOLIBEAR_U39.upgrade.title` | [PreparedEffects.cs:157](<../src/Volibear/Content/Cards/PreparedEffects.cs#L157>) | 雷暴先兆 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(4m, Move), new DynamicVar("Domain", 1m)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_U40

模型来源：[DirectEffects.cs:401](<../src/Volibear/Content/Cards/DirectEffects.cs#L401>)

#### 基础 · VOLIBEAR_U40.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Energy": 2, "IfUpgraded": false, "Lightning": 8, "Threshold": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U40.base.description` | [DirectEffects.cs:404](<../src/Volibear/Content/Cards/DirectEffects.cs#L404>) | 造成{Lightning:diff()}雷伤。本回合此前已造成至少{Threshold:diff()}次雷伤时，获得{Energy:diff()}能量。 |  |
| `cards:VOLIBEAR_U40.base.title` | [DirectEffects.cs:404](<../src/Volibear/Content/Cards/DirectEffects.cs#L404>) | 雷路贯通 |  |

#### 升级 · VOLIBEAR_U40.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Energy": 2, "IfUpgraded": true, "Lightning": 12, "Threshold": 2}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U40.upgrade.description` | [DirectEffects.cs:404](<../src/Volibear/Content/Cards/DirectEffects.cs#L404>) | 造成{Lightning:diff()}雷伤。本回合此前已造成至少{Threshold:diff()}次雷伤时，获得{Energy:diff()}能量。 |  |
| `cards:VOLIBEAR_U40.upgrade.title` | [DirectEffects.cs:404](<../src/Volibear/Content/Cards/DirectEffects.cs#L404>) | 雷路贯通 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DynamicVar("Lightning", 8m), new DynamicVar("Threshold", 2m), new EnergyVar(2)]
 UpgradeVar("Lightning", 4m);
```

</details>

### VOLIBEAR_U41

模型来源：[BeastEffects.cs:80](<../src/Volibear/Content/Cards/BeastEffects.cs#L80>)

#### 基础 · VOLIBEAR_U41.base

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 3, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U41.base.description` | [BeastEffects.cs:83](<../src/Volibear/Content/Cards/BeastEffects.cs#L83>) | 造成{Damage:diff()}伤害。兽化1张攻击手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_U41.base.title` | [BeastEffects.cs:83](<../src/Volibear/Content/Cards/BeastEffects.cs#L83>) | 破皮见骨 |  |

#### 升级 · VOLIBEAR_U41.upgrade

- 费用：1；类型：Attack；稀有度：Uncommon；目标：AnyEnemy；原生关键词：无。
- 模板变量：`{"Damage": 6, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U41.upgrade.description` | [BeastEffects.cs:83](<../src/Volibear/Content/Cards/BeastEffects.cs#L83>) | 造成{Damage:diff()}伤害。兽化1张攻击手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_U41.upgrade.title` | [BeastEffects.cs:83](<../src/Volibear/Content/Cards/BeastEffects.cs#L83>) | 破皮见骨 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new DamageVar(3m, Move)]
 UpgradeVar("Damage", 3m);
```

</details>

### VOLIBEAR_U42

模型来源：[BeastEffects.cs:96](<../src/Volibear/Content/Cards/BeastEffects.cs#L96>)

#### 基础 · VOLIBEAR_U42.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 3, "IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U42.base.description` | [BeastEffects.cs:99](<../src/Volibear/Content/Cards/BeastEffects.cs#L99>) | 获得{Block:diff()}格挡。兽化1张非攻击手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_U42.base.title` | [BeastEffects.cs:99](<../src/Volibear/Content/Cards/BeastEffects.cs#L99>) | 蛮荒护体 |  |

#### 升级 · VOLIBEAR_U42.upgrade

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：无。
- 模板变量：`{"Block": 6, "IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U42.upgrade.description` | [BeastEffects.cs:99](<../src/Volibear/Content/Cards/BeastEffects.cs#L99>) | 获得{Block:diff()}格挡。兽化1张非攻击手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_U42.upgrade.title` | [BeastEffects.cs:99](<../src/Volibear/Content/Cards/BeastEffects.cs#L99>) | 蛮荒护体 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
[new BlockVar(3m, Move)]
 UpgradeVar("Block", 3m);
```

</details>

### VOLIBEAR_U43

模型来源：[BeastEffects.cs:111](<../src/Volibear/Content/Cards/BeastEffects.cs#L111>)

#### 基础 · VOLIBEAR_U43.base

- 费用：1；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"IfUpgraded": false}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U43.base.description` | [BeastEffects.cs:114](<../src/Volibear/Content/Cards/BeastEffects.cs#L114>) | 检索1张牌，兽化1张手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_U43.base.title` | [BeastEffects.cs:114](<../src/Volibear/Content/Cards/BeastEffects.cs#L114>) | 循着本能 |  |

#### 升级 · VOLIBEAR_U43.upgrade

- 费用：0；类型：Skill；稀有度：Uncommon；目标：Self；原生关键词：Exhaust。
- 模板变量：`{"IfUpgraded": true}`。

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_U43.upgrade.description` | [BeastEffects.cs:114](<../src/Volibear/Content/Cards/BeastEffects.cs#L114>) | 检索1张牌，兽化1张手牌，其本回合下次打出时设为0费。 |  |
| `cards:VOLIBEAR_U43.upgrade.title` | [BeastEffects.cs:114](<../src/Volibear/Content/Cards/BeastEffects.cs#L114>) | 循着本能 |  |

<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>

```csharp
// 无额外 CanonicalVars
 EnergyCost.UpgradeBy(-1);
```

</details>

## 其它硬编码文本

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `literal:src/Volibear/Content/VolibearCardPool.cs:VolibearCardPool:1` | [VolibearCardPool.cs:13](<../src/Volibear/Content/VolibearCardPool.cs#L13>) | 沃利贝尔 |  |

## 剧情

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `ancients:THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-0r.ancient` | [VolibearLoc.cs:60](<../src/Volibear/Content/VolibearLoc.cs#L60>) | 你的风暴，已经震动了这里的根基。 |  |
| `ancients:THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-1r.char` | [VolibearLoc.cs:61](<../src/Volibear/Content/VolibearLoc.cs#L61>) | 石墙会崩塌。雷霆不会。 |  |
| `ancients:THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-2r.ancient` | [VolibearLoc.cs:62](<../src/Volibear/Content/VolibearLoc.cs#L62>) | 那就让我看看，这场风暴还能持续多久。 |  |

## 选牌与兽化提示

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `cards:VOLIBEAR_C07.selectionScreenPrompt` | [ControlledEffects.cs:178](<../src/Volibear/Content/Cards/ControlledEffects.cs#L178>) | 选择{Amount}张攻击加入手牌。 |  |
| `cards:VOLIBEAR_C15.selectionScreenPrompt` | [ControlledEffects.cs:208](<../src/Volibear/Content/Cards/ControlledEffects.cs#L208>) | 选择1张攻击或雷法加入手牌。 |  |
| `cards:VOLIBEAR_C19.selectionScreenPrompt` | [PreparedEffects.cs:44](<../src/Volibear/Content/Cards/PreparedEffects.cs#L44>) | 选择1张攻击获得保留与蓄势。 |  |
| `cards:VOLIBEAR_R10.selectionScreenPrompt` | [ControlledEffects.cs:347](<../src/Volibear/Content/Cards/ControlledEffects.cs#L347>) | 选择至多{Amount}张攻击加入手牌。 |  |
| `cards:VOLIBEAR_R25.selectionScreenPrompt` | [ControlledEffects.cs:381](<../src/Volibear/Content/Cards/ControlledEffects.cs#L381>) | 选择至多{Amount}张技能加入手牌。 |  |
| `cards:VOLIBEAR_R27.beastSelectionPrompt` | [BeastEffects.cs:131](<../src/Volibear/Content/Cards/BeastEffects.cs#L131>) | 选择至多{Amount}张手牌兽化。 |  |
| `cards:VOLIBEAR_R28.beastSelectionPrompt` | [BeastEffects.cs:144](<../src/Volibear/Content/Cards/BeastEffects.cs#L144>) | 可以选择1张手牌兽化。 |  |
| `cards:VOLIBEAR_R30.beastSelectionPrompt` | [BeastEffects.cs:173](<../src/Volibear/Content/Cards/BeastEffects.cs#L173>) | 选择1张手牌兽化。 |  |
| `cards:VOLIBEAR_U17.selectionScreenPrompt` | [ControlledEffects.cs:273](<../src/Volibear/Content/Cards/ControlledEffects.cs#L273>) | 可选择任意张牌移至弃牌堆；其余牌保持顺序。 |  |
| `cards:VOLIBEAR_U39.selectionScreenPrompt` | [PreparedEffects.cs:158](<../src/Volibear/Content/Cards/PreparedEffects.cs#L158>) | 选择1张雷法加入手牌。 |  |
| `cards:VOLIBEAR_U41.beastSelectionPrompt` | [BeastEffects.cs:84](<../src/Volibear/Content/Cards/BeastEffects.cs#L84>) | 选择1张攻击手牌兽化。 |  |
| `cards:VOLIBEAR_U42.beastSelectionPrompt` | [BeastEffects.cs:100](<../src/Volibear/Content/Cards/BeastEffects.cs#L100>) | 选择1张非攻击手牌兽化。 |  |
| `cards:VOLIBEAR_U43.beastSelectionPrompt` | [BeastEffects.cs:115](<../src/Volibear/Content/Cards/BeastEffects.cs#L115>) | 选择1张手牌兽化。 |  |
| `cards:VOLIBEAR_U43.selectionScreenPrompt` | [BeastEffects.cs:115](<../src/Volibear/Content/Cards/BeastEffects.cs#L115>) | 选择1张牌加入手牌。 |  |

## 角色

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `characters:VOLIBEAR_CHARACTER.aromaPrinciple` | [VolibearLoc.cs:40](<../src/Volibear/Content/VolibearLoc.cs#L40>) | 风暴只服从自己的意志 |  |
| `characters:VOLIBEAR_CHARACTER.banter.alive.endTurnPing` | [VolibearLoc.cs:42](<../src/Volibear/Content/VolibearLoc.cs#L42>) | 风暴不会等待。 |  |
| `characters:VOLIBEAR_CHARACTER.banter.dead.endTurnPing` | [VolibearLoc.cs:43](<../src/Volibear/Content/VolibearLoc.cs#L43>) | 雷声尚未消散…… |  |
| `characters:VOLIBEAR_CHARACTER.cardsModifierDescription` | [VolibearLoc.cs:38](<../src/Volibear/Content/VolibearLoc.cs#L38>) | 沃利贝尔的卡牌会出现在奖励和商店中。 |  |
| `characters:VOLIBEAR_CHARACTER.cardsModifierTitle` | [VolibearLoc.cs:37](<../src/Volibear/Content/VolibearLoc.cs#L37>) | 不灭狂雷 |  |
| `characters:VOLIBEAR_CHARACTER.description` | [VolibearLoc.cs:31](<../src/Volibear/Content/VolibearLoc.cs#L31>) | 不灭狂雷。以雷霆与兽性碾碎敌人。 |  |
| `characters:VOLIBEAR_CHARACTER.eventDeathPrevention` | [VolibearLoc.cs:39](<../src/Volibear/Content/VolibearLoc.cs#L39>) | 雷霆拒绝了死亡。 |  |
| `characters:VOLIBEAR_CHARACTER.goldMonologue` | [VolibearLoc.cs:41](<../src/Volibear/Content/VolibearLoc.cs#L41>) | 这些金属，终将被雷霆熔铸。 |  |
| `characters:VOLIBEAR_CHARACTER.possessiveAdjective` | [VolibearLoc.cs:36](<../src/Volibear/Content/VolibearLoc.cs#L36>) | 他的 |  |
| `characters:VOLIBEAR_CHARACTER.pronounObject` | [VolibearLoc.cs:34](<../src/Volibear/Content/VolibearLoc.cs#L34>) | 他 |  |
| `characters:VOLIBEAR_CHARACTER.pronounPossessive` | [VolibearLoc.cs:35](<../src/Volibear/Content/VolibearLoc.cs#L35>) | 他的 |  |
| `characters:VOLIBEAR_CHARACTER.pronounSubject` | [VolibearLoc.cs:33](<../src/Volibear/Content/VolibearLoc.cs#L33>) | 他 |  |
| `characters:VOLIBEAR_CHARACTER.title` | [VolibearLoc.cs:30](<../src/Volibear/Content/VolibearLoc.cs#L30>) | 沃利贝尔 |  |
| `characters:VOLIBEAR_CHARACTER.titleObject` | [VolibearLoc.cs:32](<../src/Volibear/Content/VolibearLoc.cs#L32>) | 沃利贝尔 |  |

## 关键词匹配词（非独立可见文案）

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `glossary-match:ABSORPTION.0` | [MechanicGlossary.cs:17](<../src/Volibear/Content/MechanicGlossary.cs#L17>) | 吸收 |  |
| `glossary-match:BEASTIFY.0` | [MechanicGlossary.cs:21](<../src/Volibear/Content/MechanicGlossary.cs#L21>) | 兽化 |  |
| `glossary-match:BEAST_FORM.0` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 兽形 |  |
| `glossary-match:BEAST_FORM.1` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 爪形 |  |
| `glossary-match:BEAST_FORM.2` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 躯形 |  |
| `glossary-match:BEAST_FORM.3` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 裂骨之爪 |  |
| `glossary-match:BEAST_FORM.4` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 风暴之躯 |  |
| `glossary-match:BITE.0` | [MechanicGlossary.cs:23](<../src/Volibear/Content/MechanicGlossary.cs#L23>) | 咬痕 |  |
| `glossary-match:DISCOUNT.0` | [MechanicGlossary.cs:34](<../src/Volibear/Content/MechanicGlossary.cs#L34>) | 减费 |  |
| `glossary-match:DOMAIN.0` | [MechanicGlossary.cs:15](<../src/Volibear/Content/MechanicGlossary.cs#L15>) | 领域 |  |
| `glossary-match:DRAIN.0` | [MechanicGlossary.cs:28](<../src/Volibear/Content/MechanicGlossary.cs#L28>) | 汲取 |  |
| `glossary-match:ENGAGE.0` | [MechanicGlossary.cs:14](<../src/Volibear/Content/MechanicGlossary.cs#L14>) | 迎战 |  |
| `glossary-match:LIGHTNING.0` | [MechanicGlossary.cs:18](<../src/Volibear/Content/MechanicGlossary.cs#L18>) | 雷伤 |  |
| `glossary-match:PREPARE.0` | [MechanicGlossary.cs:25](<../src/Volibear/Content/MechanicGlossary.cs#L25>) | 蓄势 |  |
| `glossary-match:PURIFY.0` | [MechanicGlossary.cs:31](<../src/Volibear/Content/MechanicGlossary.cs#L31>) | 净化消耗 |  |
| `glossary-match:PURIFY.1` | [MechanicGlossary.cs:31](<../src/Volibear/Content/MechanicGlossary.cs#L31>) | 净化 |  |
| `glossary-match:RECOVER.0` | [MechanicGlossary.cs:33](<../src/Volibear/Content/MechanicGlossary.cs#L33>) | 回收 |  |
| `glossary-match:REPLAY.0` | [MechanicGlossary.cs:27](<../src/Volibear/Content/MechanicGlossary.cs#L27>) | 重演 |  |
| `glossary-match:RETAIN_BLOCK.0` | [MechanicGlossary.cs:29](<../src/Volibear/Content/MechanicGlossary.cs#L29>) | 留甲 |  |
| `glossary-match:RETALIATE.0` | [MechanicGlossary.cs:24](<../src/Volibear/Content/MechanicGlossary.cs#L24>) | 反雷 |  |
| `glossary-match:RETRIEVE.0` | [MechanicGlossary.cs:32](<../src/Volibear/Content/MechanicGlossary.cs#L32>) | 检索 |  |
| `glossary-match:SUPPRESSION.0` | [MechanicGlossary.cs:16](<../src/Volibear/Content/MechanicGlossary.cs#L16>) | 领域 |  |
| `glossary-match:THUNDER_FORCE.0` | [MechanicGlossary.cs:19](<../src/Volibear/Content/MechanicGlossary.cs#L19>) | 雷势 |  |
| `glossary-match:THUNDER_SPELL.0` | [MechanicGlossary.cs:20](<../src/Volibear/Content/MechanicGlossary.cs#L20>) | 雷法 |  |
| `glossary-match:TRAIN.0` | [MechanicGlossary.cs:26](<../src/Volibear/Content/MechanicGlossary.cs#L26>) | 强化 |  |
| `glossary-match:UNBREAKABLE.0` | [MechanicGlossary.cs:30](<../src/Volibear/Content/MechanicGlossary.cs#L30>) | 坚甲 |  |

## 关键词悬停

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `static_hover_tips:VOLIBEAR-ABSORPTION.description` | [MechanicGlossary.cs:17](<../src/Volibear/Content/MechanicGlossary.cs#L17>) | 本次迎战中，发起者的格挡实际挡住的伤害总量。按每个伤害段累计；完全格挡也计算，坚甲未减少格挡仍照计。队友挡住的伤害不计入你的吸收。 | 本次迎战中，发起者的格挡实际挡住的伤害总量。 |
| `static_hover_tips:VOLIBEAR-ABSORPTION.title` | [MechanicGlossary.cs:17](<../src/Volibear/Content/MechanicGlossary.cs#L17>) | 吸收 |  |
| `static_hover_tips:VOLIBEAR-BEASTIFY.description` | [MechanicGlossary.cs:21](<../src/Volibear/Content/MechanicGlossary.cs#L21>) | 先消耗原牌，再在原牌所在牌堆生成新的兽形牌：攻击生成裂骨之爪，其他牌生成风暴之躯。原牌正常触发消耗响应；新牌继承升级、临时减费与保留，使用后消耗。已有兽形不重复转换。永久牌组保持原牌。 | 先消耗原牌，再生成新的兽形牌：攻击生成裂骨之爪，其他牌生成风暴之躯。 |
| `static_hover_tips:VOLIBEAR-BEASTIFY.title` | [MechanicGlossary.cs:21](<../src/Volibear/Content/MechanicGlossary.cs#L21>) | 兽化 |  |
| `static_hover_tips:VOLIBEAR-BEAST_FORM.description` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 裂骨之爪与风暴之躯的统称。爪形为攻击，躯形为直接造成雷伤的技能；继承材料升级，使用后消耗。 |  |
| `static_hover_tips:VOLIBEAR-BEAST_FORM.title` | [MechanicGlossary.cs:22](<../src/Volibear/Content/MechanicGlossary.cs#L22>) | 兽形 |  |
| `static_hover_tips:VOLIBEAR-BITE.description` | [MechanicGlossary.cs:23](<../src/Volibear/Content/MechanicGlossary.cs#L23>) | 暴怒撕咬命中后留下的标记，按发起玩家与敌人实体分别记录，持续本战。完全格挡仍可留下标记。追加伤害读取本次出牌前的标记，同次重演不会借用本牌刚施加的标记。 | 暴怒撕咬命中后留下的标记。 |
| `static_hover_tips:VOLIBEAR-BITE.title` | [MechanicGlossary.cs:23](<../src/Volibear/Content/MechanicGlossary.cs#L23>) | 咬痕 |  |
| `static_hover_tips:VOLIBEAR-DISCOUNT.description` | [MechanicGlossary.cs:34](<../src/Volibear/Content/MechanicGlossary.cs#L34>) | 按牌面为指定牌或下一张符合条件的牌降低费用，最低0。同类待用减费取最大值；实际打出时消费。X费牌仍按原生X费规则支付。 | 为指定牌降低费用 |
| `static_hover_tips:VOLIBEAR-DISCOUNT.title` | [MechanicGlossary.cs:34](<../src/Volibear/Content/MechanicGlossary.cs#L34>) | 减费 |  |
| `static_hover_tips:VOLIBEAR-DOMAIN.description` | [MechanicGlossary.cs:15](<../src/Volibear/Content/MechanicGlossary.cs#L15>) | 展开或延长指定轮数。领域1持续到你的下一次正常起手抽牌结束，抽完才扣1轮；永久领域持续本战。你每次实际打出的攻击牌，在领域内首次普通攻击段后，对全体附加4＋当前雷势的雷伤，多段与重演共用一次机会。你实际抽到状态或诅咒时，净化消耗并补抽1张。敌方特殊效果的压制对全队生效；任一存活持有者仍有领域，压制就继续，多人领域不使压制翻倍。 | 展开指定轮数，每轮领域持续到下回合抽牌后。领域期间禁用敌方的特殊能力，禁用自身debuff，每抽到状态或诅咒消耗并补抽1张牌，每打出一张攻击牌对全体造成4雷伤。 |
| `static_hover_tips:VOLIBEAR-DOMAIN.title` | [MechanicGlossary.cs:15](<../src/Volibear/Content/MechanicGlossary.cs#L15>) | 领域 |  |
| `static_hover_tips:VOLIBEAR-DRAIN.description` | [MechanicGlossary.cs:28](<../src/Volibear/Content/MechanicGlossary.cs#L28>) | 按照该段伤害实际造成的生命损失恢复生命。 | 按照实际造成的伤害恢复生命。 |
| `static_hover_tips:VOLIBEAR-DRAIN.title` | [MechanicGlossary.cs:28](<../src/Volibear/Content/MechanicGlossary.cs#L28>) | 汲取 |  |
| `static_hover_tips:VOLIBEAR-ENGAGE.description` | [MechanicGlossary.cs:14](<../src/Volibear/Content/MechanicGlossary.cs#L14>) | 按牌面顺序，令目标立即执行本轮尚未使用的真实行动。每名敌人每轮只有一次机会，全队共享；正常敌方阶段跳过已迎战的行动。保留敌人原本的攻击目标，不会让发起者替队友承伤。目标提前死亡或已经行动时不再执行；行动实际开始、发起者存活且战斗继续，才触发迎战完成收益。 | 令目标立即执行当前意图。 |
| `static_hover_tips:VOLIBEAR-ENGAGE.title` | [MechanicGlossary.cs:14](<../src/Volibear/Content/MechanicGlossary.cs#L14>) | 迎战 |  |
| `static_hover_tips:VOLIBEAR-LIGHTNING.description` | [MechanicGlossary.cs:18](<../src/Volibear/Content/MechanicGlossary.cs#L18>) | 非普通攻击伤害。加上当前雷势及明确适用的增幅，不受普通攻击的力量、虚弱与易伤加成。仍经过格挡、减免和死亡结算。每段完整雷伤计1次，全体同一段也只计1次；不会递归触发普通攻击响应。 | 法术伤害，受雷势增幅 |
| `static_hover_tips:VOLIBEAR-LIGHTNING.title` | [MechanicGlossary.cs:18](<../src/Volibear/Content/MechanicGlossary.cs#L18>) | 雷伤 |  |
| `static_hover_tips:VOLIBEAR-PREPARE.description` | [MechanicGlossary.cs:25](<../src/Volibear/Content/MechanicGlossary.cs#L25>) | 指定牌下次打出时，每段固定普通攻击伤害增加指定值；该次完整出牌结算后清除。不会增加雷伤。 | 指定牌下次打出时，每段攻击伤害增加指定值 |
| `static_hover_tips:VOLIBEAR-PREPARE.title` | [MechanicGlossary.cs:25](<../src/Volibear/Content/MechanicGlossary.cs#L25>) | 蓄势 |  |
| `static_hover_tips:VOLIBEAR-PURIFY.description` | [MechanicGlossary.cs:31](<../src/Volibear/Content/MechanicGlossary.cs#L31>) | 先禁止所选状态或诅咒牌自身的效果，再消耗该牌。其他遗物与能力的消耗响应仍会触发。领域的实际抽牌净化会补抽1张；普通净化按牌面执行。 | 先禁止所选状态或诅咒牌自身的效果，再消耗该牌。 |
| `static_hover_tips:VOLIBEAR-PURIFY.title` | [MechanicGlossary.cs:31](<../src/Volibear/Content/MechanicGlossary.cs#L31>) | 净化消耗 |  |
| `static_hover_tips:VOLIBEAR-RECOVER.description` | [MechanicGlossary.cs:33](<../src/Volibear/Content/MechanicGlossary.cs#L33>) | 从弃牌堆选择符合条件的牌加入手牌，受手牌上限约束。回收不是抽牌，不触发领域的抽牌净化。 | 从弃牌堆选择符合条件的牌加入手牌。 |
| `static_hover_tips:VOLIBEAR-RECOVER.title` | [MechanicGlossary.cs:33](<../src/Volibear/Content/MechanicGlossary.cs#L33>) | 回收 |  |
| `static_hover_tips:VOLIBEAR-REPLAY.description` | [MechanicGlossary.cs:27](<../src/Volibear/Content/MechanicGlossary.cs#L27>) | 额外结算完整牌效，沿用原目标、已支付的X和出牌前记录。不再次付费，不另算一次打出；与原牌共用领域附雷机会。 | 额外结算完整牌效。 |
| `static_hover_tips:VOLIBEAR-REPLAY.title` | [MechanicGlossary.cs:27](<../src/Volibear/Content/MechanicGlossary.cs#L27>) | 重演 |  |
| `static_hover_tips:VOLIBEAR-RETAIN_BLOCK.description` | [MechanicGlossary.cs:29](<../src/Volibear/Content/MechanicGlossary.cs#L29>) | 回合开始时，格挡变为当前格挡减去指定值，最低0。重复获得时取较小的损耗。此更新不是获得格挡。 | 回合开始时，格挡不再移除，改为最多减少指定值 |
| `static_hover_tips:VOLIBEAR-RETAIN_BLOCK.title` | [MechanicGlossary.cs:29](<../src/Volibear/Content/MechanicGlossary.cs#L29>) | 留甲 |  |
| `static_hover_tips:VOLIBEAR-RETALIATE.description` | [MechanicGlossary.cs:24](<../src/Volibear/Content/MechanicGlossary.cs#L24>) | 本轮每承受一段敌人攻击后，对该攻击者造成牌面指定的雷伤。完全格挡也触发；多段攻击逐段响应。 | 每承受一段敌人攻击后，对该攻击者造成指定的雷伤。 |
| `static_hover_tips:VOLIBEAR-RETALIATE.title` | [MechanicGlossary.cs:24](<../src/Volibear/Content/MechanicGlossary.cs#L24>) | 反雷 |  |
| `static_hover_tips:VOLIBEAR-RETRIEVE.description` | [MechanicGlossary.cs:32](<../src/Volibear/Content/MechanicGlossary.cs#L32>) | 从抽牌堆选择符合条件的牌加入手牌，受手牌上限约束。检索不是抽牌，不触发领域的抽牌净化。 | 从抽牌堆选择符合条件的牌加入手牌。 |
| `static_hover_tips:VOLIBEAR-RETRIEVE.title` | [MechanicGlossary.cs:32](<../src/Volibear/Content/MechanicGlossary.cs#L32>) | 检索 |  |
| `static_hover_tips:VOLIBEAR-SUPPRESSION.description` | [MechanicGlossary.cs:16](<../src/Volibear/Content/MechanicGlossary.cs#L16>) | 压制对敌人有利的特殊效果，例如复活、保护阶段、限伤、不可选和给玩家施加负面效果。保留普通攻击、已有及直接获得的力量与格挡。敌人自身的不利效果、状态到期和必要清理正常执行；混合效果分别处理。已取消的一次性效果不会在领域结束后补发。 | 压制对敌人有利的特殊效果，例如复活、保护阶段、限伤、不可选和给玩家施加负面效果。保留普通攻击、已有及直接获得的力量与格挡。 |
| `static_hover_tips:VOLIBEAR-SUPPRESSION.title` | [MechanicGlossary.cs:16](<../src/Volibear/Content/MechanicGlossary.cs#L16>) | 领域压制 |  |
| `static_hover_tips:VOLIBEAR-THUNDER_FORCE.description` | [MechanicGlossary.cs:19](<../src/Volibear/Content/MechanicGlossary.cs#L19>) | 每点使每段雷伤增加1，持续本战，不自动消耗。一批全体雷伤使用同一份雷势数值；响应中新获得的雷势从下一批生效。 | 每点使每段雷伤增加1。 |
| `static_hover_tips:VOLIBEAR-THUNDER_FORCE.title` | [MechanicGlossary.cs:19](<../src/Volibear/Content/MechanicGlossary.cs#L19>) | 雷势 |  |
| `static_hover_tips:VOLIBEAR-THUNDER_SPELL.description` | [MechanicGlossary.cs:20](<../src/Volibear/Content/MechanicGlossary.cs#L20>) | 牌面自身直接造成雷伤的技能。普通攻击附带雷伤仍是攻击；领域附雷不会把一张牌变成雷法。风暴之躯属于雷法。 | 牌面自身直接造成雷伤的技能。 |
| `static_hover_tips:VOLIBEAR-THUNDER_SPELL.title` | [MechanicGlossary.cs:20](<../src/Volibear/Content/MechanicGlossary.cs#L20>) | 雷法 |  |
| `static_hover_tips:VOLIBEAR-TRAIN.description` | [MechanicGlossary.cs:26](<../src/Volibear/Content/MechanicGlossary.cs#L26>) | 指定牌本战每段自身普通攻击与原生雷伤增加指定值。不是角色雷势，也不会提高其他牌的伤害。 | 指定牌本战每段自身攻击与雷伤增加指定值。 |
| `static_hover_tips:VOLIBEAR-TRAIN.title` | [MechanicGlossary.cs:26](<../src/Volibear/Content/MechanicGlossary.cs#L26>) | 强化 |  |
| `static_hover_tips:VOLIBEAR-UNBREAKABLE.description` | [MechanicGlossary.cs:30](<../src/Volibear/Content/MechanicGlossary.cs#L30>) | 承受攻击后，格挡保持原值；超过格挡的伤害仍扣生命。不会改变回合开始的清除格挡或留甲规则。 | 承受攻击后，格挡保持原值；超过格挡的伤害仍扣生命。 |
| `static_hover_tips:VOLIBEAR-UNBREAKABLE.title` | [MechanicGlossary.cs:30](<../src/Volibear/Content/MechanicGlossary.cs#L30>) | 坚甲 |  |

## Mod 标识与依赖元数据

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `json:src/Volibear/Volibear.json:/dependencies/0/id` | [Volibear.json:10](<../src/Volibear/Volibear.json#L10>) | BaseLib |  |
| `json:src/Volibear/Volibear.json:/dependencies/0/min_version` | [Volibear.json:10](<../src/Volibear/Volibear.json#L10>) | 3.4.7 |  |
| `json:src/Volibear/Volibear.json:/id` | [Volibear.json:2](<../src/Volibear/Volibear.json#L2>) | Volibear |  |
| `json:src/Volibear/Volibear.json:/min_game_version` | [Volibear.json:7](<../src/Volibear/Volibear.json#L7>) | 0.107.1 |  |

## Mod 菜单

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `json:src/Volibear/Volibear.json:/author` | [Volibear.json:4](<../src/Volibear/Volibear.json#L4>) | fltb |  |
| `json:src/Volibear/Volibear.json:/description` | [Volibear.json:5](<../src/Volibear/Volibear.json#L5>) | 中文角色模组：89张卡牌、两件专属遗物，包含迎战、领域、雷伤与兽化机制。需要 BaseLib 3.4.7。 |  |
| `json:src/Volibear/Volibear.json:/name` | [Volibear.json:3](<../src/Volibear/Volibear.json#L3>) | 沃利贝尔 · 不灭狂雷 |  |
| `json:src/Volibear/Volibear.json:/version` | [Volibear.json:6](<../src/Volibear/Volibear.json#L6>) | 0.1.0 |  |

## 状态与能力

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `powers:BattleBodyPower.description` | [PersistentPowers.cs:259](<../src/Volibear/Core/PersistentPowers.cs#L259>) | 每张实际攻击结算后获得{Amount}力量；该牌曾提供正数格挡时，再获得{Amount}敏捷。 | 每张实际攻击结算后获得{Amount}力量；该牌曾提供正数格挡时，再获得{Amount}敏捷。 |
| `powers:BattleBodyPower.smartDescription` | [PersistentPowers.cs:260](<../src/Volibear/Core/PersistentPowers.cs#L260>) | 每张实际攻击结算后获得{Amount}力量；该牌曾提供正数格挡时，再获得{Amount}敏捷。重演共享一次实际出牌，被动雷甲不算本牌格挡。 |  |
| `powers:BattleBodyPower.title` | [PersistentPowers.cs:258](<../src/Volibear/Core/PersistentPowers.cs#L258>) | 愈战神躯 |  |
| `powers:BattleScarsPower.description` | [PersistentPowers.cs:113](<../src/Volibear/Core/PersistentPowers.cs#L113>) | 每回合首次完成迎战后，获得{Amount}力量和1雷势。每次部署独立计次。 |  |
| `powers:BattleScarsPower.smartDescription` | [PersistentPowers.cs:114](<../src/Volibear/Core/PersistentPowers.cs#L114>) | 每回合首次完成迎战后，获得{Amount}力量和1雷势。每次部署独立计次。 |  |
| `powers:BattleScarsPower.title` | [PersistentPowers.cs:112](<../src/Volibear/Core/PersistentPowers.cs#L112>) | 战痕 |  |
| `powers:BearSpiritPower.description` | [BeastPowers.cs:62](<../src/Volibear/Core/BeastPowers.cs#L62>) | 每回合首次兽化后抽{Amount}张牌；首次实际打出兽形时获得1雷势。正常起手抽牌及领域扣时后，可选兽化1张手牌。 |  |
| `powers:BearSpiritPower.smartDescription` | [BeastPowers.cs:63](<../src/Volibear/Core/BeastPowers.cs#L63>) | 每回合首次兽化后抽{Amount}张牌；首次实际打出兽形时获得1雷势。正常起手抽牌及领域扣时后，可选兽化1张手牌。各实例独立计次，重演不增加实际出牌次数。 |  |
| `powers:BearSpiritPower.title` | [BeastPowers.cs:61](<../src/Volibear/Core/BeastPowers.cs#L61>) | 熊灵侵染 |  |
| `powers:BiteMarkPower.description` | [PreparedEffects.cs:298](<../src/Volibear/Core/PreparedEffects.cs#L298>) | 暴怒撕咬对已有咬痕的目标追加伤害。 |  |
| `powers:BiteMarkPower.smartDescription` | [PreparedEffects.cs:298](<../src/Volibear/Core/PreparedEffects.cs#L298>) | 暴怒撕咬对已有咬痕的目标追加伤害。同一次实际出牌的重演读取施加前的咬痕。 |  |
| `powers:BiteMarkPower.title` | [PreparedEffects.cs:298](<../src/Volibear/Core/PreparedEffects.cs#L298>) | 咬痕 |  |
| `powers:DomainPower.description` | [DomainPower.cs:38](<../src/Volibear/Core/DomainPower.cs#L38>) | 你的领域剩余{Amount}轮。覆盖下次正常起手抽牌，抽完后扣1轮。你的每张攻击在领域内首段普通攻击后附加4＋当前雷势的全体雷伤，多段与重演共享一次机会。你实际抽到状态或诅咒时，净化消耗并补抽1张。压制敌方有利特殊效果，保留普通攻击、直接力量与格挡及必要清理。压制对全队生效；任一存活持有者仍有领域就继续，多人领域不重复叠加。 |  |
| `powers:DomainPower.permanentDescription` | [DomainPower.cs:40](<../src/Volibear/Core/DomainPower.cs#L40>) | 你的领域持续本战。你的每张攻击在领域内首段普通攻击后附加4＋当前雷势的全体雷伤，多段与重演共享一次机会。你实际抽到状态或诅咒时，净化消耗并补抽1张。压制敌方有利特殊效果，保留普通攻击、直接力量与格挡及必要清理。压制对全队生效；任一存活持有者仍有领域就继续，多人领域不重复叠加。 |  |
| `powers:DomainPower.smartDescription` | [DomainPower.cs:39](<../src/Volibear/Core/DomainPower.cs#L39>) | 你的领域剩余{Amount}轮。覆盖下次正常起手抽牌，抽完后扣1轮。你的每张攻击在领域内首段普通攻击后附加4＋当前雷势的全体雷伤，多段与重演共享一次机会。你实际抽到状态或诅咒时，净化消耗并补抽1张。压制敌方有利特殊效果，保留普通攻击、直接力量与格挡及必要清理。压制对全队生效；任一存活持有者仍有领域就继续，多人领域不重复叠加。 |  |
| `powers:DomainPower.title` | [DomainPower.cs:38](<../src/Volibear/Core/DomainPower.cs#L38>) | 领域 |  |
| `powers:EndlessHuntPower.description` | [HistoryEffects.cs:123](<../src/Volibear/Content/Cards/HistoryEffects.cs#L123>) | 每次实际打出单体攻击，使本回合对该目标的非X费攻击费用再降低{Amount}。 |  |
| `powers:EndlessHuntPower.smartDescription` | [HistoryEffects.cs:124](<../src/Volibear/Content/Cards/HistoryEffects.cs#L124>) | 每次实际打出单体攻击，使本回合对该目标的非X费攻击费用再降低{Amount}。实际出牌计一次，多段与重演不重复累计，每回合重新累计。 |  |
| `powers:EndlessHuntPower.title` | [HistoryEffects.cs:122](<../src/Volibear/Content/Cards/HistoryEffects.cs#L122>) | 不休之猎 |  |
| `powers:GrowingFuryPower.description` | [PersistentPowers.cs:182](<../src/Volibear/Core/PersistentPowers.cs#L182>) | 每回合第2张实际攻击支付后、牌效前，获得{Amount}力量和{Amount}雷势。 |  |
| `powers:GrowingFuryPower.smartDescription` | [PersistentPowers.cs:183](<../src/Volibear/Core/PersistentPowers.cs#L183>) | 每回合第2张实际攻击支付后、牌效前，获得{Amount}力量和{Amount}雷势。各部署独立计次，重演不另计实际出牌。 |  |
| `powers:GrowingFuryPower.title` | [PersistentPowers.cs:181](<../src/Volibear/Core/PersistentPowers.cs#L181>) | 愈战愈烈 |  |
| `powers:ImmovableBodyPower.description` | [PersistentPowers.cs:246](<../src/Volibear/Core/PersistentPowers.cs#L246>) | 承受攻击时不消耗格挡，溢出伤害仍扣生命。不会阻止回合开始的格挡清除。 |  |
| `powers:ImmovableBodyPower.smartDescription` | [PersistentPowers.cs:247](<../src/Volibear/Core/PersistentPowers.cs#L247>) | 承受攻击时不消耗格挡，溢出伤害仍扣生命。不会阻止回合开始的格挡清除。 |  |
| `powers:ImmovableBodyPower.title` | [PersistentPowers.cs:245](<../src/Volibear/Core/PersistentPowers.cs#L245>) | 坚甲 |  |
| `powers:LingeringStormPower.description` | [PersistentPowers.cs:127](<../src/Volibear/Core/PersistentPowers.cs#L127>) | 每次完成迎战后，抽1张牌并获得领域1。每次部署独立结算。 |  |
| `powers:LingeringStormPower.smartDescription` | [PersistentPowers.cs:128](<../src/Volibear/Core/PersistentPowers.cs#L128>) | 每次完成迎战后，先抽1张牌，再获得领域1。每次部署独立结算。 |  |
| `powers:LingeringStormPower.title` | [PersistentPowers.cs:126](<../src/Volibear/Core/PersistentPowers.cs#L126>) | 风暴不散 |  |
| `powers:NextAttackDiscount.description` | [PreparedEffects.cs:63](<../src/Volibear/Core/PreparedEffects.cs#L63>) | 本回合下一张实际打出的攻击减费{Amount}，最低0。 |  |
| `powers:NextAttackDiscount.smartDescription` | [PreparedEffects.cs:63](<../src/Volibear/Core/PreparedEffects.cs#L63>) | 本回合下一张实际打出的攻击减费{Amount}，最低0。同类待用减费取最大值，实际打出即消费。 |  |
| `powers:NextAttackDiscount.title` | [PreparedEffects.cs:63](<../src/Volibear/Core/PreparedEffects.cs#L63>) | 攻击减费 |  |
| `powers:NextAttackReplayPower.description` | [PreparedEffects.cs:91](<../src/Volibear/Core/PreparedEffects.cs#L91>) | 本回合下一张攻击额外结算{Amount}次完整效果。 |  |
| `powers:NextAttackReplayPower.smartDescription` | [PreparedEffects.cs:91](<../src/Volibear/Core/PreparedEffects.cs#L91>) | 本回合下一张攻击额外结算{Amount}次完整效果。重演不重复支付费用，不算重新打出。 |  |
| `powers:NextAttackReplayPower.title` | [PreparedEffects.cs:91](<../src/Volibear/Core/PreparedEffects.cs#L91>) | 暴风再临 |  |
| `powers:NextAttackTrainingPower.description` | [PreparedEffects.cs:118](<../src/Volibear/Core/PreparedEffects.cs#L118>) | 下一张实际打出的攻击本战每次伤害增加{Amount}。 |  |
| `powers:NextAttackTrainingPower.smartDescription` | [PreparedEffects.cs:118](<../src/Volibear/Core/PreparedEffects.cs#L118>) | 下一张实际打出的攻击本战每次伤害增加{Amount}。包括动态攻击与原生雷伤，复制继承，不改永久牌组。 |  |
| `powers:NextAttackTrainingPower.title` | [PreparedEffects.cs:118](<../src/Volibear/Core/PreparedEffects.cs#L118>) | 磨砺爪牙 |  |
| `powers:NextEngageDiscount.description` | [PreparedEffects.cs:77](<../src/Volibear/Core/PreparedEffects.cs#L77>) | 本回合下一张迎战牌减费1。 |  |
| `powers:NextEngageDiscount.smartDescription` | [PreparedEffects.cs:77](<../src/Volibear/Core/PreparedEffects.cs#L77>) | 本回合下一张迎战牌减费1。同类不叠加，实际打出即消费。 |  |
| `powers:NextEngageDiscount.title` | [PreparedEffects.cs:77](<../src/Volibear/Core/PreparedEffects.cs#L77>) | 迎战准备 |  |
| `powers:PreyStillStandsPower.description` | [PersistentPowers.cs:160](<../src/Volibear/Core/PersistentPowers.cs#L160>) | 每回合首次对同一目标打出第2张单体攻击后，抽{Amount}张牌，其中的攻击本回合减费1。 |  |
| `powers:PreyStillStandsPower.smartDescription` | [PersistentPowers.cs:161](<../src/Volibear/Core/PersistentPowers.cs#L161>) | 每回合首次对同一目标打出第2张单体攻击后，抽{Amount}张牌，其中的攻击本回合减费1。各部署独立计次，重演不另计实际出牌。 |  |
| `powers:PreyStillStandsPower.title` | [PersistentPowers.cs:159](<../src/Volibear/Core/PersistentPowers.cs#L159>) | 猎物未倒 |  |
| `powers:PrimalThunderPower.description` | [PreparedEffects.cs:146](<../src/Volibear/Core/PreparedEffects.cs#L146>) | 本轮每批雷伤增加{Amount}。 |  |
| `powers:PrimalThunderPower.smartDescription` | [PreparedEffects.cs:146](<../src/Volibear/Core/PreparedEffects.cs#L146>) | 本轮每批雷伤增加{Amount}。数值在打出时按当前正力量锁定，敌方阶段结束后失效。 |  |
| `powers:PrimalThunderPower.title` | [PreparedEffects.cs:146](<../src/Volibear/Core/PreparedEffects.cs#L146>) | 原始力量 |  |
| `powers:StandingPower.description` | [PersistentPowers.cs:87](<../src/Volibear/Core/PersistentPowers.cs#L87>) | 回合开始时，格挡只减少{Amount}。重复获得取较小损耗。 |  |
| `powers:StandingPower.smartDescription` | [PersistentPowers.cs:88](<../src/Volibear/Core/PersistentPowers.cs#L88>) | 回合开始时，格挡只减少{Amount}。重复获得取较小损耗；不是获得格挡，不受敏捷或脆弱影响。 |  |
| `powers:StandingPower.title` | [PersistentPowers.cs:86](<../src/Volibear/Core/PersistentPowers.cs#L86>) | 留甲 |  |
| `powers:StormChargePower.description` | [StormChargePower.cs:25](<../src/Volibear/Core/StormChargePower.cs#L25>) | 每段雷伤增加{Amount}。持续本战，不自动消耗。 |  |
| `powers:StormChargePower.smartDescription` | [StormChargePower.cs:26](<../src/Volibear/Core/StormChargePower.cs#L26>) | 每段雷伤增加{Amount}。持续本战，不自动消耗。 |  |
| `powers:StormChargePower.title` | [StormChargePower.cs:25](<../src/Volibear/Core/StormChargePower.cs#L25>) | 雷势 |  |
| `powers:StormConductionPower.description` | [PersistentPowers.cs:75](<../src/Volibear/Core/PersistentPowers.cs#L75>) | 每段普通攻击结算后，对全体造成{Amount}雷伤。每次部署独立结算。 |  |
| `powers:StormConductionPower.smartDescription` | [PersistentPowers.cs:76](<../src/Volibear/Core/PersistentPowers.cs#L76>) | 每段普通攻击结算后，对全体造成{Amount}雷伤。各部署独立结算，多段与重演逐段触发，全体一段只触发一次。 |  |
| `powers:StormConductionPower.title` | [PersistentPowers.cs:74](<../src/Volibear/Core/PersistentPowers.cs#L74>) | 狂雷渐起 |  |
| `powers:ThunderAftershockPower.description` | [PersistentPowers.cs:143](<../src/Volibear/Core/PersistentPowers.cs#L143>) | 本回合第2、4、6…次雷伤后获得1能量。部署时已有至少2次雷伤，立即获得1能量。 |  |
| `powers:ThunderAftershockPower.smartDescription` | [PersistentPowers.cs:144](<../src/Volibear/Core/PersistentPowers.cs#L144>) | 本回合第2、4、6…次雷伤后获得1能量。部署时已有至少2次雷伤，立即获得1能量。各部署独立响应，不补发历史次数。 |  |
| `powers:ThunderAftershockPower.title` | [PersistentPowers.cs:142](<../src/Volibear/Core/PersistentPowers.cs#L142>) | 雷霆余威 |  |
| `powers:ThunderArmorPower.description` | [PersistentPowers.cs:214](<../src/Volibear/Core/PersistentPowers.cs#L214>) | 每次雷伤后获得{Amount}格挡。每次部署独立结算。 |  |
| `powers:ThunderArmorPower.smartDescription` | [PersistentPowers.cs:215](<../src/Volibear/Core/PersistentPowers.cs#L215>) | 每次雷伤后获得{Amount}格挡。各部署独立结算，全体雷伤一批只触发一次，完全格挡的雷伤也触发。 |  |
| `powers:ThunderArmorPower.title` | [PersistentPowers.cs:213](<../src/Volibear/Core/PersistentPowers.cs#L213>) | 雷甲 |  |
| `powers:ThunderGuardPower.description` | [PreparedEffects.cs:161](<../src/Volibear/Core/PreparedEffects.cs#L161>) | 受到每段攻击后，对攻击者造成{Amount}雷伤。 |  |
| `powers:ThunderGuardPower.smartDescription` | [PreparedEffects.cs:161](<../src/Volibear/Core/PreparedEffects.cs#L161>) | 受到每段攻击后，对攻击者造成{Amount}雷伤。完全格挡也触发；双方仍可受伤且战斗未结束时结算。下次玩家回合开始失效。 |  |
| `powers:ThunderGuardPower.title` | [PreparedEffects.cs:161](<../src/Volibear/Core/PreparedEffects.cs#L161>) | 反雷 |  |
| `powers:ThunderPoolPower.description` | [PersistentPowers.cs:282](<../src/Volibear/Core/PersistentPowers.cs#L282>) | 回合结束及每回合首次完成迎战后，对全体造成{Amount}雷伤。每次部署独立结算。 |  |
| `powers:ThunderPoolPower.smartDescription` | [PersistentPowers.cs:283](<../src/Volibear/Core/PersistentPowers.cs#L283>) | 回合结束及每回合首次完成迎战后，对全体造成{Amount}雷伤。各部署独立结算，回合结束不会消费首次迎战机会。 |  |
| `powers:ThunderPoolPower.title` | [PersistentPowers.cs:281](<../src/Volibear/Core/PersistentPowers.cs#L281>) | 雷池 |  |
| `powers:UnifyPower.description` | [PreparedEffects.cs:135](<../src/Volibear/Core/PreparedEffects.cs#L135>) | 本战攻击与雷法的自身攻击、原生雷伤增加{Amount}。 |  |
| `powers:UnifyPower.smartDescription` | [PreparedEffects.cs:135](<../src/Volibear/Core/PreparedEffects.cs#L135>) | 本战攻击与雷法的自身攻击、原生雷伤增加{Amount}。不强化领域附雷或反雷。 |  |
| `powers:UnifyPower.title` | [PreparedEffects.cs:135](<../src/Volibear/Core/PreparedEffects.cs#L135>) | 天人合一 |  |
| `powers:WelcomeThunderPower.description` | [PersistentPowers.cs:199](<../src/Volibear/Core/PersistentPowers.cs#L199>) | 每回合首次完成迎战后，本回合下一张攻击减费{Amount}。每次部署独立计次。 |  |
| `powers:WelcomeThunderPower.smartDescription` | [PersistentPowers.cs:200](<../src/Volibear/Core/PersistentPowers.cs#L200>) | 每回合首次完成迎战后，本回合下一张攻击减费{Amount}。各部署独立计次，同类待用减费取最大值，不相加，使用后消费。 |  |
| `powers:WelcomeThunderPower.title` | [PersistentPowers.cs:198](<../src/Volibear/Core/PersistentPowers.cs#L198>) | 迎雷 |  |
| `powers:WildernessPower.description` | [BeastPowers.cs:127](<../src/Volibear/Core/BeastPowers.cs#L127>) | 每回合首次实际打出爪形时，获得{Amount}格挡；每次实际打出躯形时，获得1能量。 |  |
| `powers:WildernessPower.smartDescription` | [BeastPowers.cs:128](<../src/Volibear/Core/BeastPowers.cs#L128>) | 每回合首次实际打出爪形时，获得{Amount}格挡；每次实际打出躯形时，获得1能量。各实例独立计次，重演不增加实际出牌次数。 |  |
| `powers:WildernessPower.title` | [BeastPowers.cs:126](<../src/Volibear/Core/BeastPowers.cs#L126>) | 我即荒野 |  |

## 遗物

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `relics:HUNTERS_HEART.description` | [VolibearLoc.cs:48](<../src/Volibear/Content/VolibearLoc.cs#L48>) | 每回合首次完成迎战后，抽1张牌。 |  |
| `relics:HUNTERS_HEART.flavor` | [VolibearLoc.cs:49](<../src/Volibear/Content/VolibearLoc.cs#L49>) | 雷霆不会熄灭。 |  |
| `relics:HUNTERS_HEART.title` | [VolibearLoc.cs:47](<../src/Volibear/Content/VolibearLoc.cs#L47>) | 不灭狂雷 |  |
| `relics:SEA_GLASS.VOLIBEAR_CHARACTER.title` | [VolibearLoc.cs:53](<../src/Volibear/Content/VolibearLoc.cs#L53>) | 风暴海玻璃 |  |
| `relics:VOLIBEAR_HUNTERS_HEART.description` | [VolibearLoc.cs:51](<../src/Volibear/Content/VolibearLoc.cs#L51>) | 每回合首次完成迎战后，抽1张牌。 |  |
| `relics:VOLIBEAR_HUNTERS_HEART.flavor` | [VolibearLoc.cs:52](<../src/Volibear/Content/VolibearLoc.cs#L52>) | 雷霆不会熄灭。 |  |
| `relics:VOLIBEAR_HUNTERS_HEART.title` | [VolibearLoc.cs:50](<../src/Volibear/Content/VolibearLoc.cs#L50>) | 不灭狂雷 |  |
| `relics:VOLIBEAR_IMMORTAL_HEART.description` | [ImmortalHeart.cs:32](<../src/Volibear/Content/ImmortalHeart.cs#L32>) | 每回合首次完成迎战后，抽2张牌。 |  |
| `relics:VOLIBEAR_IMMORTAL_HEART.flavor` | [ImmortalHeart.cs:32](<../src/Volibear/Content/ImmortalHeart.cs#L32>) | 风暴不会遗忘，雷霆永不止息。 |  |
| `relics:VOLIBEAR_IMMORTAL_HEART.title` | [ImmortalHeart.cs:32](<../src/Volibear/Content/ImmortalHeart.cs#L32>) | 万古不灭 |  |

## 文本引用（匹配/悬停入口）

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `literal:src/Volibear/Content/Cards/BeastTokens.cs:Volibear_T01:1` | [BeastTokens.cs:24](<../src/Volibear/Content/Cards/BeastTokens.cs#L24>) | 兽形 |  |
| `literal:src/Volibear/Content/Cards/BeastTokens.cs:Volibear_T02:1` | [BeastTokens.cs:39](<../src/Volibear/Content/Cards/BeastTokens.cs#L39>) | 兽形 |  |
| `literal:src/Volibear/Content/ImmortalHeart.cs:ImmortalHeart:1` | [ImmortalHeart.cs:30](<../src/Volibear/Content/ImmortalHeart.cs#L30>) | 迎战 |  |
| `literal:src/Volibear/Content/MechanicHoverTips.cs:MechanicHoverTips:1` | [MechanicHoverTips.cs:26](<../src/Volibear/Content/MechanicHoverTips.cs#L26>) | 迎战 |  |
| `literal:src/Volibear/Content/VolibearRelicPool.cs:HuntersHeart:1` | [VolibearRelicPool.cs:35](<../src/Volibear/Content/VolibearRelicPool.cs#L35>) | 迎战 |  |

## UI 与动态信息

| 稳定 ID | 来源 | 原文 | 修改 |
| --- | --- | --- | --- |
| `static_hover_tips:VOLIBEAR-ENGAGE_STATE.empty` | [MechanicGlossary.cs:54](<../src/Volibear/Content/MechanicGlossary.cs#L54>) | 当前没有存活敌人用过本轮行动。行动机会由全队共享。 |  |
| `static_hover_tips:VOLIBEAR-ENGAGE_STATE.spent` | [MechanicGlossary.cs:55](<../src/Volibear/Content/MechanicGlossary.cs#L55>) | 本轮行动机会已用：{Enemies}。这些敌人本轮不能再次迎战；卡牌的其他效果仍按牌面结算。 |  |
| `static_hover_tips:VOLIBEAR-ENGAGE_STATE.title` | [MechanicGlossary.cs:53](<../src/Volibear/Content/MechanicGlossary.cs#L53>) | 本轮迎战信息 |  |
| `ui:src/Volibear/Presentation/volibear_energy.tscn:text:1` | [volibear_energy.tscn:94](<../src/Volibear/Presentation/volibear_energy.tscn#L94>) | 3/3 |  |

## 来源清单与快照摘要

每个扫描文件均列出 SHA-256；0 行表示没有新增可审核文本（包括诊断/探针及资源引用）。文本行数含基础/升级重复字段。

| 来源 | 审核字段数 | SHA-256 |
| --- | ---: | --- |
| [ApiProbe.cs](<../src/Volibear/ApiProbe.cs>) | 0 | `26a47810daad6af51e139ecf73a464bae8393b1a69247adfc9eac778e0440b71` |
| [AudioReceiptProbe.cs](<../src/Volibear/AudioReceiptProbe.cs>) | 0 | `caa6b487d06123eed20781b22209eb4a4030b62a191c153add282efd02d100e7` |
| [AudioReceiptProbeObservers.cs](<../src/Volibear/AudioReceiptProbeObservers.cs>) | 0 | `3a4d0c40a5f861fd851e4663d65fcc6becc26d536e5b5eabc5a03c979594526a` |
| [BaselineDriver.cs](<../src/Volibear/BaselineDriver.cs>) | 0 | `8c13951c1eeb0c34f6228bbd2e2d6deec4db7580acc19612b725ed25de0baaac` |
| [BeastContractProbe.cs](<../src/Volibear/BeastContractProbe.cs>) | 0 | `26d2cce4528f10f372898c3a914f2d6c12d77b55cebb8dafbc3e35f04392e076` |
| [CardCatalogProbe.cs](<../src/Volibear/CardCatalogProbe.cs>) | 0 | `1de5420536128220ac2b6022f3aafc1a92f1a4a7f4c8c29af4340c65734b6911` |
| [CardFaceAcceptanceProbe.cs](<../src/Volibear/CardFaceAcceptanceProbe.cs>) | 0 | `4bca0ccfe106c86d5b6d3c96772b4323d4e8f31861d68f1a7152724b2d32ad1c` |
| [CardLifecycleAcceptanceProbe.cs](<../src/Volibear/CardLifecycleAcceptanceProbe.cs>) | 0 | `d661b8587f21b0f6f04489c4bab37627e8f46e2bfebf90961424c703f2309120` |
| [CardPassiveContractProbe.cs](<../src/Volibear/CardPassiveContractProbe.cs>) | 0 | `375c3d399b45675d1bc3df9739e78f40f40f2b5a600f54eb1ba2ecaffb5cb6a0` |
| [CharacterIntegrationProbe.cs](<../src/Volibear/CharacterIntegrationProbe.cs>) | 0 | `c49d6200d03a06ae1b4a18b14a88395de382d8a7e5568f3f218e64e4a1b34d8b` |
| [CardCapabilities.cs](<../src/Volibear/Content/CardCapabilities.cs>) | 0 | `a70c11b9a4d996a8a450fbf983cbb64fbad31697d1d9c35884aafcf9e2a6c586` |
| [Basic.cs](<../src/Volibear/Content/Cards/Basic.cs>) | 0 | `c24beb170375f9127637ecaf4e04c354f98b0e71f04d595a39562cc2a1ae7963` |
| [Basic2.cs](<../src/Volibear/Content/Cards/Basic2.cs>) | 0 | `aa23238e2dc876fdc859d64c36df8e3648b1366564031d4809af55d8b08aa6cb` |
| [BeastEffects.cs](<../src/Volibear/Content/Cards/BeastEffects.cs>) | 35 | `1ccdcbb0427307a633f85fcdc8d676712743db1babad47f0ae13275bb297157c` |
| [BeastTokens.cs](<../src/Volibear/Content/Cards/BeastTokens.cs>) | 10 | `8c4a9d7327d720458f1fa06bb9dd2a7a0bd6b035853744ba349f58b3cd263f31` |
| [ControlledEffects.cs](<../src/Volibear/Content/Cards/ControlledEffects.cs>) | 69 | `6053ebb436688bd307485e7a05dbed983252d2dcb380108f902cdcb380e8d49d` |
| [DirectEffects.Lifecycle.cs](<../src/Volibear/Content/Cards/DirectEffects.Lifecycle.cs>) | 0 | `53c0b701b0411c01102cba762feb67f8ff7faf1fda1ac9748685f42a4693c114` |
| [DirectEffects.cs](<../src/Volibear/Content/Cards/DirectEffects.cs>) | 132 | `c43b2036f702e023c01ba6e241476bb8e584af938f4ecb9208715fb85adf2cc6` |
| [HistoryEffects.cs](<../src/Volibear/Content/Cards/HistoryEffects.cs>) | 23 | `23fdc848ab45f9b0c642f6cffed6b893311333a496d8c883118e1fc1be97c175` |
| [PersistentEffects.cs](<../src/Volibear/Content/Cards/PersistentEffects.cs>) | 48 | `80dd8a24b46b734a7295377e23b546e99010fa3d5b1465d264615dc318eca606` |
| [PreparedEffects.cs](<../src/Volibear/Content/Cards/PreparedEffects.cs>) | 42 | `272b6f7e37c96e0b4d208fe11b117d4c73416d37d75420fdcd2f04fb6a2c9634` |
| [ContentRegistry.cs](<../src/Volibear/Content/ContentRegistry.cs>) | 0 | `4e54f5b7458f7dddeb2d9494635cf0719cce4e8fee697f50dff9f04f9506f7e9` |
| [ImmortalHeart.cs](<../src/Volibear/Content/ImmortalHeart.cs>) | 4 | `2c014b574fcccfc26c411000eb25ae6411c5e2f112a47a44f6ed21437589e92e` |
| [InlineModelLocalization.cs](<../src/Volibear/Content/InlineModelLocalization.cs>) | 0 | `4d0ce42698ad478bfbddd44ff6d15b753e7bf2f4d553eca5b746df659e67ea74` |
| [LightningCmd.cs](<../src/Volibear/Content/LightningCmd.cs>) | 0 | `594fc2075f03ec01593835360a99f3d307d571448bd63ed1944ecc76ee860977` |
| [MechanicGlossary.cs](<../src/Volibear/Content/MechanicGlossary.cs>) | 71 | `4d6740c7a7ccc161df85e6a27e76fec75de21438efdf5c253a100d19ae3c128d` |
| [MechanicHoverTips.cs](<../src/Volibear/Content/MechanicHoverTips.cs>) | 1 | `b207ab5d5a283cef6be8f5a23963f4049fd2820dd404c346c5403402d93e5352` |
| [VolibearAssetBridge.cs](<../src/Volibear/Content/VolibearAssetBridge.cs>) | 0 | `3fced660eb28c87d0928f15e20bcdcbcb2534520e278b86d31bd4386ec1b808b` |
| [VolibearAssets.cs](<../src/Volibear/Content/VolibearAssets.cs>) | 0 | `80e2d206bc8624b7f71bea4ae2bffcbdc311e7d14f2de71babd332f4d183d80f` |
| [VolibearCard.cs](<../src/Volibear/Content/VolibearCard.cs>) | 0 | `f9dac07a0c1cabeec062bfc029a52bb36fdf06d92ab6a0b23b42d0a6a23c4274` |
| [VolibearCardPool.cs](<../src/Volibear/Content/VolibearCardPool.cs>) | 1 | `62e109706f5eade35a91f32b24b02f44029b5d2f8a19f8b61bb0a1d64cb8acde` |
| [VolibearCharacter.cs](<../src/Volibear/Content/VolibearCharacter.cs>) | 0 | `1efb6e9ab8a4a1b8aae031f9829f14927a48b75b0a477f2ae10c3b39912caa0b` |
| [VolibearLoc.cs](<../src/Volibear/Content/VolibearLoc.cs>) | 40 | `cd0cff9b50425030432215dca207cac4aca695532481a96252c4ff607ebe77fe` |
| [VolibearPortraits.cs](<../src/Volibear/Content/VolibearPortraits.cs>) | 0 | `ed3f4287344026dc2b6a12cde91606ecbeda237fa50956e0a5c65dcbd2489aee` |
| [VolibearRelicPool.cs](<../src/Volibear/Content/VolibearRelicPool.cs>) | 1 | `9cd676bf6a4fe27d99d88a70c178a2e430bbdf70fe63990d8e09a0395181e11c` |
| [ContentProbe.cs](<../src/Volibear/ContentProbe.cs>) | 0 | `0f79713915bd77406f4c17c081aba58b738df4baaa583a92555a59e64e6f8a69` |
| [AttackHistory.cs](<../src/Volibear/Core/AttackHistory.cs>) | 0 | `eea4d8094c346a8ef278ddb7c74215849d3b153110bedfa16dd3367434602335` |
| [BeastForms.cs](<../src/Volibear/Core/BeastForms.cs>) | 0 | `ea64facaea0439c5b3ffcbf389b47b144a5ad5af3a184e10771f99f110a17818` |
| [BeastFormsCost.cs](<../src/Volibear/Core/BeastFormsCost.cs>) | 0 | `77aab7290bbad5787fcab11b72351e207de9400082b3a1143e68ccd8343b2a2b` |
| [BeastFormsNativeCosts.cs](<../src/Volibear/Core/BeastFormsNativeCosts.cs>) | 0 | `e35afbc00600a954bbd2dfd18d4cac88d9b77e31b4b8dee6eb4d18c56219fb91` |
| [BeastPowers.cs](<../src/Volibear/Core/BeastPowers.cs>) | 6 | `fb9979ac78450d01d08a26086ca0b75b04e135c485988f135e9a00ce68c82ac0` |
| [CardPresentationReceipts.cs](<../src/Volibear/Core/CardPresentationReceipts.cs>) | 0 | `83c96d10741aca65ba1b34f755c40431ec09fc8a5ce1adfb41fa11897dd4ddae` |
| [CardReceiptPolicy.cs](<../src/Volibear/Core/CardReceiptPolicy.cs>) | 0 | `c6bb821dea9e4484ecdbc1107b002c38cdca5e381c9bbe07a70924a23494a784` |
| [CardResolutionDrawHooks.cs](<../src/Volibear/Core/CardResolutionDrawHooks.cs>) | 0 | `5e49b61978dd454f8a80cc78fb54b0c392487b46b3ec5e1640beb1b8204ab9d7` |
| [CardResolutionHooks.cs](<../src/Volibear/Core/CardResolutionHooks.cs>) | 0 | `14cc8b6e68df91a9bf727d5b76a245f2a08644953365ef1d39aef4be36de50a5` |
| [CardResolutionState.cs](<../src/Volibear/Core/CardResolutionState.cs>) | 0 | `c59ad863c4adfc5b7cab0b10f82753958fa0a43a2a1c2fd11bd6bfcd0941c06f` |
| [CostPresentationReceipts.cs](<../src/Volibear/Core/CostPresentationReceipts.cs>) | 0 | `3a145f748efa50075e83b84f3f0275e7960a09d1275fb3e3167a18e90a1226e7` |
| [DampenLifetime.cs](<../src/Volibear/Core/DampenLifetime.cs>) | 0 | `b33369fffcbb7d9ffa358d48514a3907cad2c2665dc93ab3cb11922a39594268` |
| [DomainAdditionalRevivalEffects.Hatch.cs](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Hatch.cs>) | 0 | `de069273970ade196dfd0bc6a3dbbee3df7789085728681964b5fb610b3e30fd` |
| [DomainAdditionalRevivalEffects.Patches.cs](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Patches.cs>) | 0 | `fe7ed2f98683789e35b54c6109824f74b0720b1555a2891d54c0cbb49680cc20` |
| [DomainAdditionalRevivalEffects.Votes.cs](<../src/Volibear/Core/DomainAdditionalRevivalEffects.Votes.cs>) | 0 | `0acdc3d8b7cc33634d5ce335569a9c601a2ea68cbd97727785a8ad8ba9bc5a7e` |
| [DomainAdditionalRevivalEffects.cs](<../src/Volibear/Core/DomainAdditionalRevivalEffects.cs>) | 0 | `9dac9d750dad910ddd472b4671dd452de7dd236e76e8f7662f364de8c7c34371` |
| [DomainCardContributionLedger.cs](<../src/Volibear/Core/DomainCardContributionLedger.cs>) | 0 | `5daf189a4b505d24e41673bc0bcc49320e630dea978fbd03ede129feaf662bbc` |
| [DomainCardContributions.cs](<../src/Volibear/Core/DomainCardContributions.cs>) | 0 | `c40905871776567e3e7d5e7e307d57cb05bf57f716921fb066caa1ab716dd325` |
| [DomainDampenTransactions.cs](<../src/Volibear/Core/DomainDampenTransactions.cs>) | 0 | `4e91b5f78f9765ba3370d732804ee3e661f9233e8bdef523a61425f75a59e043` |
| [DomainEnemyEffects.cs](<../src/Volibear/Core/DomainEnemyEffects.cs>) | 0 | `967cd70de7eb615a99a6da17e113dccafdbd8be4656e01860b1511dcf8b241f4` |
| [DomainEnemySpecialContributions.Surprise.cs](<../src/Volibear/Core/DomainEnemySpecialContributions.Surprise.cs>) | 0 | `1560dbe4f9b07321004050aa13eb0001ad84e6bdef34034dd22c6f214e07c2d1` |
| [DomainEnemySpecialContributions.cs](<../src/Volibear/Core/DomainEnemySpecialContributions.cs>) | 0 | `b89a9d55531fecf6dd636728672cabd53c4f4474470a6fb4dda2a3a79fc6e7f2` |
| [DomainEnemyStatusContributions.PowerEffects.cs](<../src/Volibear/Core/DomainEnemyStatusContributions.PowerEffects.cs>) | 0 | `d5d01a91331ec690fb0100aebe91f38ef3a82710feb23ff92e016cb4dfe2490f` |
| [DomainEnemyStatusContributions.Wither.cs](<../src/Volibear/Core/DomainEnemyStatusContributions.Wither.cs>) | 0 | `b620097a35be24547342fd2ef30bf4c835c85220467343bf5ba3bd09907b9475` |
| [DomainEnemyStatusContributions.cs](<../src/Volibear/Core/DomainEnemyStatusContributions.cs>) | 0 | `b0a31928137af4d7d83359d52ae0b21cdca45bb6ab331a49c8c3b82b7b68a59b` |
| [DomainHopperDecision.cs](<../src/Volibear/Core/DomainHopperDecision.cs>) | 0 | `2045f361e3afb0d62b4ecc64f2c19660fd7a0a3101b25b8abd1f9673235cfbba` |
| [DomainHopperEffects.Patches.cs](<../src/Volibear/Core/DomainHopperEffects.Patches.cs>) | 0 | `19d9e1c0b31df273132561bafc2a49d00ced89184e4315e91934e4b264fc29e7` |
| [DomainHopperEffects.cs](<../src/Volibear/Core/DomainHopperEffects.cs>) | 0 | `af07e98369a21e999cc811808fffeff5495ae2f2f72962f7978b8394b0495b7b` |
| [DomainPassiveEffects.cs](<../src/Volibear/Core/DomainPassiveEffects.cs>) | 0 | `1ff8c6ba1d1fa2aac11a20312a0cba6ad70565e95ca69a79271057420052a306` |
| [DomainPlayerDebuffContributions.CommitGates.cs](<../src/Volibear/Core/DomainPlayerDebuffContributions.CommitGates.cs>) | 0 | `3fff4acc3b677e154fb83e3169c41382051275a37051807317ccb85f3c8dfb9b` |
| [DomainPlayerDebuffContributions.NullSource.cs](<../src/Volibear/Core/DomainPlayerDebuffContributions.NullSource.cs>) | 0 | `12527da268c796a3d4f91d1aef20064baa757664de9194e358803e21a52d08d8` |
| [DomainPlayerDebuffContributions.Patches.cs](<../src/Volibear/Core/DomainPlayerDebuffContributions.Patches.cs>) | 0 | `c65690a55f35cf715b1416895a509db1965920299e1f572ad3cc903b25e42ee4` |
| [DomainPlayerDebuffContributions.cs](<../src/Volibear/Core/DomainPlayerDebuffContributions.cs>) | 0 | `372d06f83c5f0780c33a30b429460f58eed8a69b1ebfbb02b9d0ce52f1fc82e2` |
| [DomainPlayerStatContributions.Possess.cs](<../src/Volibear/Core/DomainPlayerStatContributions.Possess.cs>) | 0 | `883e69f1650b5a97b5d29217a0e9ee485b201afafd980eb61361026fceee8a4f` |
| [DomainPlayerStatContributions.Tender.cs](<../src/Volibear/Core/DomainPlayerStatContributions.Tender.cs>) | 0 | `6609ac3f4e83ef7ba1110ef4544d6ee6f71f689ed99d013c36d29478c0a3edb4` |
| [DomainPlayerStatContributions.cs](<../src/Volibear/Core/DomainPlayerStatContributions.cs>) | 0 | `3526442044bb47f843da5fb590bd8b67f39418d691b7294eea3baae6a67b3b28` |
| [DomainPower.cs](<../src/Volibear/Core/DomainPower.cs>) | 4 | `61160874b2f60e96a14e6c92df5dc2f298d81c27bb9c1cd2eef19b9fdb59b03e` |
| [DomainRevivalEffects.cs](<../src/Volibear/Core/DomainRevivalEffects.cs>) | 0 | `a56766b7038d7550afdf0462073e6deb5c80042356dd62a26cc4fb2ca2dde869` |
| [DomainSandpitEffects.cs](<../src/Volibear/Core/DomainSandpitEffects.cs>) | 0 | `b20df93830d9c3a4086f5bd515c3fd6c69cef402d04969c1ecacb09a2c7a0960` |
| [DomainSteamEruptionEffects.Damage.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.Damage.cs>) | 0 | `59186e8c301b79abe12ded076c4526ed739b8e2ae419bfe448a7d09db707fbe2` |
| [DomainSteamEruptionEffects.HpObservation.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.HpObservation.cs>) | 0 | `633393d551b9487b9e3ff98f92e7965eb1189fcfff9172ed6108a738c72a5516` |
| [DomainSteamEruptionEffects.Install.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.Install.cs>) | 0 | `c31da2e4661d8f8401194cfeb54711255d2de4e54ddcd3d10b6b924ec1382ec4` |
| [DomainSteamEruptionEffects.Lifecycle.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.Lifecycle.cs>) | 0 | `dfcf85abf74d6d68e34ab2abf3754348fa6857e486f96a5d61dcd7dc451ed4f5` |
| [DomainSteamEruptionEffects.Observation.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.Observation.cs>) | 0 | `323bdbae25c18705f4ef992135b0002ecb6697858e31926cf060145bc5585383` |
| [DomainSteamEruptionEffects.Phase.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.Phase.cs>) | 0 | `bc9efccd22dcfb1b009702736ecd928d2d08f006d94f2bc2aa7f7c75245eb661` |
| [DomainSteamEruptionEffects.Scopes.cs](<../src/Volibear/Core/DomainSteamEruptionEffects.Scopes.cs>) | 0 | `0cc3761dfcb418bcf68c00a42786bbf923783f9ad4e099b9ec43e355d2a042bb` |
| [DomainSummonDecision.cs](<../src/Volibear/Core/DomainSummonDecision.cs>) | 0 | `7baba7bd117c8b3bf7fc3e574371137ad24b9fe9ce30833b689c960f6880d5f4` |
| [DomainSummonEffects.Additional.cs](<../src/Volibear/Core/DomainSummonEffects.Additional.cs>) | 0 | `59a641842770f48a418ee1800f07a0ec29ac0d5b3c15b0d8236520b6c50749f1` |
| [DomainSummonEffects.cs](<../src/Volibear/Core/DomainSummonEffects.cs>) | 0 | `2ba9c2c54b8346745799071e5735d0f30dd18dd8933e6781b0cb59c723321d58` |
| [EngageCmd.cs](<../src/Volibear/Core/EngageCmd.cs>) | 0 | `4fe078a53f58dc81506ac6afb9e60e16163b772242ee810f6cc0177d05298932` |
| [EngageOpportunityLedger.cs](<../src/Volibear/Core/EngageOpportunityLedger.cs>) | 0 | `8e4d3b974d2d8b6341959da015a0f63c67856cdfbe491de25b9e7a57fbcd8a7a` |
| [GameplayPresentationReceipts.cs](<../src/Volibear/Core/GameplayPresentationReceipts.cs>) | 0 | `2c06c292a9792d8cb55c0efc85ba90d388e33c2c77a3192fa2bdecefb5382def` |
| [IOrdinarySegmentResponder.cs](<../src/Volibear/Core/IOrdinarySegmentResponder.cs>) | 0 | `9b0395797fda0b731c98b17ebd34c697bd32ade770f82ab7ce2a330e0e6aae35` |
| [LightningBatches.cs](<../src/Volibear/Core/LightningBatches.cs>) | 0 | `fe6783b9d75a9449544549f7903ffacb2be35f2e3dc6ce538e2b3c0703f99701` |
| [LightningCounter.cs](<../src/Volibear/Core/LightningCounter.cs>) | 0 | `a5cdf0e92938a8e55e91913a9776a7e079ec58da9b86cd94a96b57702ee17fe1` |
| [LightningResponseDispatch.cs](<../src/Volibear/Core/LightningResponseDispatch.cs>) | 0 | `404eb8a21c0385fa7daa5c886770224297f7bf86bc2dfd27f28722f03d3556ad` |
| [PersistentPowers.cs](<../src/Volibear/Core/PersistentPowers.cs>) | 36 | `9a3f686532855d6e42bb4700fa350dff2106577192da28b466b7abf18ec92d72` |
| [PreparedEffects.cs](<../src/Volibear/Core/PreparedEffects.cs>) | 24 | `95f7c6512e2f4085b6a1f5a812a39f8a3708a5f4b126dda60e54e20232c091d7` |
| [RevivalDecision.cs](<../src/Volibear/Core/RevivalDecision.cs>) | 0 | `0bff6bac29604bc038da16ef7e83460890e5df1e1ffc677182bec3008f04c068` |
| [ScryPresentationScope.cs](<../src/Volibear/Core/ScryPresentationScope.cs>) | 0 | `c3d5587fdd83b8ffc9f66e068093d5216f06c684ee5f2ea53bb6be3bdfa79d9d` |
| [SteamEruptionDecision.cs](<../src/Volibear/Core/SteamEruptionDecision.cs>) | 0 | `69dcd4cee0bd32cc6c2b0cd84a10ec7069f78717a73374d1fecf36b4a09c4c2e` |
| [SteamNativeEntryBinding.cs](<../src/Volibear/Core/SteamNativeEntryBinding.cs>) | 0 | `97c9b3f4f3448028fc7c9c3993cad8a16e70baf5866740d1ce0b2cf61b9799e4` |
| [StormChargePower.cs](<../src/Volibear/Core/StormChargePower.cs>) | 3 | `6d5c1748143d09df88b2b80afbd585af49d2bc74dc327ab6db07f5c63b0096f1` |
| [SummonRegistration.cs](<../src/Volibear/Core/SummonRegistration.cs>) | 0 | `b93d4b43760d3d34a65548d828685e0e1288f70366095ccb05805ea034d352b3` |
| [SupportedGameBuild.cs](<../src/Volibear/Core/SupportedGameBuild.cs>) | 0 | `33c344638a652e6fbed97e5e7f3d5afee966862af99270e414230e0637cc56e9` |
| [TargetCosts.cs](<../src/Volibear/Core/TargetCosts.cs>) | 0 | `94867eba73106040530af55b74d6967b0b4436d2a78707a38bb30337d55b4651` |
| [CouponContractProbe.cs](<../src/Volibear/CouponContractProbe.cs>) | 0 | `1806790731ee2736b8601fb7188321473c6f2636f60b85f6e52f8ab367df3a57` |
| [DevelopmentBootstrap.cs](<../src/Volibear/DevelopmentBootstrap.cs>) | 0 | `71932db457782d7b5bb743eba22c656674a4a641d64a91253e317ee84a20bede` |
| [DomainCardContributionsProbe.cs](<../src/Volibear/DomainCardContributionsProbe.cs>) | 0 | `776117def2cd6b00ac35e1a1a6f898263eab0954e2eaaec17422e040ff7af7ad` |
| [DomainContractProbe.cs](<../src/Volibear/DomainContractProbe.cs>) | 0 | `4cb8bda32755448cc670d65e3ac9bed576a793d339aba178ee193ec287702854` |
| [DomainDampenTransactionsProbe.cs](<../src/Volibear/DomainDampenTransactionsProbe.cs>) | 0 | `1d17b0ca1e4f81a80cb61b961e41252f83e526391981777653109f7fdf374fa4` |
| [DomainEnemyContractProbe.cs](<../src/Volibear/DomainEnemyContractProbe.cs>) | 0 | `d03735e2ad050b967f66e532c8ff87db72d1750088ccb83cd78395333a8b736f` |
| [DomainHopperProbe.cs](<../src/Volibear/DomainHopperProbe.cs>) | 0 | `fd44b8d3bfb17a95e84b9755a3bcbdd3b7338b627478eb717b13ff9c7b0d04aa` |
| [DomainRevivalProbe.cs](<../src/Volibear/DomainRevivalProbe.cs>) | 0 | `540cfe7541be2b40142c89b40db5180e721c74cb1b488b15ae8790bdd2319296` |
| [DomainSteamEruptionProbe.cs](<../src/Volibear/DomainSteamEruptionProbe.cs>) | 0 | `e22b6b80af318fb6fad831ecf3a6f90d4b1fe6c37e9ea36662778b9ddd786788` |
| [DomainSteamForeignFixture.cs](<../src/Volibear/DomainSteamForeignFixture.cs>) | 0 | `ee7b1f257248d646ba112c27bc55612c209084c543d52e94f74bedbd85c465e6` |
| [DomainSteamNativeObservation.History.cs](<../src/Volibear/DomainSteamNativeObservation.History.cs>) | 0 | `f73365343b4b50b525bfea441691bc2988990402ea237acb402f8066867b6f38` |
| [DomainSteamNativeObservation.Stages.cs](<../src/Volibear/DomainSteamNativeObservation.Stages.cs>) | 0 | `17546e96a95923974180951c564e26b4ef48981637128e6b89a478e11a84aab6` |
| [DomainSteamNativeObservation.cs](<../src/Volibear/DomainSteamNativeObservation.cs>) | 0 | `7202af5e1c5bde8b9d65a75671b2e11d9c28311711bddbc1c98011752d6b59d0` |
| [DomainSummonContractProbe.cs](<../src/Volibear/DomainSummonContractProbe.cs>) | 0 | `e6ee009eb823722e3afa0a072782157038d209f6dbbb005694fecec2a51257e8` |
| [DomainSummonD17Probe.cs](<../src/Volibear/DomainSummonD17Probe.cs>) | 0 | `352ae75d7804ba43fcf718ef94a4c0e3e50c1f5cb615b233f98095ef85de525f` |
| [EnemyCatalogProbe.cs](<../src/Volibear/EnemyCatalogProbe.cs>) | 0 | `9eac8e63a5b6fc1618ba3f2ee3a5bf060233948f68a89f19f7238bb83805a8a6` |
| [EnemyExplorationProbe.cs](<../src/Volibear/EnemyExplorationProbe.cs>) | 0 | `03765b7a0f3b9ffdea2bcce955175a7d19f1776da2f636f97be2be40161e324c` |
| [EnemyMatrixProbe.cs](<../src/Volibear/EnemyMatrixProbe.cs>) | 0 | `0a4cc20ac6457d56501f2ae9dcd41b9a26e586551980bffe61c8d07042551e9c` |
| [EngageCardProbe.cs](<../src/Volibear/EngageCardProbe.cs>) | 0 | `386a0d0442f0ef8153860eebc32ad53be6bd621ffeb2fdbc8f652aa011b570e8` |
| [EngageContractProbe.cs](<../src/Volibear/EngageContractProbe.cs>) | 0 | `e7a7f955502d6315d58af522f7f0f22126b849452e4c25159588685aeeba5fa9` |
| [EngagePrototype.cs](<../src/Volibear/EngagePrototype.cs>) | 0 | `e0378f6eb49a10c5fbe962b8dac3d03396e409d6690b29559eae78ff887529cb` |
| [GlobalAliases.cs](<../src/Volibear/GlobalAliases.cs>) | 0 | `879cc10f895e503881e37771cb7b1cb3a26e05b74394ac02cc09ecc707eef99a` |
| [InitialPlatingContractProbe.cs](<../src/Volibear/InitialPlatingContractProbe.cs>) | 0 | `0f32adb0c7900fe1326fff3ed8277aad054b1835b16eab095cfe74f986fbd054` |
| [ManualPlayProbe.cs](<../src/Volibear/ManualPlayProbe.cs>) | 0 | `718f59e91467294c0f3ef97f56e5b6860026de3e554be420cf6d0c71e26b3f74` |
| [ModEntry.cs](<../src/Volibear/ModEntry.cs>) | 0 | `f3ee2757059b4dec4a11a447fdf40d84c97bd9b7a50218606fd8e8adfd5b1e31` |
| [MultiplayerAcceptanceProbe.cs](<../src/Volibear/MultiplayerAcceptanceProbe.cs>) | 0 | `452d5c9941c925fb429ba7bf050ef22bf4f4dd50ada55c5ac97c7d35b7435d86` |
| [NativeAcceptanceRunHost.cs](<../src/Volibear/NativeAcceptanceRunHost.cs>) | 0 | `9b9bf01fd87cc65d5cb1ad8ac530f25d04f3cfc7f3a74e77867bcfc59cf37878` |
| [NativeAutomationSelector.cs](<../src/Volibear/NativeAutomationSelector.cs>) | 0 | `890ac30ddc370a6c1caf971e76e3283d9405dd1b24cc788413f9d8f37f45f438` |
| [NativeControlledChoice.cs](<../src/Volibear/NativeControlledChoice.cs>) | 0 | `96076fa801e2b54ad95e1bc6b90d4cf6cc09a39089a92477624950cfe950026f` |
| [NativeLobbyApi.cs](<../src/Volibear/NativeLobbyApi.cs>) | 0 | `3afdb23396f6ec4bcf9b571d007df3fef525ba9814812e59fd20deb04e2a7398` |
| [NativeMultiplayerSession.cs](<../src/Volibear/NativeMultiplayerSession.cs>) | 0 | `3292d240f89c2e5bc1716b30d3e54497497030b50b2030ea52dd84dbd7ba6cbc` |
| [NativeProductFlowProbe.cs](<../src/Volibear/NativeProductFlowProbe.cs>) | 0 | `8edd3c0892da58aacb26f23983d98eac77fdca097c5ed9e9cf43048bdfc50179` |
| [NativeRunAcceptanceProbe.cs](<../src/Volibear/NativeRunAcceptanceProbe.cs>) | 0 | `06e617830802f6bb424352e4c9522fe9ed5ef6564303d77c13f1ef1ff369642f` |
| [NativeVerificationSuite.cs](<../src/Volibear/NativeVerificationSuite.cs>) | 0 | `d8b489228599451dc9ae37c56e2e0772c4bd4a94318db3e424e43f8c236931f0` |
| [NewStrengthPassiveProbe.cs](<../src/Volibear/NewStrengthPassiveProbe.cs>) | 0 | `a2c63375d2093a8002cb30f2592e6e6e4aa0578017191448d5024e0617477baf` |
| [PassiveContractProbe.cs](<../src/Volibear/PassiveContractProbe.cs>) | 0 | `7205ce99c9345914e79d7d8c93575f4395385e026329121931291d677dda8cdf` |
| [PersistentContractProbe.cs](<../src/Volibear/PersistentContractProbe.cs>) | 0 | `4d9099d18ca128549819155dfe8e5ebad78924f558b6b391e3cb79dbabef7143` |
| [PowerPresentationProbe.cs](<../src/Volibear/PowerPresentationProbe.cs>) | 0 | `343f66b5c333741d7a8294f60a8d582406e767548d491d9b15a515783253ccf9` |
| [PreparedChoiceProbe.cs](<../src/Volibear/PreparedChoiceProbe.cs>) | 0 | `b4fb6f929cecbec4cded144350f73895cd103c31da5aa62524ff7d1a8f2614b9` |
| [PreparedContractProbe.cs](<../src/Volibear/PreparedContractProbe.cs>) | 0 | `2cb09359720c8db862e8114c635f17024cb2eb2ea8a7849f42704ae59c1ea7de` |
| [AudioCommitGate.cs](<../src/Volibear/Presentation/AudioCommitGate.cs>) | 0 | `80b5cdf120390de5d4b3fee861eaa78a67f8bcf3fef9296d7811c26e3a5f804c` |
| [PowerAudioReceipts.cs](<../src/Volibear/Presentation/PowerAudioReceipts.cs>) | 0 | `909b5d30e7e8234f2541e1cc4fb5bc907c5c7b695c964d20cb664f15070c0774` |
| [PowerPresentationCommits.cs](<../src/Volibear/Presentation/PowerPresentationCommits.cs>) | 0 | `6fb7b74e7b81c65daf544d81a3de0e9be9d336b25940b1bd785e23d5b1780c1a` |
| [PowerPresentationDomain.cs](<../src/Volibear/Presentation/PowerPresentationDomain.cs>) | 0 | `d4a860cb70637b67cd41f38549873b802d9e9301492fe17c50b291ad843fbfd9` |
| [PowerPresentationDomainScalars.cs](<../src/Volibear/Presentation/PowerPresentationDomainScalars.cs>) | 0 | `40fd8c68276006da4c1b65a848687a476a12e8d7568ee6e9fa9cca92714e26de` |
| [VolibearEffects.cs](<../src/Volibear/Presentation/VolibearEffects.cs>) | 0 | `9a63cd5f79dd5d54d22c23f6d70c4d59918220f49e33d62fb95f808bb860c06d` |
| [VolibearIcons.cs](<../src/Volibear/Presentation/VolibearIcons.cs>) | 0 | `0861a72767881fa8106c9f0c4f19bcaca503d792403dd5fc43cf30f9973b6c54` |
| [VolibearInspectPortraits.cs](<../src/Volibear/Presentation/VolibearInspectPortraits.cs>) | 0 | `688bd00135feb4e58ccecae348b16a1d913e206128e7122338901fed8a8340f0` |
| [VolibearMerchantIntegration.cs](<../src/Volibear/Presentation/VolibearMerchantIntegration.cs>) | 0 | `a8c921204135a186327f3dd8ee3db5ddbcf080ebeadef2da040b54593671b228` |
| [VolibearNativeAudio.cs](<../src/Volibear/Presentation/VolibearNativeAudio.cs>) | 0 | `d9518839623c986b201b26cb84222fb4012b821628c4ecea9ad7f2185d3d7c65` |
| [VolibearPresentation.cs](<../src/Volibear/Presentation/VolibearPresentation.cs>) | 0 | `f857a9ddb6efb26555d8c7518f54c5b8b26d4f67733084a4fb9c9f6f7e7d8ab1` |
| [VolibearPresentationBridge.DomainSpirit.cs](<../src/Volibear/Presentation/VolibearPresentationBridge.DomainSpirit.cs>) | 0 | `aff6a6201811b832f6b8bea8e67b63436bd14af4e1685fbd159438055ccf91ba` |
| [VolibearPresentationBridge.Motion.cs](<../src/Volibear/Presentation/VolibearPresentationBridge.Motion.cs>) | 0 | `4438d294d571ff31c560fd56d8943365c916bc294ae50d67ae6eb0f098716e8e` |
| [VolibearPresentationBridge.Semantics.cs](<../src/Volibear/Presentation/VolibearPresentationBridge.Semantics.cs>) | 0 | `d1991a8cf91b81cbe8564666bdbbec2ed9068e62339329f6306899d475aefb78` |
| [VolibearPresentationBridge.cs](<../src/Volibear/Presentation/VolibearPresentationBridge.cs>) | 0 | `b597cadadfbaa9f60210a24c3ab35df58d2c888b9565ade9444c77e893ef50ab` |
| [VolibearPresentationCues.cs](<../src/Volibear/Presentation/VolibearPresentationCues.cs>) | 0 | `63dcd419cd6ca2e551aedbe8b3344033a10259cdfc87d5a4c245e3002fb3aa63` |
| [VolibearTrailFactory.cs](<../src/Volibear/Presentation/VolibearTrailFactory.cs>) | 0 | `3a661cab5fba4642740bb0cf373f847faa62e9ae6393054dce35f258d2a7121a` |
| [actor.gd](<../src/Volibear/Presentation/actor.gd>) | 0 | `bf4e0c7e9a96cd5c5c4d94a97d1f24d8be4a81823b896768955b1ee204f444c6` |
| [audio_profile.gd](<../src/Volibear/Presentation/audio_profile.gd>) | 0 | `2b5a53a68090f4eb431d672fbf359b5c75c210c1f3231255def21df681c171a8` |
| [effects.gd](<../src/Volibear/Presentation/effects.gd>) | 0 | `ecf43c50d1b149438795610e6492ef7ff38c8320f5a8c1a36220ddbab129d3d3` |
| [energy.gd](<../src/Volibear/Presentation/energy.gd>) | 0 | `36770f2a01c61484e10bd3a425372ba5ba5fcf844072bdbe226d4081c2d47827` |
| [verify_audio_profile.gd](<../src/Volibear/Presentation/verify_audio_profile.gd>) | 0 | `b9269296cb463dde7c445a79d9f1775a08f5b3f7ea9d0a19c658fdb9581b09c4` |
| [verify_effects.gd](<../src/Volibear/Presentation/verify_effects.gd>) | 0 | `c158c2cfbba1bb126512147b1bb9c09cab47fd060b8197d2266e8e9e6a522de3` |
| [verify_pack.gd](<../src/Volibear/Presentation/verify_pack.gd>) | 0 | `e23abdcba95c871769206aee3d6fe37283332ba291ff9d7002d1597ac0341b09` |
| [volibear_effects.tscn](<../src/Volibear/Presentation/volibear_effects.tscn>) | 0 | `08e61c50338ba36d0cd2ea83c5e538fea28df23330e4bd020a90edb6bb38ef41` |
| [volibear_energy.tscn](<../src/Volibear/Presentation/volibear_energy.tscn>) | 1 | `f52dde1f328a910c8b2ca3d29977824c7e2aadb92e479405bef3bb078d05ed20` |
| [volibear_icon.tscn](<../src/Volibear/Presentation/volibear_icon.tscn>) | 0 | `e8dafd2336c8810fcd89cc8cf993db18df3913010d31152beca25390ecfc3065` |
| [volibear_merchant.tscn](<../src/Volibear/Presentation/volibear_merchant.tscn>) | 0 | `250d93ec724319c4c5a5e0677ee0fe1d050bdb2d8c1e1364b4252708faa3f92e` |
| [volibear_rest.tscn](<../src/Volibear/Presentation/volibear_rest.tscn>) | 0 | `11cb478d086e3dfc768abe2659ecb49814e39791a913f4271fd34d4e4aaf2e19` |
| [volibear_trail.tscn](<../src/Volibear/Presentation/volibear_trail.tscn>) | 0 | `3c3ea9b65155ce7e2f9fbb9edc6d71346a862fc25872b9a895271403ac88da81` |
| [volibear_transition.tres](<../src/Volibear/Presentation/volibear_transition.tres>) | 0 | `a4fd9d4a70c1e778d773b72c3834090f76b744b3a4838b5e03d35b01f1157bf7` |
| [PresentationAcceptanceProbe.cs](<../src/Volibear/PresentationAcceptanceProbe.cs>) | 0 | `77a54052defcea20b40922e0490ed49070be7433cede116bfcfdaffce1fa5651` |
| [PrimalContractProbe.cs](<../src/Volibear/PrimalContractProbe.cs>) | 0 | `3818af83ab4652145f5293c47d4756002121debd7f9860e8701a46b0f1022fe9` |
| [ProbeDiag.cs](<../src/Volibear/ProbeDiag.cs>) | 0 | `78f4fb4a9912a6f7453e7a8d73916d71cc6c54cc998f126926d36b57b3ae4571` |
| [RelicContractProbe.cs](<../src/Volibear/RelicContractProbe.cs>) | 0 | `2fae337f1cb91dcccb62102d4969c346bf83735b109666d854afbc343d1c3ce3` |
| [SaveLoadCatalogProbe.cs](<../src/Volibear/SaveLoadCatalogProbe.cs>) | 0 | `53386949a9087447c8cf65357ebe7d48a07f61781ef452b7f0873514b3f6b7b2` |
| [SaveLoadContractProbe.cs](<../src/Volibear/SaveLoadContractProbe.cs>) | 0 | `1be20b1557495316df435b7028cf91f47ea49b1103425180e57950418d477769` |
| [StandingExtraTurnProbe.cs](<../src/Volibear/StandingExtraTurnProbe.cs>) | 0 | `9bdeb7dfb5b5f159f6a32826d126877ab7aea384f9232b1749f8118617a9e55a` |
| [SuckPassiveContractProbe.cs](<../src/Volibear/SuckPassiveContractProbe.cs>) | 0 | `9800e9944d9a1523f0a291795f281077f113d936c43a8f30680d2171a8e78dbf` |
| [Volibear.json](<../src/Volibear/Volibear.json>) | 8 | `bd982d4d493c2bd4eb63aa34511a0df0d95a05ae8e8d238e2549d7da0846fab1` |
| [VolibearBootstrap.cs](<../src/Volibear/VolibearBootstrap.cs>) | 0 | `65c6423f424831bdea9810193e31dc57f6abbcd8ea63b6408928c941b2331ab8` |

## 复跑与冻结约定

```sh
python -B tools/export_text_review.py
python -B tools/export_text_review.py --check
# 仅在所有实施结束且 Lead 授权后运行一次：
python -B tools/export_text_review.py --replace-final
```

默认命令拒绝覆盖已有文档；--check 只比较而不写入。最终覆盖前须先合并人工修改；修改栏非空时工具拒绝覆盖。
