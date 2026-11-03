"""Synthetic oracle fixtures only; never native-game evidence."""
import power_stack_evidence as stack


def sample_stack():
    rows = []
    for i, (phase, model, amounts) in enumerate(stack.expected_samples()):
        label = stack.label_for(model, amounts)
        node = 101 if phase in ('armor-paid-base', 'armor-paid-mixed', 'armor-after-lightning') else 102 if phase.startswith('armor-') else 1000 + i
        description = '效果说明。'
        if model in stack.COUNT and len(amounts) == 2:
            description = '共2份，分别触发。'
        if model == 'ThunderArmorPower' and len(amounts) == 2:
            description = f'基础格挡合计{sum(amounts)}，分2次获得。'
        if phase == 'domain-permanent':
            description = '领域持续本战。'
        rows.append(dict(phase=phase, model=model, amounts=amounts, nodeCount=len(amounts), visibleCount=int(bool(amounts)),
                         label=label, visibleNode=node if amounts else 0, tips=[description] if amounts else [],
                         tipTitles=[stack.TITLES[model]] if amounts else []))
    return dict(fixture='native-container-matrix-and-paid-armor', samples=rows, powersRestored=True,
                blockBefore=11, blockAfter=18, blockGains=[3, 4], lightningBefore=0, lightningAfter=1,
                payments=[dict(model='Volibear_U34', upgraded=False, before=10, after=9, state='Finished', type='PlayCardAction'),
                          dict(model='Volibear_U34', upgraded=True, before=9, after=8, state='Finished', type='PlayCardAction'),
                          dict(model='Volibear_C24', upgraded=False, before=8, after=7, state='Finished', type='PlayCardAction')],
                captures=['armor-mixed.png', 'multiple-lightning.png', 'nonstacking.png', 'domain-permanent.png'])
