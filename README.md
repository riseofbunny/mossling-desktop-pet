# DST 鹅崽桌宠（MosslingDesktopPet）

让《饥荒联机版》的麋鹿鹅幼崽（mossling）住在桌面一角。它会认得轻点、喂食、拖动和靠近，也会自己活动或打个短盹；被击退会踉跄，惹急了会刮起龙卷风。

> 本仓库**只包含代码和构建脚本**。动画帧、manifest.json 等由 `export_mossling.py`
> 从你本机的游戏安装中离线渲染生成（Klei 版权素材，不入库、不分发）。

## 互动一览

- 轻点不同部位、双击触发不同互动：拍翅炫耀、叫妈妈、起飞转圈。
- 按 `F` 喂蔬菜；喂过几次后（活泼亲人模式）有概率触发**龙卷风**彩蛋：
  旋风起手 → 愤怒旋风（换 angry build + 闪电特效）→ 急停 → 眩晕打转 → 恢复。
- 拖动甩动会被击退；向下滚轮三格冻结四秒再碎冰解冻；两秒内轻点四次触发受击火花。
- 右键菜单：喂食、陪伴节奏（活泼亲人/安静陪伴）、自动活动、窗口吸附、
  外观切换（普通/**圣诞**，冬季盛宴 build）、窗口大小、直播采集窗口、退出。
- 倒下后会**破壳重生**；睡觉会贴支撑面，醒来不吞输入。

## 从源码构建

Windows x64、Python 3.12+：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe export_mossling.py --game "C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together"
.\.venv\Scripts\python.exe build_release.py --skip-export
```

一条命令完成“导出 → 打包 → smoke 验证”：

```powershell
.\.venv\Scripts\python.exe build_release.py --game "C:\...Don't Starve Together"
```

产物在 `dist\MosslingDesktopPet\`（exe + `_internal` + manifest.json + frames）。
源码运行（免打包）：

```powershell
python export_mossling.py --game "C:\...Don't Starve Together"
start_pet.bat
```

## 架构

```
export_mossling.py     离线管线：ANIM/BILD/KTEX 解码 → 符号重建 → 换装烘焙 → PNG 帧
MosslingDesktopPet/
├── desktop_pet.py     Qt 主程序：渲染循环、alpha 遮罩点击穿透、吸附维护、输入
├── action_controller.py   动作编排（steps/exit_steps/安全打断，纯 Python 无 Qt）
├── interaction_policy.py  交互节奏策略（冷却、排队、自动小动作、打盹）
├── cursor_play.py     鼠标靠近互动（沿支撑面安全走位）
├── snap_geometry.py   屏幕/任务栏/窗口边缘吸附几何（Win32 枚举）
├── capture_window.py  OBS/直播姬采集窗（固定画布 + 色度键底色）
└── launcher.py        入口（--smoke-test 机器可读自检报告）
```

设计要点（同样适用于其它 DST 生物的桌宠化）：

- **离线烘焙**：运行时不解析游戏格式；缺失符号/装备槽在导出期显式跳过
  （`OPTIONAL_SLOTS`——如 spin 闪电属于独立子实体 `mossling_spin_fx`）。
- **换装 = 符号叠加**：与游戏 `AnimState` 的 Show/Hide/OverrideSymbol 同构；
  圣诞皮肤整体换 `mossling_yule_build`，龙卷风切 `mossling_angry_build`，
  冰冻叠 `swap_frozen` 覆盖。
- **共享画布 + 脚底锚点**：全部 clip 渲染到同一 canvas/origin；吸附锚定
  使用 manifest.origin 推导的**恒定脚底矩形**而非逐帧 alpha 包围盒，
  否则窗口会随动作漂移。
- **逐 clip 横向对齐**：大幅位移动画（斜飞、击退）按可见重心平移回
  待机位置，保留 clip 内部运动。
- **安全打断**：loop/hold 动作收到新意图时必须走 `exit_steps`
  （醒来/落地/眩晕恢复永不被跳过）。

## 许可与素材

MIT 许可只覆盖本项目原创代码。兔人/麋鹿鹅角色、动画帧等《饥荒联机版》
素材归 Klei Entertainment 所有——请阅读
[Klei 玩家创作指南](https://support.klei.com/hc/en-us/articles/360029880791-Player-Creation-Guidelines)
与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。这是免费、非商业的同人
项目，与 Klei Entertainment 无关，也未获其背书。

架构灵感来自 [bunnyman-desktop-pet](https://github.com/hydrangeia/bunnyman-desktop-pet)
（兔人桌宠），其运行时模块以 MIT 许可发布。
