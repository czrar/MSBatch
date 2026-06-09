# MSBatch GUI — 设计文档

## 概述

为 MSBatch STEM-HAADF 结构鉴定管道开发 PyQt6 桌面 GUI，让非编程人员（材料/电镜实验人员）能通过图形界面完成"元素输入 → 候选检索 → 切面模拟 → 报告比对"全流程。

## 核心设计原则

- **分步可视**：Step 1→2→3→4，每步状态清晰（检索/候选/模拟/对比）
- **后台不卡 UI**：所有管道操作用 QThread 异步执行
- **零 CLI 接触**：用户不需要打开终端，不需要写命令
- **可移植**：拷贝文件夹到任何 Windows 机器，`setup.bat` 一键装好环境即可用

## 技术选型

| 组件 | 技术 | 原因 |
|------|------|------|
| GUI 框架 | PyQt6 | 原生 Windows 控件，稳定成熟 |
| 3D 结构 | py3Dmol + QWebEngineView | 卡片中嵌入可旋转晶体结构 |
| 图像显示 | QLabel + QPixmap | 内置支持 PNG，点击弹出放大 |
| 后台任务 | QThread + signal/slot | 管道路四阶段异步执行 |
| 管道模块 | 复用 src/ | 零改动，直接 import |
| 配置 | JSON 用户目录 | 可移植，不写死路径 |

## 文件结构

```
MSBatch/
  gui/
    __init__.py
    main_window.py       # 主窗口容器
    sidebar.py           # 左侧参数面板
    candidate_view.py    # 候选卡片列表
    simulation_view.py   # 模拟图像网格
    comparison_view.py   # 实验图 vs 模拟图对比
    worker.py            # QThread 后台任务
    dialogs.py           # 高级参数设置弹窗
  gui_main.py            # 启动入口: python gui_main.py
  setup.bat              # 一键环境安装
  config/
    defaults.py          # 出厂默认参数（只读）
  src/                   # 现有管道模块（不动）
```

## 界面布局

```
┌──────────────────────────────────────────────────────┐
│  MSBatch — STEM-HAADF Structure Identification    │
├──────────────┬───────────────────────────────────────┤
│  侧边栏 240px │  右侧主区域                          │
│              │  ┌──────────────────────────────────┐ │
│  Step 1      │  │ [候选结构] [模拟图像] [对比报告]   │ │
│  元素检索     │  └──────────────────────────────────┘ │
│  ┌─────────┐ │                                       │
│  │元素     │ │  ┌─────────────────────────────────┐  │
│  │计量比   │ │  │ ✅ 检索完成 | 3个候选 | Li-Co-O │  │
│  │晶面     │ │  └─────────────────────────────────┘  │
│  │候选数   │ │                                       │
│  └─────────┘ │  ┌───┐ ┌──────────────────────────┐  │
│  [开始检索]  │  │3D │ │ LiCoO₂     mp-12345 #1  ✓│  │
│              │  │缩 │ │ R-3m  trigonal          │  │
│  Step 2      │  │略 │ │ 形成能 -1.85  Hull 0.00  │  │
│  选择候选     │  │图 │ │ 带隙 3.2  位点 4        │  │
│  找到 3 个    │  └───┘ └──────────────────────────┘  │
│              │                                       │
│  Step 3      │  ┌───┐ ┌──────────────────────────┐  │
│  模拟 & 对比  │  │3D │ │ LiCoO₂     mp-54321 #2  ✓│  │
│  [开始模拟]  │  │缩 │ │ Fd-3m  cubic            │  │
│  3/6 已模拟  │  │略 │ │ 形成能 -1.70  Hull 0.15  │  │
│              │  │图 │ │ 带隙 2.8  位点 4        │  │
│  Step 4      │  └───┘ └──────────────────────────┘  │
│  实验图       │                                       │
│  [拖入图片]  │                                       │
│              │                                       │
│  ⚙ 高级设置  │                                       │
└──────────────┴───────────────────────────────────────┘
```

## 操作流程

### Step 1: 元素检索
- 输入：元素（逗号分隔）、计量比范围（可选）、晶面（可选）、最大候选数
- 点击"开始检索"→ 后台调用 `MPRetriever.retrieve_elements()`
- 状态栏实时显示进度
- 完成 → 候选卡片列表出现

### Step 2: 浏览候选
- 每张卡片：3D 结构缩略图（py3Dmol）+ 材料属性（空间群、晶系、形成能、Hull、带隙、位点数）
- 右上角勾选框（默认全选），可取消不需要的结构
- 点击缩略图 → 弹出可旋转 3D 结构查看器
- 状态栏显示候选总数和已选数量

### Step 3: 模拟
- 点击"开始模拟"→ 后台循环：`SlabBuilder.build()` → `STEMSimulator.simulate()`
- 每个候选 × 每个晶面 = N 张模拟图
- 进度条：`模拟中 3/12 (mp-12345 001)`
- 完成 → 自动切到"模拟图像"标签页

### Step 4: 对比报告
- "模拟图像"标签页：网格排列所有模拟 HAADF 图，标注 (hkl) 和 mp-id
- 点击单张 → 弹出放大查看
- 上传实验图（拖入或浏览文件）
- "对比报告"标签页：实验图固定左侧，模拟图网格右侧，人眼比对
- 底部有"导出 HTML 报告"按钮调用 `Reporter.generate()`

## 高级参数设置弹窗

点击侧边栏 "⚙ 高级设置" 弹出模态对话框：

```
┌─────────────────────────────────────────┐
│  高级模拟参数                     [关闭] │
├─────────────────────────────────────────┤
│  Slab 参数                              │
│    最小板厚: [12.0] Å   真空层: [15.0] Å │
│                                         │
│  电子光学                               │
│    加速电压: [200] kV  会聚角: [22] mrad│
│    Cs: [0.001] mm      欠焦: [0.0] nm  │
│                                         │
│  HAADF 探测器                           │
│    内角: [60] mrad     外角: [200] mrad │
│    像素尺寸: [0.1] Å                    │
│                                         │
│  热漫散射 (TDS)                          │
│    Frozen Phonon: [15]  热振动: [0.075]  │
│                                         │
│         [恢复默认值]         [保存设置]   │
└─────────────────────────────────────────┘
```

各参数说明：
- **Slab 参数**：控制 slab 厚度和真空层，影响图像中结构对比度
- **电子光学**：显微镜核心参数，对应 abTEM Probe 设置
- **HAADF 探测器**：环形探测器角度范围，决定 Z 衬度强度
- **热漫散射**：Frozen phonon 组态数越多图像越真实但越慢

## 可移植性

### 环境安装 (setup.bat)
```batch
@echo off
echo === MSBatch Environment Setup ===
conda create --prefix "%~dp0env" python=3.11 -y
call "%~dp0env\python.exe" -m pip install pymatgen mp-api abtem numpy scipy Pillow click requests pyqt6 py3dmol
echo === Setup Complete ===
pause
```

### 配置管理
- API key 从 `%USERPROFILE%\.msbatch\config.json` 读取
- 如果文件不存在 → 首次启动弹出设置向导：输入 API Key、默认输出路径
- 模拟参数也保存在用户目录，修改后持久化，不影响多人共用同一份程序
- `config/defaults.py` 提供出厂默认值，作为只读参考

### 路径计算
- 所有路径相对于 `gui_main.py` 所在目录（`Path(__file__).resolve().parent`）
- 不依赖绝对路径，不写死盘符
- 输出目录默认 `./data/output/`（可配置）

### Python 环境
- 启动入口 `gui_main.py` 顶部检查 Python 版本和关键 import
- 缺依赖时弹窗提示并引导运行 `setup.bat`

## 数据流

```
用户输入 → Sidebar
    │
    ├─→ Worker.retrieve()  [QThread]
    │       └→ MPRetriever.retrieve_elements()
    │              └→ signal: candidates_ready → CandidateView 显示
    │
    ├─→ Worker.simulate()  [QThread]
    │       └→ for each (candidate, miller):
    │              SlabBuilder.build() → CIF
    │              STEMSimulator.simulate() → PNG
    │              signal: progress_update → Sidebar 进度条
    │       └→ signal: simulation_done → SimulationView 显示
    │
    └─→ Reporter.generate()
            └→ 自包含 HTML 报告
```

## 依赖清单

```
# 现有（不变）
pymatgen, mp-api, abtem, numpy, scipy, Pillow, click

# GUI 新增
pyqt6          # 桌面框架
pyqtdarktheme  # 可选暗色主题

# 3D 结构
py3dmol        # 嵌入晶体结构查看
```

## 未列入范围
- PyInstaller 打包独立 EXE（用户否定）
- 多人协作 / 服务端部署
- 自动图像匹配算法
- Mac/Linux 支持（仅 Windows）
