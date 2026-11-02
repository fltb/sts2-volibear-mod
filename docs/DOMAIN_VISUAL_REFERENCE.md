# 领域视觉参考与实现

## 参考

- Riot 官方沃利贝尔页面：https://www.leagueoflegends.com/en-gb/champions/volibear/
- 官方 R 技能演示：https://lol.dyn.riotcdn.net/x/videos/champion-abilities/0106/ability_0106_R1.mp4
- 参考视频仅保留在忽略目录 `.local/domain-reference/`，不随公开源码或 Mod 分发。

## 本轮目标

按用户指定将领域表现为放大的半透明蓝色灵体熊，脚下环绕雷电。保持已批准角色、动画帧与动作身份；通过实时渲染变换完成，而不是重画整套角色。

## 实现位置

`src/Volibear/Presentation/VolibearPresentationBridge.DomainSpirit.cs`：

- 以内层 Visuals 的脚部原点为中心放大 1.22 倍，避免以贴图左上角缩放导致脚底漂移。
- 只给角色 AnimatedSprite2D 挂载实时蓝色滤镜，保留明暗造型，透明度 72%，轻微蓝光脉动。
- 六条环形/断续折线雷电绕脚底运行，外圈蓝光、内层亮青白雷电；不依赖短暂一次性粒子来表示持续领域。
- 进入与退出沿既有领域动作、声音和特效；持续阶段跟随角色节点更新。
- 退出、死亡、战斗结束及销毁时恢复原比例与材质，释放护体雷圈。节点替换时重新绑定。

## 验证

实现中的参数与最终画面需通过定向 Godot 资源/运行检查及原生表现检查收口；最终结果记录在交付报告，不以本文参数表代替渲染结果。
