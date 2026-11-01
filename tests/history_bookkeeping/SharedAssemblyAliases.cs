extern alias ParentBuild;
// Only shared public APIs come from the parent's previously compiled assembly.
// The owned history, target-cost and card implementation files are compiled from source.
global using VolibearCard = ParentBuild::Volibear.Content.VolibearCard;
global using CardResolutionHooks = ParentBuild::Volibear.Core.CardResolutionHooks;
global using BeastForms = ParentBuild::Volibear.Core.BeastForms;
global using LightningBatches = ParentBuild::Volibear.Core.LightningBatches;
