"""Complete mossling actions and their safe interruption points, independent of Qt.

Game clips checked against stategraphs/SGmossling.lua and
stategraphs/commonstates.lua. Logical keys keep the desktop pet's stable names
where the interaction policy and smoke test reference them; the underlying
clips are mossling's own. The pet's spin attack is the game's full whirlwind
chain (spin_pre -> spin_loop[angry build] -> spin_pst -> dizzy -> recovery).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    clip: str
    mode: str = 'once'


@dataclass(frozen=True)
class ActionSpec:
    label: str
    group: str
    steps: tuple[Step, ...]
    exit_steps: tuple[Step, ...] = ()


def _steps(*names):
    return tuple(Step(name) for name in names)


def _catalog(idle):
    return {
        'idle': ActionSpec('待机', '日常互动', (Step(idle, 'loop'),)),
        # SGmossling "taunt" is the happy wing-flap; used for joy reactions.
        'happy': ActionSpec('拍翅开心', '日常互动', _steps('taunt_pre', 'taunt', 'taunt_pst')),
        # SGmossling "meep" honks for the mother; the pet's affection reaction.
        'earrub': ActionSpec('叫妈妈', '日常互动', _steps('meep')),
        # Take off, flap a full climb, and land again.
        'dance': ActionSpec('起飞转圈', '日常互动',
                            _steps('takeoff_pre_vertical', 'takeoff_vertical', 'land')),
        'eat': ActionSpec('吃食', '日常互动', _steps('action', 'eat'), _steps('eat_pst')),
        'meep': ActionSpec('叫妈妈', '日常互动', _steps('meep')),
        'hatch': ActionSpec('破壳出生', '出场与变化', _steps('hatch')),
        'sleep': ActionSpec('睡觉', '休息与状态',
                            (Step('sleep_pre'), Step('sleep_loop', 'loop')), _steps('sleep_pst')),
        'wake': ActionSpec('醒来', '休息与状态', (Step(idle, 'loop'),)),
        'freeze': ActionSpec('冰冻', '休息与状态',
                             (Step('frozen', 'hold'),), _steps('frozen_loop_pst')),
        'thaw': ActionSpec('解冻', '休息与状态', (Step(idle, 'loop'),)),
        'shock': ActionSpec('触电', '休息与状态',
                            (Step('shock_loop', 'loop'),), _steps('shock_pst')),
        'walk': ActionSpec('走路', '移动与飞行',
                           (Step('walk_pre'), Step('walk_loop', 'loop')), _steps('walk_pst')),
        'jump': ActionSpec('斜飞掠过', '移动与飞行',
                           _steps('takeoff_pre_diagonal', 'land')),
        'attack': ActionSpec('啄击', '战斗与旋风', _steps('atk')),
        # Policy compatibility key: mossling pecks instead of swinging a pillow.
        'attack_pillow': ActionSpec('啄击', '战斗与旋风', _steps('atk')),
        'hit': ActionSpec('受击', '战斗与旋风', _steps('hit')),
        # SGmossling has no hit_big; the heavy reaction is the knockback.
        'hit_big': ActionSpec('被击退', '战斗与旋风', _steps('knockback')),
        'death': ActionSpec('倒下', '战斗与旋风',
                            (Step('death'), Step('corpse', 'hold')),
                            _steps('hatch')),
        # The signature whirlwind: angry build spin, then dizzy recovery.
        'spin_attack': ActionSpec('龙卷风', '战斗与旋风',
                                  (Step('spin_pre'), Step('spin_loop', 'loop')),
                                  _steps('spin_pst', 'spin_pst_loop', 'spin_pst_loop_pst')),
    }


ALIASES = {
    'idle': 'idle',
    'taunt_pre': 'happy', 'taunt': 'happy', 'taunt_pst': 'happy',
    'meep': 'earrub',
    'action': 'eat', 'eat': 'eat', 'eat_pst': 'idle',
    'sleep_pre': 'sleep', 'sleep_loop': 'sleep', 'sleep_pst': 'wake',
    'walk_pre': 'walk', 'walk_loop': 'walk', 'walk_pst': 'idle',
    'frozen': 'freeze', 'frozen_loop_pst': 'thaw',
    'shock_loop': 'shock', 'shock_pst': 'idle',
    'takeoff_pre_vertical': 'dance', 'takeoff_vertical': 'dance', 'land': 'idle',
    'takeoff_pre_diagonal': 'jump',
    'atk': 'attack',
    'hit': 'hit', 'knockback': 'hit_big',
    'death': 'death', 'corpse': 'death', 'corpse_hit': 'death',
    'hatch': 'idle',
    'spin_pre': 'spin_attack', 'spin_loop': 'spin_attack', 'spin_pst': 'spin_attack',
    'spin_pst_loop': 'spin_attack', 'spin_pst_loop_pst': 'spin_attack',
}


class ActionController:
    """Queue the latest intention and finish physical recovery before switching.

    request() returns a Step only when playback may change immediately. Otherwise
    the renderer finishes the current clip, then calls finish_clip(), including
    at loop boundaries. Requests during finite sequences replace the pending
    destination; they never discard a wake, landing, or dizzy recovery segment.
    """
    def __init__(self, available_names, default_idle='idle', initial_clip=None):
        self.available = set(available_names)
        self.default_idle = default_idle
        if default_idle not in self.available:
            raise ValueError('The default idle clip is required')
        catalog = _catalog(default_idle)
        # The whirlwind needs its complete native chain.
        spin_clips = {'spin_pre', 'spin_loop', 'spin_pst', 'spin_pst_loop',
                      'spin_pst_loop_pst'}
        if not spin_clips <= self.available:
            catalog.pop('spin_attack', None)
        if 'land' not in self.available:
            for key in ('dance', 'jump'):
                spec = catalog.get(key)
                if spec is not None and any(s.clip == 'land' for s in spec.steps):
                    catalog.pop(key, None)
        if 'eat_pst' not in self.available:
            spec = catalog.get('eat')
            if spec is not None:
                catalog['eat'] = ActionSpec(spec.label, spec.group, spec.steps)
        self.actions = {
            key: spec for key, spec in catalog.items()
            if all(s.clip in self.available for s in spec.steps + spec.exit_steps)
        }
        self.active_action = 'idle'
        self.pending_action = None
        self._stage = 'body'
        self._remaining = []
        self.current = Step(default_idle, 'loop')
        if initial_clip and initial_clip != default_idle:
            self._resume_clip(initial_clip)

    @property
    def action_ids(self):
        return list(self.actions)

    def _begin(self, action):
        if action in ('wake', 'thaw'):
            action = 'idle'
        self.active_action = action
        self._stage = 'body'
        self._remaining = list(self.actions[action].steps)
        self.current = self._remaining.pop(0)
        return self.current

    def _resume_clip(self, clip):
        if clip not in self.available:
            raise ValueError(f'Unknown initial clip: {clip}')
        if clip == 'corpse_hit' and 'death' in self.actions:
            self.actions['_preview'] = ActionSpec(
                '倒地预览收尾', '开发预览', (Step(clip), Step('corpse', 'hold')),
                self.actions['death'].exit_steps)
            self.active_action = '_preview'
            self.current = Step(clip)
            self._remaining = [Step('corpse', 'hold')]
            return
        # Raw previews can end in a sleeping, frozen, or airborne pose. Infer
        # the appropriate recovery rather than treating every pose as standing.
        preferred = {
            'sleep_pre': 'sleep', 'sleep_loop': 'sleep', 'sleep_pst': 'sleep',
            'walk_pre': 'walk', 'walk_loop': 'walk', 'walk_pst': 'walk',
            'frozen': 'freeze', 'frozen_loop_pst': 'freeze',
            'shock_loop': 'shock', 'shock_pst': 'shock',
            'takeoff_pre_vertical': 'dance', 'takeoff_vertical': 'dance',
            'takeoff_pre_diagonal': 'jump', 'land': 'jump',
            'atk': 'attack',
            'death': 'death', 'corpse': 'death',
            'spin_pre': 'spin_attack', 'spin_loop': 'spin_attack',
            'spin_pst': 'spin_attack', 'spin_pst_loop': 'spin_attack',
            'spin_pst_loop_pst': 'spin_attack',
        }.get(clip)
        if preferred in self.actions:
            self.active_action = preferred
            spec = self.actions[preferred]
            for stage, steps in [('body', spec.steps), ('exit', spec.exit_steps)]:
                for index, step in enumerate(steps):
                    if step.clip == clip:
                        self._stage = stage
                        self.current = step
                        self._remaining = list(steps[index + 1:])
                        return
        # Unclassified previews still finish their current clip before returning.
        self.actions['_preview'] = ActionSpec('预览收尾', '开发预览', (Step(clip),))
        self.active_action = '_preview'
        self.current = Step(clip)

    def request(self, action):
        action = ALIASES.get(action, action)
        if action not in self.actions:
            raise ValueError(f'Unknown or unavailable action: {action}')
        # Wake/thaw are intentions to stand, not free-standing wake animations.
        if action in ('wake', 'thaw'):
            action = 'idle'
        if action == self.active_action and self._stage == 'body':
            self.pending_action = None
            return None
        self.pending_action = action
        if self.active_action == 'idle':
            self.pending_action = None
            return self._begin(action)
        if self.current.mode == 'hold':
            return self._start_exit()
        return None

    def _complete(self):
        destination = self.pending_action or 'idle'
        self.pending_action = None
        return self._begin(destination)

    def _start_exit(self):
        self._stage = 'exit'
        exit_steps = self.actions[self.active_action].exit_steps
        self._remaining = list(exit_steps)
        if not self._remaining:
            return self._complete()
        self.current = self._remaining.pop(0)
        return self.current

    def finish_clip(self):
        if self.current.mode == 'hold':
            return self.current
        if self.current.mode == 'loop':
            if self.pending_action is None:
                return self.current
            return self._start_exit()
        if self._remaining:
            # An interrupted entry may go straight to its exit once the entry
            # finishes. The resting/airborne/dizzy state is never replaced by idle.
            if (self._stage == 'body' and self.pending_action is not None
                    and self._remaining[0].mode in ('loop', 'hold')):
                return self._start_exit()
            self.current = self._remaining.pop(0)
            return self.current
        if self._stage == 'exit':
            return self._complete()
        return self._start_exit()
