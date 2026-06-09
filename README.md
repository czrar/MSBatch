# MSBatch — STEM-HAADF 结构鉴定工具

> 输入元素组成 → 自动检索晶体结构 → STEM 图像模拟 → 与实验图比对 → 确定未知结构

**适用场景**：拿到一张 STEM-HAADF 原子像，知道样品含有哪些元素，但不清楚具体是哪种晶体结构/哪个晶面。MSBatch 帮你从 Materials Project 数据库（15 万+ 材料）检索候选结构，自动模拟 HAADF 图像，与实验图并排对比。

---

## 快速开始（非编程人员）

### 第一步：安装环境

双击项目文件夹中的 `setup.bat`，等待安装完成（约 5-10 分钟，仅需一次）。

### 第二步：启动程序

```bash
env\python.exe gui_main.py
```

或者在命令行中：

```bash
D:\conda_envs\msbatch\python.exe gui_main.py
```

### 第三步：使用流程

1. **输入元素** — 左侧栏填入样品元素（如 `Li, Co, O`），可选填化学计量比、晶面
2. **点击检索** — 自动从 Materials Project 搜索候选结构
3. **浏览候选** — 卡片式展示，每张含晶体信息和 3D 结构缩略图，默认全选
4. **开始模拟** — 自动切面并生成 STEM-HAADF 模拟图
5. **上传实验图** — 与模拟图并排比对，确定最佳匹配
6. **导出报告** — 保存 HTML 报告供分享

---

## 安装指南（编程人员）

### 环境要求

- Windows 10/11
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda
- Python 3.11+
- Materials Project API Key（[免费注册获取](https://materialsproject.org)）

### 手动安装

```bash
# 创建环境
conda create --prefix D:\conda_envs\msbatch python=3.11 -y

# 安装依赖
D:\conda_envs\msbatch\python.exe -m pip install pymatgen mp-api abtem numpy scipy Pillow click PyQt6 py3Dmol pytest pytest-qt PyQt6-WebEngine
```

### 配置 API Key

首次启动 GUI 时，在高级设置中填入 Materials Project API Key。或设置环境变量：

```bash
set MP_API_KEY=your_api_key_here
```

---

## 项目结构

```
MSBatch/
├── gui_main.py                  # GUI 启动入口
├── setup.bat                    # 一键环境安装
├── requirements.txt             # Python 依赖
│
├── gui/                         # PyQt6 图形界面
│   ├── main_window.py           #   主窗口（侧边栏 + 标签页）
│   ├── sidebar.py               #   左侧参数面板
│   ├── candidate_view.py        #   候选结构卡片列表 + 3D 查看器
│   ├── simulation_view.py       #   模拟图像网格
│   ├── comparison_view.py       #   实验图 vs 模拟图对比
│   ├── dialogs.py               #   高级参数设置弹窗
│   └── worker.py                #   后台任务线程
│
├── src/                         # 管道核心模块
│   ├── retriever.py             #   Stage 1: Materials Project 检索
│   ├── slabber.py               #   Stage 2: 表面切面生成
│   ├── simulator.py             #   Stage 3: STEM-HAADF 模拟 (abTEM)
│   └── reporter.py              #   Stage 4: HTML 报告生成
│
├── scripts/                     # CLI 命令行工具
│   ├── run_pipeline.py          #   全管道一键运行
│   └── run_stage.py             #   单阶段分步运行
│
├── config/
│   └── defaults.py              # 默认参数配置
│
├── tests/                       # 单元测试与集成测试 (32 个)
│
└── docs/                        # 文档
    └── superpowers/
        ├── specs/               #   设计文档
        └── plans/               #   实现计划
```

---

## CLI 使用（高级用户）

```bash
# 全管道
python scripts/run_pipeline.py --elements Li,Co,O

# 带计量比筛选 + 指定晶面
python scripts/run_pipeline.py --elements Li,Co,O \
  --stoich "Co:0.15-0.35,O:0.50-0.75" \
  --miller 001,104

# 单阶段分步执行
python scripts/run_stage.py retrieve --elements Li,Co,O
python scripts/run_stage.py slab --candidates data/output/xxx/candidates.json
python scripts/run_stage.py simulate --manifest data/output/xxx/slabs_manifest.json
python scripts/run_stage.py report --candidates data/output/xxx/candidates.json \
  --sim-manifest data/output/xxx/sim_images_manifest.json
```

---

## 常见问题

**Q: 为什么模拟图里看不到轻元素（O、Li）？**
A: HAADF 信号与原子序数的 ~1.7 次方成正比。Co (Z=27) 比 O (Z=8) 亮约 10 倍。这是正确的物理行为，与真实电镜一致。

**Q: 检索返回了相同化学式但不同结构的候选？**
A: 这是本工具的核心功能——同一化学式可能对应多种晶体结构（如层状 vs 尖晶石 LiCoO₂），通过 STEM 图像区分它们。

**Q: 模拟太慢？**
A: 减少候选数（max_candidates）、减少晶面数、或在高级设置中降低 Frozen Phonon 组态数（如 15→5）。后续可支持 GPU 加速。

**Q: 需要 GPU 吗？**
A: 不需要。abTEM 使用 CPU（numba JIT），普通笔记本即可运行。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 界面 | PyQt6 |
| 3D 结构 | py3Dmol + QWebEngineView |
| 模拟引擎 | abTEM 1.0 (multislice + frozen phonon) |
| 材料数据 | Materials Project API v2 (mp-api) |
| 晶体学 | pymatgen |
| 图像处理 | Pillow, NumPy, SciPy |

## 许可与引用

本工具使用的数据来自 [Materials Project](https://materialsproject.org)。发表时请引用其论文。
