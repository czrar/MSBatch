# STEM-HAADF 结构鉴定管道 — 设计文档

## 概述

**问题**：已知元素组成，拿到 STEM-HAADF 原子像后无法确定材料的具体结构和晶面。需要从 Materials Project 数据库检索候选结构，生成 STEM 模拟图像，供人眼与实验图像比对鉴定。

**适用范围**：任意无机晶体材料（不只 LiCoO₂），全元素系统通用。

## 架构

分阶段管道，每阶段独立可运行，中间结果落盘缓存：

```
输入(元素+计量比+晶面) → Stage1(MP检索) → Stage2(切面) → Stage3(STEM模拟) → Stage4(报告)
                                  ↓               ↓               ↓
                            candidates.json   slabs_manifest   sim_manifest
                                  +              *.cif           *.png
```

### 模块划分

| 模块 | 文件 | 职责 |
|------|------|------|
| `Config` | `config/defaults.py` | 全局默认参数（API key, 模拟参数等） |
| `MPRetriever` | `src/retriever.py` | MP API 检索 + 排序 + 缓存 |
| `SlabBuilder` | `src/slabber.py` | 切面生成 + 超胞扩展 + CIF 导出 |
| `STEMSimulator` | `src/simulator.py` | MULTEM HAADF 模拟 |
| `Reporter` | `src/reporter.py` | HTML 报告生成 |
| CLI | `scripts/run_pipeline.py` | 命令行入口 |

## Stage 1: MP Retriever

### 输入
```python
# 方式1: 纯元素
MPRetriever(elements=["Li", "Co", "O"])

# 方式2: 元素 + 计量比范围
MPRetriever(elements=["Li", "Co", "O"],
             stoichiometry={"Co": (0.8, 1.2), "O": (1.8, 2.2)},
             max_candidates=50)

# 方式3: 化学式字符串（精确匹配）
MPRetriever(formula="LiCoO2")
```

### 处理逻辑
1. 调 `materials/summary/` 搜索含所有指定元素的结构
2. 客户端过滤化学计量比范围（MP API 无原生支持）
3. 按 `energy_above_hull` 升序排列
4. 不去重——同一化学式的不同结构都保留（不同 mp-id），这是项目的核心需求
5. 只拉必要字段，避免带宽浪费

### 输出 `candidates.json`
```json
{
  "query": {
    "elements": ["Li", "Co", "O"],
    "stoichiometry": {"Co": [0.8, 1.2], "O": [1.8, 2.2]},
    "timestamp": "2026-06-08T14:30:00"
  },
  "candidates": [
    {
      "rank": 1,
      "material_id": "mp-12345",
      "formula_pretty": "LiCoO2",
      "formation_energy_per_atom": -1.85,
      "energy_above_hull": 0.0,
      "band_gap": 3.2,
      "space_group": "R-3m",
      "crystal_system": "trigonal",
      "n_sites": 4,
      "structure_cif": "<CIF string>"
    }
  ]
}
```

### 查询字段
`material_id`, `formula_pretty`, `formation_energy_per_atom`, `energy_above_hull`, `band_gap`, `structure`, `space_group`, `crystal_system`, `nsites`

## Stage 2: Slab Builder

### 输入
- `candidates.json`（可限定只处理 rank 前 N 个）
- 晶面参数：
  - 默认自动：`[(0,0,1), (1,0,0), (1,1,0), (1,1,1)]`
  - 用户可追加：如 `[(1,0,4)]`
  - 或完全手动指定晶面列表

### 处理逻辑
1. 从 CIF 构建 `pymatgen.Structure`
2. 用 `SlabGenerator` 切 slab，自动处理对称等价面去重
3. 超胞扩展（xy 方向保证模拟视场，z 方向默认 10-20 Å slab + 15 Å 真空层）
4. 输出 CIF 文件

### 输出
```
slabs/
  mp-12345_LiCoO2/
    mp-12345_001.cif
    mp-12345_100.cif
    mp-12345_110.cif
    mp-12345_104.cif
slabs_manifest.json
```

### `slabs_manifest.json`
```json
{
  "slabs": [
    {
      "material_id": "mp-12345",
      "miller_index": [0, 0, 1],
      "cif_path": "slabs/mp-12345_LiCoO2/mp-12345_001.cif",
      "slab_thickness_A": 12.3,
      "vacuum_A": 15.0,
      "supercell": [2, 2, 1]
    }
  ]
}
```

## Stage 3: STEM Simulator

### 依赖
- py_multem（Python 绑定 MULTEM）

### 模拟参数（带物理正确配置）
```python
sim_config = {
    # 几何参数
    "accelerating_voltage_kV": 200,
    "semi_angle_mrad": 22,
    "HAADF_inner_mrad": 60,
    "HAADF_outer_mrad": 200,
    "probe_defocus_nm": 0.0,
    "spherical_aberration_mm": 0.001,
    "pixel_size_A": 0.1,

    # Z 衬度关键参数（确保轻元素不出现在 HAADF 图中）
    "frozen_phonon_configs": 15,
    "include_tds": True,
    "thermal_sigma_A": 0.075,
    "seed": 42,
}
```

### 处理逻辑
1. 从 CIF 读结构 → 提取原子序号、位置、占位
2. 构建 MULTEM 输入
3. 跑 multislice + frozen phonon 模拟
4. 渲染 HAADF 强度图为 PNG

### 输出
```
sim_images/
  mp-12345_LiCoO2/
    mp-12345_001_HAADF.png
    mp-12345_100_HAADF.png
    mp-12345_110_HAADF.png
    mp-12345_104_HAADF.png
sim_images_manifest.json
```

## Stage 4: Report Generator

### 输出
自包含 HTML 文件 `report.html`，浏览器直接打开。

### 报告结构
- 顶部：查询摘要（元素、计量比、晶面、模拟参数、候选数）
- 主体：每个候选一张卡片
  - 材料信息：化学式、mp-id、形成能、能量距 hull、空间群
  - 各晶面 HAADF 模拟图网格（标注 Millier 指数 + slab 厚度）
  - 点击图片可放大
- 底部：实验图区域（路径指定或拖入占位符）

### 设计原则
- 报告不做自动匹配——自动匹配不可靠且用户已明确表示自己判断
- 报告的目标是让"人眼对比"尽可能高效：按形成能排序，模拟图与结构信息并列一目了然

## 项目结构
```
MSBatch/
  src/
    __init__.py
    retriever.py      # Stage 1: MP 检索
    slabber.py        # Stage 2: 切面生成
    simulator.py      # Stage 3: MULTEM 模拟
    reporter.py       # Stage 4: HTML 报告
  config/
    defaults.py       # 全局默认参数
  scripts/
    run_pipeline.py   # CLI 全管道
    run_stage.py      # CLI 单阶段
  data/
    output/           # 运行输出目录（按时间戳命名）
      YYYYMMDD_HHMMSS/
        candidates.json
        slabs/
        sim_images/
        report.html
  docs/
    superpowers/
      specs/
```

## 依赖
```
pymatgen
mp-api
py_multem
numpy
scipy
click (CLI)
```

## 用户交互方式

### 完整管道
```bash
python scripts/run_pipeline.py --elements Li,Co,O --stoich "Co:0.8-1.2,O:1.8-2.2"
```

### 单阶段
```bash
python scripts/run_stage.py retrieve --elements Li,Co,O
python scripts/run_stage.py slab --candidates data/output/xxx/candidates.json --miller 001,100,110,111,104
python scripts/run_stage.py simulate --manifest data/output/xxx/slabs_manifest.json
python scripts/run_stage.py report --sim-manifest data/output/xxx/sim_images_manifest.json
```

## 未列入范围
- GUI（后续考虑）
- 自动图像匹配/比对（用户明确表示自己判断）
- 远程服务器执行（暂无 GPU 服务器）
- 非晶/缺陷结构支持（仅晶体材料）
