"""Render rest-site one-shots on the approved character rig (no part regeneration)."""
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

import render as rig

OUTPUT = Path(__file__).resolve().parents[2] / 'camp'
CHANNELS = ('root_y', 'torso_rot', 'head_rot', 'near_shoulder', 'near_elbow',
            'near_wrist', 'far_shoulder', 'far_elbow')
IDLE = (5, 0, 3, 2, -2, 0, 0, 0)
# Two contact poses per activity. The beat sheet below controls approach, repetition and release.
POSES = {
    'heal': ((59, 7, 13, -52, -44, 12, 18, -28), (57, 6, 10, -64, -50, 2, 14, -34)),
    'smith': ((32, 8, 13, -78, -52, -16, 12, -20), (43, 15, 19, -55, -19, 17, 10, -18)),
    'mend': ((26, 6, 10, -78, -24, 3, 4, -22), (30, 10, 8, -93, -38, -22, 9, -32)),
    'cook': ((36, 8, 12, -70, -39, -24, 11, -25), (42, 13, 18, -48, -25, 20, 9, -27)),
    'dig': ((24, -7, 4, -47, -66, -10, 12, -26), (58, 19, 17, -48, -5, 26, 2, -10)),
    'lift': ((43, 5, 10, -30, -15, -5, 8, -10), (6, -8, -13, -112, -69, -12, -13, -55)),
    'clone': ((18, 1, 13, -55, -56, -14, 5, -27), (15, -4, -1, -96, -35, 24, -23, -34)),
    'hatch': ((49, 8, 19, -53, -36, 18, 14, -30), (36, -3, -4, -73, -53, 8, 20, -43)),
    'evolve': ((32, 6, 13, -62, -45, 7, 14, -26), (8, -7, -18, -104, -54, 13, -24, -53)),
    'kindle': ((41, 11, 15, -70, -22, 18, 8, -18), (26, 3, -3, -75, -45, -16, 11, -26)),
    'restore': ((50, 14, 14, -53, -25, 18, 11, -16), (43, 8, 9, -72, -39, -13, 13, -34)),
}
def contact(animation, t):
    angles, offsets, _ = rig.pose(animation, t)
    point, angle = rig.world(angles, offsets)['wrist_near']
    tip = point + rig.rot(angle) @ rig.np.array([-48, 93])
    return tuple(tip * (.46 * 512 / 768) + rig.np.array([70, 111]) * (512 / 768))


def draw_props(name, t, x, y, stone, accents):
    """Paint the grindstone under the claws; embers and grit follow the point of contact."""
    props = Image.new('RGBA', (512, 512))
    draw = ImageDraw.Draw(props)
    if name == 'smith':
        sx, sy = stone
        draw.polygon([(sx-34,sy+19),(sx-19,sy+2),(sx+22,sy-2),(sx+34,sy+7),
                      (sx+29,sy+19),(sx-19,sy+28)], fill='#353a44', outline='#222931')
        draw.polygon([(sx-34,sy+19),(sx-19,sy+2),(sx+22,sy-2),(sx+34,sy+7),
                      (sx-16,sy+15)], fill='#879296', outline='#515d64')
        draw.line([(sx-18,sy+6),(sx+18,sy+1)], fill='#bdc7c3', width=2)
        if any(0 <= t-beat < .075 for beat in accents[::2]):
            for dx, dy in ((16,-10),(11,-18),(25,-4),(-8,-9)):
                draw.line([(sx+dx*.35,sy+dy*.35),(sx+dx,sy+dy)], fill='#ffbd65', width=2)
    elif name == 'dig' and any(0 <= t-beat < .12 for beat in accents[::2]):
        for dx, dy in ((19,-11),(31,-6),(-9,-15),(11,-24)):
            draw.ellipse((x+dx,y+dy,x+dx+4,y+dy+3), fill='#916e51')
    elif name in ('heal', 'kindle') and .18 <= t <= .88:
        for i in range(4):
            phase = (25*t + 3*i) % 10
            ex = x + 17 + i*6 + math.sin(phase*.5)*3
            ey = y + 14 - phase*3
            draw.line([(ex,ey+3),(ex+1,ey)], fill=(255,154+10*i,74,210), width=2)
    elif name == 'lift':
        # Cast iron bell hangs below the paw throughout the lift.
        draw.arc((x-9,y-1,x+9,y+20), 174, 366, fill='#636c78', width=5)
        draw.ellipse((x-15,y+8,x+15,y+35), fill='#3c4654', outline='#929ca5', width=2)
        draw.arc((x-12,y+11,x+9,y+30), 205, 275, fill='#677682', width=2)
    elif name == 'clone':
        for j in range(2):
            offset = j * 17 * min(1, max(0,(t-.26)*4))
            draw.rounded_rectangle((x+offset-8,y-12-offset/2,x+offset+9,y+10-offset/2),
                                   radius=2, fill='#465970', outline='#d5b775', width=2)
    elif name == 'cook':
        cx, cy = stone
        draw.line([(x,y),(cx,cy+12)], fill='#b3875e', width=4)
        draw.pieslice((cx-24,cy-6,cx+24,cy+33),0,180,fill='#37404b',outline='#84949c',width=2)
        draw.ellipse((cx-24,cy+8,cx+24,cy+15),fill='#945a32',outline='#a6a8a5',width=2)
    elif name in ('mend','restore','evolve'):
        tint = '#91d3ac' if name != 'evolve' else '#93ccf0'
        for j in range(3):
            phase = (t*2+j/3)%1
            xx, yy = x+9+j*10, y-27*phase
            arm = max(1, int(4*math.sin(math.pi*phase)))
            draw.line([(xx-arm,yy),(xx+arm,yy)],fill=tint,width=2)
            draw.line([(xx,yy-arm),(xx,yy+arm)],fill=tint,width=2)
    elif name == 'hatch':
        draw.ellipse((x-4,y-12,x+15,y+12), fill='#d9c593', outline='#766858', width=2)
        if t>.52:
            draw.line([(x-2,y),(x+3,y+3),(x+7,y-1),(x+13,y+2)], fill='#725749', width=2)
    opacity = min(1, t*8, (1-t)*8)
    props.putalpha(props.getchannel('A').point(lambda a: round(a*opacity)))
    return props


def render_clip(name):
    a, b = POSES[name]
    beats = [(0, IDLE), (.24, a)]
    # Stroke / pause / recover. Use separate key times for repeated and held actions.
    accents = {
        'smith': (.38, .51, .63, .74, .84), 'dig': (.42, .59, .74),
        'cook': (.37, .52, .66, .79), 'mend': (.43, .57, .73),
        'restore': (.42, .57, .74), 'heal': (.44, .63, .78),
        'kindle': (.41, .53, .72), 'lift': (.52, ), 'clone': (.56, ),
        'evolve': (.57, ), 'hatch': (.64, ),
    }[name]
    for index, t in enumerate(accents):
        beats.append((t, b if index % 2 == 0 else a))
    beats.extend([(.86, beats[-1][1]), (1, IDLE)])
    rig.CLIPS[name] = {'channels': {channel: [(t, pose[j]) for t, pose in beats]
                                    for j, channel in enumerate(CHANNELS)}}
    atlas = Image.new('RGBA', (3072, 2048))
    stone = contact(name, accents[0])
    for i in range(24):
        t = i / 23
        bear = rig.render(name, t)
        props = draw_props(name, t, *contact(name, t), stone, accents)
        bear.alpha_composite(props)
        atlas.paste(bear, ((i % 6)*512, (i // 6)*512))
    rig.save(OUTPUT / (name + '.png'), atlas)
    print(name, flush=True)


if __name__ == '__main__':
    with ProcessPoolExecutor(max_workers=4) as pool:
        list(pool.map(render_clip, POSES))
