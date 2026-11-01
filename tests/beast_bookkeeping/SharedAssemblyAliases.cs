extern alias ParentBuild;
// Scoped compile check consumes only shared public APIs from the existing build.
// Aliasing avoids importing yesterday's copies of the newly owned Beast* types.
global using VolibearCard = ParentBuild::Volibear.Content.VolibearCard;
global using VolibearCardPool = ParentBuild::Volibear.Content.VolibearCardPool;
global using LightningCmd = ParentBuild::Volibear.Content.LightningCmd;
