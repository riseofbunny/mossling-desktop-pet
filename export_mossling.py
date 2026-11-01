"""Full mossling desktop-pet export: every clip x both skins, FX layers, manifest v2.

Reads the installed game's anim zips and renders every clip for both skins,
plus the hit/thaw/spin overlay layers, into MosslingDesktopPet/ next to this
script: frames/{skin}/{clip}/*.png, frames/effects/{name}/*.png, manifest.json.
Those assets derive from game art, so they are generated locally and never
committed to the repository.

Usage:
    python export_mossling.py --game "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Don't Starve Together"
"""
from __future__ import annotations

import argparse
import io
import json
import math
import struct
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
PET_DIR = HERE / 'MosslingDesktopPet'

FRAMES_DIR = PET_DIR / 'frames'
DEFAULT_GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together")


def symbol_hash(name):
    value = 0
    for character in name.lower():
        value = (ord(character) + 65599 * value) & 0xffffffff
    return value


OPTIONAL_SLOTS = {symbol_hash(name) for name in
                  ['swap_hat', 'swap_object', 'swap_frozen', 'Belt', 'swap_fire',
                   'bolt', 'bolt_a', 'bolt_b', 'bolt_c', 'bolt_d']}
HIDDEN_LAYERS = frozenset()

SOURCES = ['mossling_basic', 'mossling_actions']
BODY_BUILDS = ['mossling_build']
EQUIPMENT_BUILDS = ['mossling_angry_build', 'mossling_yule_build',
                    'mossling_yule_angry_build', 'frozen']
SPIN_ANIMATIONS = {'spin_loop', 'spin_pst', 'spin_pst_loop', 'spin_pst_loop_pst'}
# The game tweens the entity to 1.55x during the whirlwind (SGmossling.lua:328),
# but a desktop pet must fit corners and window edges: bake the angry build at
# the same size as the ordinary chick instead.
SPIN_SCALE = 1.0
SKINS = ['normal', 'yule']


class Reader:
    def __init__(self, data):
        self.stream = io.BytesIO(data)

    def read(self, fmt):
        fmt = '<' + fmt
        vals = struct.unpack(fmt, self.stream.read(struct.calcsize(fmt)))
        return vals[0] if len(vals) == 1 else vals

    def string(self):
        return self.stream.read(self.read('I')).decode('utf-8')

    def names(self):
        result = {}
        for _ in range(self.read('I')):
            key = self.read('I')
            result[key] = self.string()
        return result


def parse_anim(data):
    r = Reader(data)
    assert r.stream.read(4) == b'ANIM' and r.read('I') == 4
    _, _, _, count = r.read('4I')
    animations = []
    for _ in range(count):
        name = r.string()
        facing = r.read('B')
        bank, fps, count_frames = r.read('IfI')
        frames = []
        for _ in range(count_frames):
            bounds = r.read('4f')
            for _ in range(r.read('I')):
                r.read('I')
            elements = [r.read('3I7f') for _ in range(r.read('I'))]
            frames.append({'bounds': bounds, 'elements': elements})
        animations.append({'name': name, 'facing': facing, 'bank': bank,
                           'fps': fps, 'frames': frames})
    names = r.names()
    assert r.stream.tell() == len(data)
    return animations, names


def decode_tex(data):
    r = Reader(data)
    assert r.stream.read(4) == b'KTEX'
    header = r.read('I')
    compression = (header >> 4) & 31
    mip_count = (header >> 13) & 31
    metas = [r.read('3HI') for _ in range(mip_count)]
    width, height, _, size = metas[0]
    payload = r.stream.read(size)
    if compression in (0, 1, 2):
        image = Image.frombytes('RGBA', (width, height), payload, 'bcn',
                                {0: 1, 1: 2, 2: 3}[compression])
    elif compression in (4, 5):
        image = Image.frombytes('RGB' if compression == 4 else 'RGBA',
                                (width, height), payload).convert('RGBA')
    else:
        raise ValueError(f'Unsupported KTEX compression {compression}')
    pixels = np.array(image).astype(np.float32)
    alpha = pixels[..., 3:4]
    pixels[..., :3] = np.minimum(255, pixels[..., :3] * 255 / np.maximum(alpha, 1))
    return Image.fromarray(pixels.astype(np.uint8)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def parse_build(z):
    data = z.read('build.bin')
    r = Reader(data)
    assert r.stream.read(4) == b'BILD' and r.read('I') == 6
    count_symbols, _ = r.read('2I')
    name = r.string()
    atlas_names = [r.string() for _ in range(r.read('I'))]
    symbols = {}
    for _ in range(count_symbols):
        key, count = r.read('2I')
        symbols[key] = [r.read('2I4f2I') for _ in range(count)]
    vertices = [r.read('6f') for _ in range(r.read('I'))]
    names = r.names()
    assert r.stream.tell() == len(data)
    atlases = [decode_tex(z.read(n)) for n in atlas_names]
    return {'name': name, 'symbols': symbols, 'vertices': vertices,
            'names': names, 'atlases': atlases}


def build_symbol_images(build):
    result = {}
    for key, frames in build['symbols'].items():
        for frame in frames:
            number, duration, cx, cy, width, height, first, count = frame
            left, top = math.floor(cx - width / 2), math.floor(cy - height / 2)
            size = (math.ceil(cx + width / 2) - left,
                    math.ceil(cy + height / 2) - top)
            image = Image.new('RGBA', size)
            for start in range(first, first + count, 6):
                verts = build['vertices'][start:start + 6]
                if len(verts) != 6:
                    raise ValueError('Incomplete build quad')
                atlas = build['atlases'][round(verts[0][5])]
                x0, x1 = min(v[0] for v in verts), max(v[0] for v in verts)
                y0, y1 = min(v[1] for v in verts), max(v[1] for v in verts)
                u0, u1 = min(v[3] for v in verts), max(v[3] for v in verts)
                v0, v1 = min(v[4] for v in verts), max(v[4] for v in verts)
                crop = atlas.crop((round(u0 * atlas.width), round((1 - v1) * atlas.height),
                                   round(u1 * atlas.width), round((1 - v0) * atlas.height)))
                target = (max(1, round(x1 - x0)), max(1, round(y1 - y0)))
                crop = crop.resize(target, Image.Resampling.LANCZOS)
                image.paste(crop, (round(x0 - left), round(y0 - top)))
            for index in range(number, number + duration):
                result[key, index] = (image, left, top)
    return result


def load_assets(anim_dir):
    symbols = {}
    all_names = {}
    animations = []
    for name in ['mossling_build', *SOURCES]:
        with zipfile.ZipFile(anim_dir / (name + '.zip')) as z:
            if 'build.bin' in z.namelist():
                build = parse_build(z)
                symbols.update(build_symbol_images(build))
                all_names.update(build['names'])
            if name in SOURCES:
                clips, names = parse_anim(z.read('anim.bin'))
                for clip in clips:
                    clip['source'] = 'anim/' + name + '.zip'
                animations.extend(clips)
                all_names.update(names)
    equipment = {}
    for name in EQUIPMENT_BUILDS:
        with zipfile.ZipFile(anim_dir / (name + '.zip')) as z:
            build = parse_build(z)
            equipment[name] = build_symbol_images(build)
            all_names.update(build['names'])
    # FX builds: spin lightning child entity + universal hit sparks + shatter.
    fx = {}
    for name in ('mossling_spin_fx', 'sparks', 'frozen_shatter'):
        with zipfile.ZipFile(anim_dir / (name + '.zip')) as z:
            build = parse_build(z)
            clips, names = parse_anim(z.read('anim.bin'))
            for clip in clips:
                clip['source'] = 'anim/' + name + '.zip'
            fx[name] = {'symbols': build_symbol_images(build), 'clips': clips}
            all_names.update(names)
    return animations, symbols, equipment, all_names, fx


def symbol_setup(skin, animation, base, equipment):
    symbols = dict(base)
    if skin == 'yule':
        # The game swaps the whole build for Winters' Feast
        # (prefabs/mossling.lua:117): same symbol hashes, festive art, plus beak.
        symbols.update(equipment['mossling_yule_build'])
    if animation in SPIN_ANIMATIONS:
        symbols.update(equipment['mossling_yule_angry_build' if skin == 'yule'
                                 else 'mossling_angry_build'])
    if animation.startswith('frozen'):
        for (key, index), value in equipment['frozen'].items():
            if key == symbol_hash('frozen'):
                symbols[symbol_hash('swap_frozen'), index] = value
    return symbols, set()


def complete_animation_symbols(symbols, animations):
    required = {}
    for animation in animations:
        for frame in animation['frames']:
            for key, index, *_ in frame['elements']:
                required[key] = max(index, required.get(key, -1))
    completed = dict(symbols)
    for key, max_index in required.items():
        available = sorted(index for symbol_key, index in symbols if symbol_key == key)
        if not available:
            continue
        for index in range(max_index + 1):
            if (key, index) in completed:
                continue
            earlier = [candidate for candidate in available if candidate < index]
            fallback = max(earlier) if earlier else min(available)
            completed[key, index] = symbols[key, fallback]
    return completed


def extra_scale(clip):
    return SPIN_SCALE if clip['name'] in SPIN_ANIMATIONS else 1.0


def clip_origin(clip, origin_pixels, base_scale):
    scale = base_scale * extra_scale(clip)
    origin = tuple(value / scale for value in origin_pixels)
    return (origin[0] + clip.get('dx', 0.0), origin[1])


def visible_bounds(frame, symbols, hidden, extra=1.0, origin=(0.0, 0.0)):
    bounds = []
    for key, index, layer, a, b, c, d, tx, ty, z in frame['elements']:
        if layer in hidden:
            continue
        if (key, index) not in symbols:
            if key in OPTIONAL_SLOTS:
                continue
            raise KeyError(f'Missing required symbol {key}/{index}')
        image, left, top = symbols[key, index]
        box = image.getbbox()
        if not box:
            continue
        x0, y0, x1, y1 = box
        for x, y in [(x0 + left, y0 + top), (x1 + left, y0 + top),
                     (x0 + left, y1 + top), (x1 + left, y1 + top)]:
            wx, wy = a * x + c * y + tx, b * x + d * y + ty
            wx = (wx + origin[0]) * extra - origin[0]
            wy = (wy + origin[1]) * extra - origin[1]
            bounds.append((wx, wy))
    return bounds


def render_frame(frame, symbols, canvas, origin, hidden_layers=None, scale=1):
    result = Image.new('RGBA', canvas)
    hidden_layers = HIDDEN_LAYERS if hidden_layers is None else hidden_layers
    for element in sorted(frame['elements'], key=lambda e: e[-1], reverse=True):
        key, index, layer, a, b, c, d, tx, ty, z = element
        if layer in hidden_layers:
            continue
        if (key, index) not in symbols:
            if key in OPTIONAL_SLOTS:
                continue
            raise KeyError(f'Missing symbol {key} frame {index}')
        image, left, top = symbols[key, index]
        transform = np.array([[a, c, tx + origin[0] + a * left + c * top],
                              [b, d, ty + origin[1] + b * left + d * top],
                              [0, 0, 1]], dtype=float)
        transform[:2] *= scale
        if abs(np.linalg.det(transform)) < 1e-8:
            continue
        corners = transform @ np.array([[0, image.width, 0, image.width],
                                        [0, 0, image.height, image.height], [1, 1, 1, 1]])
        x0, y0 = np.floor(corners[:2].min(axis=1) - 2).astype(int)
        x1, y1 = np.ceil(corners[:2].max(axis=1) + 2).astype(int)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(canvas[0], x1), min(canvas[1], y1)
        if x1 <= x0 or y1 <= y0:
            continue
        transform[:2, 2] -= [x0, y0]
        inverse = np.linalg.inv(transform)
        transformed = image.transform((x1 - x0, y1 - y0), Image.Transform.AFFINE,
                                      tuple(inverse[:2].ravel()), Image.Resampling.BICUBIC)
        result.alpha_composite(transformed, (x0, y0))
    return result


def save_png_atomic(image, path: Path):
    temporary = path.with_name(path.stem + '.new.png')
    image.save(temporary, format='PNG', compress_level=2)
    temporary.replace(path)


def save_clip_images(skin, clip_id, images, fps):
    folder = FRAMES_DIR / skin / clip_id
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, image in enumerate(images):
        path = folder / f'{index:03}.png'
        save_png_atomic(image, path)
        paths.append(path.relative_to(PET_DIR).as_posix())
    return paths


def find_clip(clips, name, facing):
    for clip in clips:
        if clip['name'] == name and clip['facing'] == facing:
            return clip
    raise KeyError(f'Missing animation {name} facing {facing}')


LABELS = {
    'idle': '待机', 'walk_pre': '走路起步', 'walk_loop': '走路', 'walk_pst': '走路停下',
    'sleep_pre': '入睡', 'sleep_loop': '睡觉', 'sleep_pst': '醒来',
    'frozen': '冰冻', 'frozen_loop_pst': '解冻',
    'shock_loop': '触电', 'shock_pst': '触电结束',
    'eat': '吃食', 'eat_pst': '吃完整理', 'action': '觅食动作',
    'atk': '啄击', 'hit': '受击', 'death': '倒下', 'corpse': '倒地', 'corpse_hit': '倒地受击',
    'hatch': '破壳出生', 'meep': '叫妈妈', 'knockback': '被击退',
    'taunt_pre': '挑衅起手', 'taunt': '拍翅炫耀', 'taunt_pst': '挑衅收尾',
    'spin_pre': '旋风起手', 'spin_loop': '龙卷风', 'spin_pst': '旋风急停',
    'spin_pst_loop': '眩晕打转', 'spin_pst_loop_pst': '眩晕恢复',
    'takeoff_pre_vertical': '起飞预备', 'takeoff_vertical': '垂直起飞',
    'takeoff_pre_diagonal': '斜向起飞', 'land': '落地',
    'mossling': '参考姿势', 'misc': '杂项', 'frames': '帧参考',
}


def action_group(name):
    if name.startswith(('sleep', 'frozen', 'shock')):
        return '休息与状态'
    if name.startswith(('walk', 'takeoff', 'land')):
        return '移动与飞行'
    if name.startswith(('atk', 'hit', 'corpse', 'death', 'spin', 'knockback')):
        return '战斗与旋风'
    if name in ('hatch', 'mossling', 'misc', 'frames'):
        return '出场与参考'
    return '日常互动'


def clip_center_x(clip, symbols, hidden):
    """Mean world-space visible x across the clip (pose-independent anchor)."""
    total = 0.0
    count = 0
    for frame in clip['frames']:
        for x, _y in visible_bounds(frame, symbols, hidden, extra_scale(clip)):
            total += x
            count += 1
    return total / count if count else 0.0


def horizontal_offsets(animations, setups):
    """Per-clip world dx aligning its visible center to same-facing idle.

    Native clips live in one shared world space, so wide actions (the diagonal
    takeoff, knockback) sit far from the resting chick inside the shared
    canvas; on a stationary desktop pet that reads as the body teleporting.
    Baking a horizontal offset per clip keeps every action centered on the
    resting pose while preserving each clip's internal motion.
    """
    centers = {(a['name'], a['facing']): a for a in animations}
    reference = {}
    for facing in (5, 8, 2, 255):
        clip = centers.get(('idle', facing))
        if clip is not None:
            symbols, hidden = setups['normal', 'idle']
            reference[facing] = clip_center_x(clip, symbols, hidden)
    fallback = reference.get(5, next(iter(reference.values()), 0.0))
    offsets = {}
    for a in animations:
        if a['name'] == 'idle':
            offsets[id(a)] = 0.0
            continue
        symbols, hidden = setups['normal', a['name']]
        center = clip_center_x(a, symbols, hidden)
        ref = reference.get(a['facing'], fallback)
        offsets[id(a)] = ref - center
    return offsets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--game', type=Path, default=DEFAULT_GAME,
                        help="Path to the local Don't Starve Together installation")
    args = parser.parse_args(argv)
    anim_dir = args.game / 'data' / 'anim'
    if not (anim_dir / 'mossling_build.zip').is_file():
        raise SystemExit(f'No mossling anims under {anim_dir} — pass --game with your '
                         "Don't Starve Together installation path")
    PET_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    print('loading assets...', flush=True)
    animations, base, equipment, names, fx = load_assets(anim_dir)
    base = complete_animation_symbols(base, animations)
    for name in EQUIPMENT_BUILDS:
        equipment[name] = complete_animation_symbols(equipment[name], animations)
    for name in fx:
        fx[name]['symbols'] = complete_animation_symbols(fx[name]['symbols'],
                                                         fx[name]['clips'])
    print(f'clips={len(animations)} body_symbols={len(base)}', flush=True)

    setups = {(skin, a['name']): symbol_setup(skin, a['name'], base, equipment)
              for skin in SKINS for a in animations}

    print('computing per-clip horizontal alignment...', flush=True)
    offsets = horizontal_offsets(animations, setups)
    for a in animations:
        a['dx'] = offsets[id(a)]

    print('measuring bounds...', flush=True)
    points = []
    for a in animations:
        extra = extra_scale(a)
        dx = a['dx']
        for skin in SKINS:
            symbols, hidden = setups[skin, a['name']]
            for frame in a['frames']:
                points.extend((x + dx, y)
                              for x, y in visible_bounds(frame, symbols, hidden, extra))
    left = math.floor(min(x for x, y in points)) - 20
    top = math.floor(min(y for x, y in points)) - 20
    right = math.ceil(max(x for x, y in points)) + 20
    bottom = math.ceil(max(y for x, y in points)) + 20
    scale = min(1.0, 620 / max(right - left, bottom - top))
    canvas = (math.ceil((right - left) * scale), math.ceil((bottom - top) * scale))
    origin_pixels = (-left * scale, -top * scale)
    print(f'bounds=({left},{top})-({right},{bottom}) canvas={canvas} '
          f'scale={scale:.4f}', flush=True)

    manifest = {
        'version': 2, 'fps': 30, 'default_skin': 'normal', 'default_animation': 'idle',
        'canvas': list(canvas), 'origin': list(origin_pixels),
        'skins': {'normal': {'label': '普通鹅崽'}, 'yule': {'label': '圣诞鹅崽'}},
        'animations': {}, 'effects': {},
        'source_scripts': ['prefabs/mossling.lua', 'stategraphs/SGmossling.lua',
                           'stategraphs/commonstates.lua', 'prefabs/sparks.lua',
                           'prefabs/shatter.lua', 'prefabs/mossling_spin_fx.lua'],
    }

    total_frames = 0
    for a in animations:
        name, facing = a['name'], a['facing']
        clip_id = f'{name}__{facing}'
        entry = {'name': name, 'label': LABELS.get(name, name),
                 'group': action_group(name), 'facing': facing,
                 'fps': a['fps'], 'source': a['source'], 'frames': {}}
        for skin in SKINS:
            symbols, hidden = setups[skin, name]
            o = clip_origin(a, origin_pixels, scale)
            s = scale * extra_scale(a)
            images = [render_frame(frame, symbols, canvas, o, hidden, s)
                      for frame in a['frames']]
            entry['frames'][skin] = save_clip_images(skin, clip_id, images, a['fps'])
            total_frames += len(images)
        manifest['animations'][clip_id] = entry
        print(f'rendered {clip_id} ({len(a["frames"])} frames x {len(SKINS)} skins)',
              flush=True)

    # ---- FX layers, same canvas/origin so frames align by path alone ----
    # Each overlay follows the dx of the body clip that triggers it.
    fx_specs = {
        'hit': ('sparks', 'sparks_1', 2, ('hit', 255)),
        'thaw': ('frozen_shatter', 'medium', 1, ('frozen_loop_pst', 255)),
        'spin': ('mossling_spin_fx', 'spin_loop', 1, ('spin_loop', 255)),
    }
    body_by_key = {(a['name'], a['facing']): a for a in animations}
    for effect_name, (asset_name, anim_name, effect_scale, body_key) in fx_specs.items():
        asset = fx[asset_name]
        clip = find_clip(asset['clips'], anim_name, 255)
        body_dx = body_by_key[body_key]['dx'] if body_key in body_by_key else 0.0
        o = tuple(value / (scale * effect_scale) for value in origin_pixels)
        o = (o[0] + body_dx, o[1])
        s = scale * effect_scale
        images = [render_frame(frame, asset['symbols'], canvas, o, set(), s)
                  for frame in clip['frames']]
        folder = FRAMES_DIR / 'effects' / effect_name
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for index, image in enumerate(images):
            path = folder / f'{index:03}.png'
            save_png_atomic(image, path)
            paths.append(path.relative_to(PET_DIR).as_posix())
        manifest['effects'][effect_name] = {
            'frames': paths, 'fps': clip['fps'], 'anchor': 'body',
            'origin': list(origin_pixels),
            'source': f'anim/{asset_name}.zip:{anim_name}',
        }
        print(f'effect {effect_name}: {len(images)} frames', flush=True)

    manifest['statistics'] = {
        'action_names': len({e['name'] for e in manifest['animations'].values()}),
        'directional_clips': len(manifest['animations']),
        'frames_per_skin': sum(len(e['frames'].get('normal', []))
                               for e in manifest['animations'].values()),
        'total_pngs': total_frames,
    }
    (PET_DIR / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Ready', manifest['statistics'], flush=True)


if __name__ == '__main__':
    main()
