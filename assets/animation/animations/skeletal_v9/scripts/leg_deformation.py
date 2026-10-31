"""Shared thigh/shin deformation; preserves the reviewed source textures.

Near knee cap matches storm_leap 3/48. Shortening replaces excessive
front-facing flexion. Both leg layers use one field to avoid split seams.
"""
import math
import numpy as np

NEAR_BEND_CAP = math.radians(12.0)
FAR_PROXIMAL_SUPPORT = 65.0


def sector_vertex(vertex, worlds, bones, side):
    """Map one rest-world vertex to the reviewed common leg sector field."""
    h, k, f = [np.array(bones[n + '_' + side]['rest_world'])
               for n in ('hip', 'knee', 'ankle')]
    hp, kp, fp = [worlds[n + '_' + side][0]
                  for n in ('hip', 'knee', 'ankle')]
    angle = lambda p: math.atan2(p[1], p[0])
    tau = 2 * math.pi
    base = angle(h - k)
    span = (angle(f - k) - base) % tau
    target = angle(hp - kp)
    target_span = (angle(fp - kp) - target) % tau
    q = vertex - k
    theta = (angle(q) - base) % tau
    mapped = target + (theta / span * target_span if theta <= span else
                       target_span + (theta - span) / (tau - span) * (tau - target_span))
    radial_scale = 1.0
    if side == 'near':
        axis = (f - h) / np.linalg.norm(f - h)
        compression = np.linalg.norm(fp - kp) / np.linalg.norm(f - k)
        radial_scale += (compression - 1) * (np.dot(q, axis) / (np.linalg.norm(q) + 1e-12)) ** 2
    point = kp + radial_scale * np.linalg.norm(q) * np.array([math.cos(mapped), math.sin(mapped)])
    axis = (k - h) / np.linalg.norm(k - h)
    along = float(np.dot(vertex - h, axis))
    mix = float(np.clip((along + 35) / 170, 0, 1))
    mix = mix * mix * (3 - 2 * mix)
    position, rotation = worlds['pelvis']
    c, s = math.cos(rotation), math.sin(rotation)
    pelvis_point = position + np.array([[c, -s], [s, c]]) @ (vertex - np.array(bones['pelvis']['rest_world']))
    result = mix * point + (1 - mix) * pelvis_point
    if side == 'far':
        support = float(np.clip(1 - max(0, along) / 180, 0, 1))
        support = support * support * (3 - 2 * support)
        result = result + np.array([0., -FAR_PROXIMAL_SUPPORT]) * support
    return result
