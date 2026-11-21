"""Author combat clips on the existing, approved Volibear bone/mesh rig.

No source painting is changed. Shoulder, elbow, wrist, torso, head and planted-foot
IK keys produce independent actions; these are not aliases or image translations.
The neutral 26-clip set remains byte-for-byte untouched.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parent
RIG = ROOT.parent / 'skeletal_v9'
sys.path.insert(0, str(RIG / 'scripts'))
import render as rig
from PIL import Image, ImageDraw


def curve(*values):
    """Evenly spaced normalized pose keys, with smoothstep between each pair."""
    return [[i / (len(values) - 1), value] for i, value in enumerate(values)]


def action(name, frames, contact, description, **channels):
    return dict(name=name, frame_count=frames, fps=24, duration=frames / 24,
                loop=False, skin='neutral', contact_frames=contact,
                description=description, channels=channels, events=[],
                procedural={'breath': 0.12, 'sway': 0.0})


MOTIONS = [
    action('backhand', 18, [7], '近爪收肘后反手掠出，远爪守胸，回收时肘部保持弯曲。',
           near_shoulder=curve(0, -68, -112, -30, 0), near_elbow=curve(0, -54, -16, -34, 0),
           near_wrist=curve(0, -16, 18, 2, 0), far_shoulder=curve(0, -12, -24, -12, 0),
           far_elbow=curve(0, -35, -32, -15, 0), torso_rot=curve(0, -5, 6, 2, 0),
           root_x=curve(0, -8, 18, 7, 0), head_rot=curve(0, -2, -5, 1, 0)),
    action('double_claw', 24, [7, 15], '近爪横挥后远爪追击，两侧肩肘交错，第二击不重播起手。',
           near_shoulder=curve(0, 6, -100, -46, -18, -8, 0),
           near_elbow=curve(0, -46, -20, -38, -32, -10, 0),
           far_shoulder=curve(0, -16, -28, 6, -56, -30, 0),
           far_elbow=curve(0, -18, -34, -44, -34, -24, 0),
           near_wrist=curve(0, -8, 12, 3, -7, 0, 0),
           torso_rot=curve(0, -4, 5, -2, 7, 2, 0), root_x=curve(0, -6, 20, 8, 22, 8, 0),
           root_y=curve(0, 5, 10, 5, 12, 4, 0)),
    action('claw_flurry', 26, [6, 12, 18], '三段交替挥爪：近爪、远爪、近爪反撕，各段均有收肘。',
           near_shoulder=curve(0, 10, -98, -32, -18, -78, -112, -30, 0),
           near_elbow=curve(0, -40, -20, -48, -36, -45, -14, -30, 0),
           far_shoulder=curve(0, -8, -28, 8, -58, -24, -12, -10, 0),
           far_elbow=curve(0, -18, -26, -42, -34, -26, -24, -14, 0),
           torso_rot=curve(0, -3, 5, -3, 6, -4, 7, 2, 0),
           root_x=curve(0, -6, 18, 4, 20, 6, 24, 8, 0),
           root_y=curve(0, 4, 10, 5, 12, 5, 14, 5, 0)),
    action('sweep', 24, [10], '压低身体蓄势，伸展开的近爪从低处向外横扫，头随肩回转。',
           near_shoulder=curve(0, 18, -36, -122, -76, -18, 0),
           near_elbow=curve(0, -46, -58, -16, -24, -28, 0),
           near_wrist=curve(0, -12, -16, 22, 14, 2, 0),
           far_shoulder=curve(0, -16, -28, -8, 8, -5, 0),
           far_elbow=curve(0, -34, -40, -22, -8, -12, 0),
           torso_rot=curve(0, -7, -3, 10, 7, 2, 0), head_rot=curve(0, -5, -8, 2, 4, 0, 0),
           root_y=curve(0, 20, 26, 18, 13, 6, 0), root_x=curve(0, -10, -6, 25, 18, 5, 0)),
    action('uppercut', 22, [10], '屈膝收爪后向上挑击，肘部先收后展，远臂反向平衡。',
           near_shoulder=curve(0, 14, -20, -125, -106, -28, 0),
           near_elbow=curve(0, -50, -58, -32, -20, -30, 0),
           far_shoulder=curve(0, -18, -12, 12, -5, -8, 0),
           far_elbow=curve(0, -28, -38, -10, -18, -12, 0),
           root_y=curve(0, 24, 28, -4, -2, 7, 0), root_x=curve(0, -9, -2, 18, 14, 4, 0),
           torso_rot=curve(0, 5, 6, -5, -6, 0, 0), head_rot=curve(0, 5, 5, -8, -6, 0, 0)),
    action('lunge', 20, [8], '低身蓄势，近脚向前踏，肩与爪同时送出，收脚回到战斗站姿。',
           near_shoulder=curve(0, 6, -82, -90, -35, 0),
           near_elbow=curve(0, -50, -26, -18, -34, 0),
           far_shoulder=curve(0, -30, 10, 8, -20, 0), far_elbow=curve(0, -35, -10, -18, -26, 0),
           root_x=curve(0, -12, 35, 42, 18, 0), root_y=curve(0, 16, 18, 14, 6, 0),
           torso_rot=curve(0, -4, 10, 9, 3, 0), head_rot=curve(0, -2, -3, -2, 0, 0),
           step_near_x=curve(0, 0, 22, 22, 10, 0), step_near_y=curve(0, -6, 0, 0, -4, 0)),
    action('ground_slam', 28, [14], '双臂举起收肘后向下砸击，膝盖承重下沉，再起身回收。',
           near_shoulder=curve(0, -40, -118, -124, -12, 10, -10, 0),
           near_elbow=curve(0, -30, -45, -50, -12, -10, -20, 0),
           far_shoulder=curve(0, -28, -64, -70, 12, 18, -8, 0),
           far_elbow=curve(0, -24, -40, -42, -14, -8, -14, 0),
           torso_rot=curve(0, -2, -8, -8, 12, 10, 3, 0),
           head_rot=curve(0, -3, -10, -10, 8, 5, 2, 0),
           root_y=curve(0, 12, -4, -5, 34, 30, 12, 0), root_x=curve(0, -8, -12, -8, 22, 14, 4, 0)),
    action('stomp_chain', 30, [8, 17, 24], '近脚与远脚轮流提膝落踏，最后双脚压地；手臂随每次承重摆动。',
           step_near_y=curve(0, -30, 0, 0, 0, -24, 0, 0),
           step_near_x=curve(0, 9, 10, 0, 0, 8, 6, 0),
           step_far_y=curve(0, 0, 0, -26, 0, 0, 0, 0),
           step_far_x=curve(0, 0, 0, -8, -6, 0, 0, 0),
           near_shoulder=curve(0, -48, -10, -16, -56, -62, -4, 0),
           near_elbow=curve(0, -36, -16, -28, -40, -46, -10, 0),
           far_shoulder=curve(0, -8, -30, -50, -8, -30, -2, 0),
           far_elbow=curve(0, -16, -38, -42, -12, -24, -8, 0),
           root_y=curve(0, 4, 26, 2, 28, 8, 32, 0), torso_rot=curve(0, -3, 6, -4, 5, -4, 8, 0)),
    action('bite_rend', 26, [9, 17], '张口前探咬住，再向后撕扯，头颈与躯干有两次不同方向的发力。',
           root_x=curve(0, -10, 30, 26, -8, -13, 0), root_y=curve(0, 7, 19, 16, 9, 4, 0),
           torso_rot=curve(0, -4, 9, 7, -5, -6, 0), head_rot=curve(0, -5, 8, 6, -12, -8, 0),
           head_x=curve(0, -4, 18, 16, -8, -3, 0), head_y=curve(0, -2, 9, 6, -7, -3, 0),
           near_shoulder=curve(0, -16, -46, -36, -74, -38, 0),
           near_elbow=curve(0, -22, -38, -28, -46, -20, 0),
           far_shoulder=curve(0, -18, -24, -12, -42, -18, 0), far_elbow=curve(0, -20, -42, -36, -38, -16, 0),
           roar=[[0, 0], [.18, 1], [.32, 1], [.38, 0], [.60, 0], [.69, .5], [.82, 0], [1, 0]]),
    action('thunder_call', 28, [13], '抬头举起近掌唤雷，远掌护胸，落雷时近臂向下引导。',
           near_shoulder=curve(0, -36, -132, -136, -82, -44, 0),
           near_elbow=curve(0, -36, -26, -22, -44, -30, 0), near_wrist=curve(0, -14, -24, -18, 12, 5, 0),
           far_shoulder=curve(0, -24, -82, -90, -36, -12, 0), far_elbow=curve(0, -26, -32, -30, -40, -16, 0),
           head_rot=curve(0, -4, -13, -12, -3, -2, 0), torso_rot=curve(0, -2, -6, -6, 1, 0, 0),
           root_y=curve(0, 6, -3, -3, 9, 5, 0)),
    action('chain_channel', 28, [9, 15, 21], '两掌交替导引雷弧，头跟随指向，三个脉冲使用不同肩肘姿态。',
           near_shoulder=curve(0, -28, -98, -54, -38, -108, -62, 0),
           near_elbow=curve(0, -36, -24, -46, -36, -24, -30, 0),
           far_shoulder=curve(0, -20, -24, -62, -58, -22, -28, 0),
           far_elbow=curve(0, -24, -40, -20, -24, -38, -22, 0),
           head_rot=curve(0, -3, -5, 3, 2, -7, -2, 0),
           torso_rot=curve(0, -2, 3, -3, 1, 4, 1, 0), root_y=curve(0, 6, 2, 7, 2, 8, 4, 0)),
    action('storm_channel', 32, [15], '双臂张开向上托起风暴，胸部展开，释放时下压并张口咆哮。',
           near_shoulder=curve(0, -26, -88, -128, -122, -58, -24, 0),
           near_elbow=curve(0, -32, -36, -18, -20, -38, -20, 0),
           far_shoulder=curve(0, -24, -52, -72, -68, -34, -18, 0),
           far_elbow=curve(0, -28, -32, -16, -18, -32, -18, 0),
           torso_rot=curve(0, -2, -6, -8, -8, 4, 1, 0), head_rot=curve(0, -4, -10, -13, -8, 1, 0, 0),
           root_y=curve(0, 8, -3, -6, -4, 20, 10, 0),
           roar=[[0, 0], [.34, .5], [.48, 1], [.68, 1], [.8, 0], [1, 0]]),
    action('iron_guard', 24, [9], '双臂交错护住胸口、下沉重心，受力前保持稳固支撑姿态。',
           near_shoulder=curve(0, -58, -112, -116, -102, -44, 0),
           near_elbow=curve(0, -36, -54, -54, -48, -26, 0), near_wrist=curve(0, 4, 18, 18, 14, 4, 0),
           far_shoulder=curve(0, -26, -42, -44, -40, -20, 0),
           far_elbow=curve(0, -30, -52, -54, -48, -20, 0),
           root_x=curve(0, -3, -10, -12, -10, -4, 0), root_y=curve(0, 12, 24, 25, 23, 10, 0),
           torso_rot=curve(0, -2, -5, -5, -4, -1, 0), head_rot=curve(0, 3, 6, 7, 6, 2, 0)),
    action('primal_charge', 28, [13], '双爪向胸前聚拢再展开，抬头咆哮，蓄势与普通施法有不同轮廓。',
           near_shoulder=curve(0, -28, -64, -100, -76, -26, 0),
           near_elbow=curve(0, -38, -56, -28, -18, -24, 0),
           far_shoulder=curve(0, -20, -36, -58, -30, -12, 0),
           far_elbow=curve(0, -28, -50, -22, -14, -20, 0),
           torso_rot=curve(0, 3, 5, -8, -6, 0, 0), head_rot=curve(0, 6, 8, -14, -9, 0, 0),
           root_y=curve(0, 18, 24, -4, -3, 8, 0),
           roar=[[0, 0], [.30, .5], [.42, 1], [.65, 1], [.78, 0], [1, 0]]),
]


def install_clips():
    rig.CLIPS.update({clip['name']: clip for clip in MOTIONS})
    original = rig.leg_target

    def leg_target(side, channels, air):
        return original(side, channels, air) + rig.np.array([
            channels.get('step_' + side + '_x', 0),
            channels.get('step_' + side + '_y', 0)]) / .46

    rig.leg_target = leg_target


install_clips()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    paths = [Path(__file__), RIG / 'rig.json', RIG / 'scripts/render.py',
             RIG / 'scripts/leg_deformation.py', ROOT.parent / 'rig/motions.json']
    paths += sorted((RIG / 'parts').glob('*.png'))
    return {path.relative_to(ROOT.parent).as_posix(): digest(path) for path in paths}


def render_frame(task):
    name, index, count = task
    # Both ends match neutral pose; avoiding a one-frame pop into the return loop.
    return rig.render(name, index / (count - 1))


def export_clip(pool, clip, fingerprint, preview_root):
    name, count = clip['name'], clip['frame_count']
    frames = list(pool.map(render_frame, [(name, i, count) for i in range(count)]))
    atlas = Image.new('RGBA', (8 * 512, math.ceil(count / 8) * 512))
    records, poses, bounds = [], [], []
    for i, frame in enumerate(frames):
        rect = [i % 8 * 512, i // 8 * 512, 512, 512]
        atlas.alpha_composite(frame, tuple(rect[:2]))
        bound = frame.getbbox()
        if bound is None or bound[0] <= 0 or bound[1] <= 0 or bound[2] >= 512 or bound[3] >= 512:
            raise ValueError(f'Clipped or empty frame: {name}/{i} {bound}')
        bounds.append(list(bound))
        records.append(dict(frame=i, rect=rect, time_seconds=i / 24, duration_ms=1000 / 24,
                            raw_rgba_sha256=hashlib.sha256(frame.tobytes()).hexdigest(), pivot_px=[250, 442]))
        angles, offsets, channels = rig.pose(name, i / (count - 1))
        worlds = rig.world(angles, offsets)
        poses.append(dict(frame=i, channels=channels,
                          markers_px={bone: (worlds[bone][0] * (.46 * 512 / 768)
                                             + rig.np.array([70, 111]) * 512 / 768).round(3).tolist()
                                      for bone in ('head', 'wrist_near', 'wrist_far', 'ankle_near', 'ankle_far')}))
    image_path = ROOT / 'atlases' / (name + '.png')
    json_path = image_path.with_suffix('.json')
    rig.save(image_path, atlas)
    meta = {key: clip[key] for key in ('name', 'fps', 'frame_count', 'duration', 'loop', 'skin', 'contact_frames', 'description')}
    meta.update(frames=records, poses=poses, alpha_bounds=bounds, pivot_px=[250, 442],
                atlas=dict(image='atlases/' + name + '.png', json='atlases/' + name + '.json',
                           columns=8, rows=math.ceil(count / 8), tile_size=[512, 512]),
                input_fingerprint=fingerprint, technique='existing_weighted_skeleton_new_joint_keyframes')
    rig.js(json_path, meta)
    result = {key: value for key, value in meta.items() if key not in ('poses', 'alpha_bounds')}
    result.update(atlas_sha256=digest(image_path), atlas_json_sha256=digest(json_path))
    if preview_root:
        preview_root.mkdir(parents=True, exist_ok=True)
        preview = []
        for frame in frames:
            bg = Image.new('RGB', frame.size, (21, 30, 39))
            bg.paste(frame, (0, 0), frame)
            preview.append(bg)
        preview[0].save(preview_root / (name + '.gif'), save_all=True, append_images=preview[1:],
                        duration=[round((i + 1) * 100 / 24) * 10 - round(i * 100 / 24) * 10 for i in range(count)],
                        loop=0, disposal=2)
        sheet = Image.new('RGB', (256 * 4, 280 * math.ceil(count / 4)), (21, 30, 39))
        draw = ImageDraw.Draw(sheet)
        for i, frame in enumerate(preview):
            x, y = i % 4 * 256, i // 4 * 280
            sheet.paste(frame.resize((256, 256)), (x, y + 24))
            draw.text((x + 7, y + 6), f'{name} / {i:02}', fill=(220, 235, 240))
        sheet.save(preview_root / (name + '.png'))
    print(json.dumps(dict(clip=name, frames=count, bytes=image_path.stat().st_size)), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--extremes', action='store_true')
    args = parser.parse_args()
    if args.extremes:
        if not args.preview:
            parser.error('--extremes needs --preview')
        args.preview.mkdir(parents=True, exist_ok=True)
        canvas = Image.new('RGB', (256 * 4, 280 * math.ceil(len(MOTIONS) / 4)), (21, 30, 39))
        draw = ImageDraw.Draw(canvas)
        for index, clip in enumerate(MOTIONS):
            frame = rig.render(clip['name'], clip['contact_frames'][0] / (clip['frame_count'] - 1))
            x, y = index % 4 * 256, index // 4 * 280
            frame = frame.resize((256, 256))
            canvas.paste(frame, (x, y + 24), frame)
            draw.text((x + 7, y + 6), clip['name'], fill=(220, 235, 240))
        canvas.save(args.preview / 'extremes.png')
        return
    before = inputs()
    fingerprint = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
    clips = []
    with ProcessPoolExecutor(max_workers=max(1, min(4, args.jobs))) as pool:
        for clip in MOTIONS:
            clips.append(export_clip(pool, clip, fingerprint, args.preview))
    if inputs() != before:
        raise ValueError('Authoring inputs changed during export; rebuild the complete set')
    rig.js(ROOT / 'manifest.json', dict(schema_version=1, render_complete=True,
           canvas_size=[512, 512], pivot_px=[250, 442], fps=24, facing='right',
           contains_baked_effects=False, contains_domain_tint=False,
           base_art='skeletal_v9 existing authored parts and unchanged anatomy',
           total_sequences=len(clips), total_frames=sum(c['frame_count'] for c in clips),
           source_integrity=before, render_input_sha256=fingerprint, clips=clips))


if __name__ == '__main__':
    main()
