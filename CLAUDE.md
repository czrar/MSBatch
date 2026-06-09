# MSBatch — STEM-HAADF 结构鉴定管道

## Python 环境
- Conda 环境: `D:\conda_envs\msbatch`
- Python: `D:\conda_envs\msbatch\python.exe`
- 原 mlp_env 仅用于 LiCoO₂ 项目

## 项目结构
- `src/` — Python 源码 (retriever, slabber, simulator, reporter)
- `scripts/` — CLI 脚本 (run_pipeline.py, run_stage.py)
- `data/output/` — 管道输出目录（按时间戳命名）
- `config/` — 默认参数（API key, 模拟参数等）
- `tests/` — 单元测试和集成测试
- `docs/superpowers/specs/` — 设计文档
- `docs/superpowers/plans/` — 实现计划

## Materials Project API
- Key: `3sDGIETDr7oH5nrQ1UP4aSczKFXJHQcC`
- 使用 `mp_api.client.MPRester`
- REST 备用: `https://api.materialsproject.org` + `X-API-KEY` header

## 依赖
- pymatgen, mp-api, python-multem, numpy, scipy, Pillow, click
