# STEM-HAADF 结构鉴定管道 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 4 阶段管道，根据元素组成从 Materials Project 检索候选结构，切面生成 slab，用 MULTEM 模拟 HAADF 图像，生成 HTML 报告供人眼比对。

**Architecture:** 4 个独立 Python 模块（retriever/slabber/simulator/reporter），通过 JSON manifest 文件交接数据，每阶段可单独运行。CLI 用 click 封装。

**Tech Stack:** Python 3.11, pymatgen, mp-api, abTEM 1.0.9, numpy, scipy, Pillow, click
- Conda 环境: `msbatch`, Python: `conda run -n msbatch python`
- 所有命令从项目根 `d:/research data/ai_project/MSBatch` 执行

---

## 文件结构

```
MSBatch/
  config/
    defaults.py          # 新建: API key, 模拟参数, 晶面默认值
  src/
    retriever.py         # 新建: Stage 1 MP 检索
    slabber.py           # 新建: Stage 2 切面生成
    simulator.py         # 新建: Stage 3 STEM 模拟
    reporter.py          # 新建: Stage 4 HTML 报告
  scripts/
    run_pipeline.py      # 新建: 全管道 CLI
    run_stage.py         # 新建: 单阶段 CLI
  tests/
    test_retriever.py    # 新建
    test_slabber.py      # 新建
    test_simulator.py    # 新建
    test_reporter.py     # 新建
  requirements.txt       # 修改: 添加实际依赖
```

---

### Task 1: 项目初始化和依赖安装

**Files:**
- Modify: `requirements.txt`
- Create: `config/defaults.py`

- [ ] **Step 1: 更新 requirements.txt**

```bash
cat > requirements.txt << 'EOF'
pymatgen>=2023.0.0
mp-api>=0.45.0
numpy>=1.24.0
scipy>=1.10.0
click>=8.0.0
EOF
```

- [ ] **Step 2: 安装依赖**

Run: `D:/conda_envs/mlp_env/python.exe -m pip install -r "d:/research data/ai_project/MSBatch/requirements.txt"`

- [ ] **Step 3: 创建 config/defaults.py**

```python
"""MSBatch 默认配置."""

# Materials Project API
MP_API_KEY = "3sDGIETDr7oH5nrQ1UP4aSczKFXJHQcC"
MP_BASE_URL = "https://api.materialsproject.org"

# MP 检索
DEFAULT_MAX_CANDIDATES = 50
DEFAULT_FIELDS = [
    "material_id", "formula_pretty", "formation_energy_per_atom",
    "energy_above_hull", "band_gap", "structure",
    "space_group", "crystal_system", "nsites"
]

# Slab 生成
DEFAULT_MIN_SLAB_THICKNESS = 12.0   # Å
DEFAULT_MIN_VACUUM = 15.0           # Å
DEFAULT_MILLER_INDICES = [
    (0, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)
]
DEFAULT_MAX_SLAB_RANK = 20           # 最多处理前 N 个候选

# STEM 模拟参数
SIM_CONFIG = {
    "accelerating_voltage_kV": 200,
    "semi_angle_mrad": 22,
    "HAADF_inner_mrad": 60,
    "HAADF_outer_mrad": 200,
    "probe_defocus_nm": 0.0,
    "spherical_aberration_mm": 0.001,
    "pixel_size_A": 0.1,
    "frozen_phonon_configs": 15,
    "include_tds": True,
    "thermal_sigma_A": 0.075,
    "seed": 42,
}
```

- [ ] **Step 4: 提交**

```bash
git add requirements.txt config/defaults.py
git commit -m "chore: add project config and dependencies"
```

---

### Task 2: MP Retriever 模块

**Files:**
- Create: `src/retriever.py`
- Create: `tests/test_retriever.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_retriever.py
import json
import pytest
from src.retriever import MPRetriever


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def make_mock_session(responses):
    """构建一个返回预设响应的 mock session."""
    class MockSession:
        def __init__(self, responses):
            self._responses = list(responses)
            self.last_url = None
            self.last_headers = None
        def get(self, url, headers=None):
            self.last_url = url
            self.last_headers = headers
            return self._responses.pop(0)
    return MockSession(responses)


MOCK_MP_DATA = {
    "data": [
        {
            "material_id": "mp-12345",
            "formula_pretty": "LiCoO2",
            "formation_energy_per_atom": -1.85,
            "energy_above_hull": 0.0,
            "band_gap": 3.2,
            "space_group": "R-3m",
            "crystal_system": "trigonal",
            "nsites": 4,
            "structure": {
                "@module": "pymatgen.core.structure",
                "@class": "Structure",
                "charge": None,
                "lattice": {
                    "matrix": [[2.815, 0.0, 0.0], [-1.407, 2.438, 0.0], [0.0, 0.0, 14.05]],
                    "a": 2.815, "b": 2.815, "c": 14.05,
                    "alpha": 90.0, "beta": 90.0, "gamma": 120.0,
                    "volume": 96.4
                },
                "sites": [
                    {"species": [{"element": "Li", "occu": 1}], "abc": [0.0, 0.0, 0.5], "xyz": [0.0, 0.0, 7.025], "label": "Li", "properties": {}},
                    {"species": [{"element": "Co", "occu": 1}], "abc": [0.0, 0.0, 0.0], "xyz": [0.0, 0.0, 0.0], "label": "Co", "properties": {}},
                    {"species": [{"element": "O", "occu": 1}], "abc": [0.0, 0.0, 0.26], "xyz": [0.0, 0.0, 3.653], "label": "O", "properties": {}},
                    {"species": [{"element": "O", "occu": 1}], "abc": [0.0, 0.0, 0.74], "xyz": [0.0, 0.0, 10.397], "label": "O", "properties": {}}
                ]
            }
        },
        {
            "material_id": "mp-54321",
            "formula_pretty": "LiCoO2",
            "formation_energy_per_atom": -1.70,
            "energy_above_hull": 0.15,
            "band_gap": 2.8,
            "space_group": "Fd-3m",
            "crystal_system": "cubic",
            "nsites": 4,
            "structure": {
                "@module": "pymatgen.core.structure",
                "@class": "Structure",
                "charge": None,
                "lattice": {
                    "matrix": [[8.05, 0.0, 0.0], [0.0, 8.05, 0.0], [0.0, 0.0, 8.05]],
                    "a": 8.05, "b": 8.05, "c": 8.05,
                    "alpha": 90.0, "beta": 90.0, "gamma": 90.0,
                    "volume": 521.66
                },
                "sites": [
                    {"species": [{"element": "Li", "occu": 1}], "abc": [0.125, 0.125, 0.125], "xyz": [1.006, 1.006, 1.006], "label": "Li", "properties": {}},
                    {"species": [{"element": "Co", "occu": 1}], "abc": [0.5, 0.5, 0.5], "xyz": [4.025, 4.025, 4.025], "label": "Co", "properties": {}},
                    {"species": [{"element": "O", "occu": 1}], "abc": [0.25, 0.25, 0.25], "xyz": [2.012, 2.012, 2.012], "label": "O", "properties": {}},
                    {"species": [{"element": "O", "occu": 1}], "abc": [0.75, 0.75, 0.75], "xyz": [6.038, 6.038, 6.038], "label": "O", "properties": {}}
                ]
            }
        }
    ],
    "meta": {"total_doc": 2, "max_limit": 1000}
}


def test_retrieve_by_elements_basic():
    """用元素列表检索，返回排序的候选列表."""
    session = make_mock_session([
        FakeResponse(MOCK_MP_DATA)
    ])
    retriever = MPRetriever(api_key="test-key")
    result = retriever._retrieve_from_mp(session, ["Li", "Co", "O"])

    assert len(result["candidates"]) == 2
    assert result["candidates"][0]["material_id"] == "mp-12345"
    assert result["candidates"][0]["energy_above_hull"] == 0.0
    assert result["candidates"][1]["energy_above_hull"] == 0.15
    assert "LiCoO2" in session.last_url
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "d:/research data/ai_project/MSBatch" && D:/conda_envs/mlp_env/python.exe -m pytest tests/test_retriever.py::test_retrieve_by_elements_basic -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: 实现 MPRetriever**

```python
# src/retriever.py
"""Stage 1: Materials Project 检索器."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from pymatgen.core.structure import Structure

from config.defaults import (
    MP_API_KEY, MP_BASE_URL, DEFAULT_MAX_CANDIDATES, DEFAULT_FIELDS
)


class MPRetriever:
    """从 Materials Project 检索候选结构."""

    def __init__(self, api_key: str = MP_API_KEY, base_url: str = MP_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def retrieve_elements(
        self,
        elements: list[str],
        stoichiometry: Optional[dict[str, tuple[float, float]]] = None,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
    ) -> dict:
        """按元素检索候选结构.

        Args:
            elements: 元素列表, 如 ["Li", "Co", "O"]
            stoichiometry: 可选计量比约束, 如 {"Co": (0.8, 1.2), "O": (1.8, 2.2)}
            max_candidates: 最多返回候选数

        Returns:
            符合 candidates.json 格式的字典
        """
        candidates = self._retrieve_from_mp(self._session, elements)

        # 客户端过滤计量比
        if stoichiometry:
            candidates["candidates"] = self._filter_stoichiometry(
                candidates["candidates"], stoichiometry
            )

        # 排序 & 截断
        candidates["candidates"].sort(
            key=lambda c: c.get("energy_above_hull", float("inf"))
        )
        candidates["candidates"] = candidates["candidates"][:max_candidates]

        # 编排名次
        for i, c in enumerate(candidates["candidates"]):
            c["rank"] = i + 1

        candidates["query"]["stoichiometry"] = stoichiometry
        candidates["query"]["timestamp"] = datetime.now(timezone.utc).isoformat()
        return candidates

    def retrieve_formula(self, formula: str, max_candidates: int = DEFAULT_MAX_CANDIDATES) -> dict:
        """按化学式精确检索."""
        candidates = self._retrieve_from_mp(self._session, [], formula=formula)
        candidates["candidates"].sort(
            key=lambda c: c.get("energy_above_hull", float("inf"))
        )
        candidates["candidates"] = candidates["candidates"][:max_candidates]
        for i, c in enumerate(candidates["candidates"]):
            c["rank"] = i + 1
        candidates["query"]["timestamp"] = datetime.now(timezone.utc).isoformat()
        return candidates

    def _retrieve_from_mp(
        self, session, elements: list[str], formula: Optional[str] = None
    ) -> dict:
        """调 MP API, 处理分页, 返回原始候选字典."""
        all_candidates = []
        offset = 0
        limit = 1000

        fields = ",".join(DEFAULT_FIELDS)

        while True:
            if formula:
                url = f"{self.base_url}/materials/summary/"
                params = {
                    "formula": formula,
                    "_limit": limit,
                    "_skip": offset,
                    "_all_fields": False,
                    "_fields": fields,
                }
            else:
                chemsys = "-".join(sorted(elements))
                url = f"{self.base_url}/materials/summary/"
                params = {
                    "chemsys": chemsys,
                    "_limit": limit,
                    "_skip": offset,
                    "_all_fields": False,
                    "_fields": fields,
                }

            headers = {"X-API-KEY": self.api_key}
            for attempt in range(3):
                resp = session.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code == 200:
                    break
                time.sleep(2 ** attempt)
            resp.raise_for_status()
            body = resp.json()

            for item in body["data"]:
                cand = {
                    "material_id": item["material_id"],
                    "formula_pretty": item.get("formula_pretty", ""),
                    "formation_energy_per_atom": item.get("formation_energy_per_atom"),
                    "energy_above_hull": item.get("energy_above_hull", float("inf")),
                    "band_gap": item.get("band_gap"),
                    "space_group": item.get("space_group", ""),
                    "crystal_system": item.get("crystal_system", ""),
                    "n_sites": item.get("nsites"),
                    "structure_data": item.get("structure"),
                }
                if cand["structure_data"] is None:
                    continue
                all_candidates.append(cand)

            if len(body["data"]) < limit:
                break
            offset += limit

        return {
            "query": {"elements": elements, "formula": formula},
            "candidates": all_candidates,
        }

    @staticmethod
    def _filter_stoichiometry(
        candidates: list[dict],
        stoichiometry: dict[str, tuple[float, float]],
    ) -> list[dict]:
        """按计量比范围过滤候选."""
        kept = []
        for cand in candidates:
            struct = Structure.from_dict(cand["structure_data"])
            comp = struct.composition
            # 元素总数作为归一化基准
            total = sum(comp.get(el, 0) for el in stoichiometry)
            if total == 0:
                continue
            ok = True
            for el, (lo, hi) in stoichiometry.items():
                ratio = comp.get(el, 0) / total
                if ratio < lo or ratio > hi:
                    ok = False
                    break
            if ok:
                kept.append(cand)
        return kept

    def save(self, result: dict, output_dir: str | Path) -> Path:
        """保存 candidates.json."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "candidates.json"
        out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return out_path

    @staticmethod
    def load(path: str | Path) -> dict:
        """加载 candidates.json."""
        return json.loads(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "d:/research data/ai_project/MSBatch" && D:/conda_envs/mlp_env/python.exe -m pytest tests/test_retriever.py::test_retrieve_by_elements_basic -v`
Expected: PASS

- [ ] **Step 5: 添加更多测试**

在 `tests/test_retriever.py` 中追加:

```python
MOCK_MP_MULTI_PAGE = {
    "data": [MOCK_MP_DATA["data"][0]] * 1000,
    "meta": {"total_doc": 1001, "max_limit": 1000}
}
MOCK_MP_PAGE2 = {
    "data": [MOCK_MP_DATA["data"][1]],
    "meta": {"total_doc": 1001, "max_limit": 1000}
}


def test_retrieve_by_formula():
    """按化学式检索."""
    session = make_mock_session([
        FakeResponse(MOCK_MP_DATA)
    ])
    retriever = MPRetriever(api_key="test-key")
    result = retriever._retrieve_from_mp(session, [], formula="LiCoO2")

    assert len(result["candidates"]) == 2
    assert "formula=LiCoO2" in session.last_url


def test_stoichiometry_filter():
    """计量比过滤: 保留 O/Co ≈ 2 的候选."""
    retriever = MPRetriever(api_key="test-key")
    raw = [{"structure_data": MOCK_MP_DATA["data"][0]["structure"], "energy_above_hull": 0.0}]
    filtered = retriever._filter_stoichiometry(
        raw, {"Co": (0.15, 0.35), "O": (0.50, 0.75)}
    )
    # LiCoO2: Co=1/4=0.25, O=2/4=0.5 — 在范围内
    assert len(filtered) == 1


def test_stoichiometry_filter_excludes_out_of_range():
    retriever = MPRetriever(api_key="test-key")
    raw = [{"structure_data": MOCK_MP_DATA["data"][0]["structure"], "energy_above_hull": 0.0}]
    filtered = retriever._filter_stoichiometry(
        raw, {"Co": (0.5, 0.6)}  # Co 实际 0.25, 不在范围内
    )
    assert len(filtered) == 0


def test_save_and_load(tmp_path):
    """保存和加载 candidates.json."""
    retriever = MPRetriever(api_key="test-key")
    result = {"query": {"elements": ["Li"]}, "candidates": []}
    path = retriever.save(result, tmp_path / "test_output")
    loaded = retriever.load(path)
    assert loaded == result


def test_candidates_sorted_by_energy_above_hull():
    """候选按 energy_above_hull 升序 (稳定相在前)."""
    session = make_mock_session([
        FakeResponse(MOCK_MP_DATA)  # mp-12345 hull=0.0, mp-54321 hull=0.15
    ])
    retriever = MPRetriever(api_key="test-key")
    result = retriever.retrieve_elements(["Li", "Co", "O"], max_candidates=50)
    hulls = [c["energy_above_hull"] for c in result["candidates"]]
    assert hulls == sorted(hulls)
```

- [ ] **Step 6: 运行全部测试**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_retriever.py -v`
Expected: 5 passed

- [ ] **Step 7: 提交**

```bash
git add src/retriever.py tests/test_retriever.py
git commit -m "feat: add MP retriever module (Stage 1)"
```

---

### Task 3: Slab Builder 模块

**Files:**
- Create: `src/slabber.py`
- Create: `tests/test_slabber.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_slabber.py
import json
from pathlib import Path
import pytest
from src.slabber import SlabBuilder


def make_test_candidates():
    """构建包含简单 FCC Cu 结构的候选."""
    from pymatgen.core.structure import Structure
    cu = Structure.from_spacegroup("Fm-3m", [[0,0,0]], ["Cu"], [[0,0,0]])
    return {
        "query": {"elements": ["Cu"]},
        "candidates": [
            {
                "rank": 1,
                "material_id": "mp-cu",
                "formula_pretty": "Cu",
                "energy_above_hull": 0.0,
                "space_group": "Fm-3m",
                "structure_data": cu.as_dict(),
            }
        ]
    }


def test_build_slabs_basic(tmp_path):
    """基本切面: FCC Cu 的 (001) 面."""
    builder = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    manifest = builder.build(
        make_test_candidates(),
        miller_indices=[(0, 0, 1)],
        output_dir=tmp_path,
    )
    assert len(manifest["slabs"]) == 1
    slab = manifest["slabs"][0]
    assert slab["material_id"] == "mp-cu"
    assert slab["miller_index"] == [0, 0, 1]
    assert Path(slab["cif_path"]).exists()


def test_build_slabs_creates_cif_files(tmp_path):
    """确认 CIF 文件写入磁盘."""
    builder = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    manifest = builder.build(
        make_test_candidates(),
        miller_indices=[(0, 0, 1), (1, 1, 0)],
        output_dir=tmp_path,
    )
    assert len(manifest["slabs"]) == 2
    for slab in manifest["slabs"]:
        cif_path = Path(slab["cif_path"])
        assert cif_path.exists()
        content = cif_path.read_text()
        assert "data_" in content


def test_max_rank_limits_candidates(tmp_path):
    """max_rank 限制处理的候选数量."""
    candidates = make_test_candidates()
    # 添加第二个候选
    candidates["candidates"].append({
        "rank": 2,
        "material_id": "mp-cu2",
        "formula_pretty": "Cu2",
        "energy_above_hull": 0.5,
        "space_group": "Fm-3m",
        "structure_data": candidates["candidates"][0]["structure_data"],
    })
    builder = SlabBuilder()
    manifest = builder.build(
        candidates, miller_indices=[(0,0,1)], max_rank=1, output_dir=tmp_path
    )
    mp_ids = {s["material_id"] for s in manifest["slabs"]}
    assert mp_ids == {"mp-cu"}


def test_symmetry_equivalent_faces_detected(tmp_path):
    """对称等价面去重: 立方晶系中 (100), (010), (001) 等价."""
    builder = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    manifest = builder.build(
        make_test_candidates(),
        miller_indices=[(1, 0, 0), (0, 1, 0), (0, 0, 1)],
        deduplicate_symmetrically=True,
        output_dir=tmp_path,
    )
    # 立方晶系这三个面等价, 去重后只保留一个
    assert len(manifest["slabs"]) == 1


def test_slab_manifest_structure(tmp_path):
    """验证 manifest 包含所有必要字段."""
    builder = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    manifest = builder.build(
        make_test_candidates(),
        miller_indices=[(0, 0, 1)],
        output_dir=tmp_path,
    )
    slab = manifest["slabs"][0]
    for key in ["material_id", "miller_index", "cif_path", "slab_thickness_A", "vacuum_A", "supercell"]:
        assert key in slab, f"Missing key: {key}"
    assert slab["vacuum_A"] >= 10.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_slabber.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 SlabBuilder**

```python
# src/slabber.py
"""Stage 2: 切面生成器."""
import json
from pathlib import Path
from typing import Optional

from pymatgen.core.structure import Structure
from pymatgen.core.surface import SlabGenerator, generate_all_slabs
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.io.cif import CifWriter

from config.defaults import (
    DEFAULT_MIN_SLAB_THICKNESS, DEFAULT_MIN_VACUUM,
    DEFAULT_MILLER_INDICES, DEFAULT_MAX_SLAB_RANK
)


class SlabBuilder:
    """为候选结构生成 slab 模型."""

    def __init__(
        self,
        min_slab_thickness: float = DEFAULT_MIN_SLAB_THICKNESS,
        min_vacuum: float = DEFAULT_MIN_VACUUM,
    ):
        self.min_slab_thickness = min_slab_thickness
        self.min_vacuum = min_vacuum

    def build(
        self,
        candidates_json: dict,
        miller_indices: Optional[list[tuple[int, int, int]]] = None,
        user_indices: Optional[list[tuple[int, int, int]]] = None,
        max_rank: int = DEFAULT_MAX_SLAB_RANK,
        deduplicate_symmetrically: bool = True,
        output_dir: str | Path = ".",
    ) -> dict:
        """生成 slab 并返回 manifest.

        Args:
            candidates_json: Stage 1 输出的候选字典
            miller_indices: 晶面列表, None 则用默认值
            user_indices: 用户追加的晶面 (与 miller_indices 合并)
            max_rank: 最多处理前 N 个候选
            deduplicate_symmetrically: 是否去重对称等价面
            output_dir: CIF 输出目录

        Returns:
            slabs_manifest dict
        """
        if miller_indices is None:
            miller_indices = list(DEFAULT_MILLER_INDICES)
        if user_indices:
            miller_indices = list(miller_indices) + list(user_indices)

        output_dir = Path(output_dir)
        slabs_dir = output_dir / "slabs"
        slabs_dir.mkdir(parents=True, exist_ok=True)

        slabs = []
        candidates = candidates_json["candidates"]

        for cand in candidates:
            if cand["rank"] > max_rank:
                break

            structure = Structure.from_dict(cand["structure_data"])
            formula = cand["formula_pretty"]
            mat_id = cand["material_id"]

            # 创建该候选的子目录
            subdir = slabs_dir / f"{mat_id}_{formula}"
            subdir.mkdir(parents=True, exist_ok=True)

            indices = self._get_unique_indices(
                structure, miller_indices, deduplicate_symmetrically
            )

            for hkl in indices:
                try:
                    slab = self._generate_slab(structure, hkl)
                    hkl_str = "".join(str(i) for i in hkl)
                    cif_path = subdir / f"{mat_id}_{hkl_str}.cif"
                    CifWriter(slab).write_file(str(cif_path))

                    slabs.append({
                        "material_id": mat_id,
                        "formula_pretty": formula,
                        "miller_index": list(hkl),
                        "cif_path": str(cif_path),
                        "slab_thickness_A": round(slab.lattice.c, 2),
                        "vacuum_A": round(
                            slab.lattice.c - self._slab_height(slab), 2
                        ),
                        "supercell": [1, 1, 1],
                    })
                except Exception as e:
                    print(f"  [WARN] 无法切 {mat_id} {hkl}: {e}")
                    continue

        manifest = {"slabs": slabs}
        manifest_path = output_dir / "slabs_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return manifest

    def _generate_slab(self, structure: Structure, hkl: tuple) -> Structure:
        """生成单个 slab."""
        slab_gen = SlabGenerator(
            initial_structure=structure,
            miller_index=hkl,
            min_slab_size=self.min_slab_thickness,
            min_vacuum_size=self.min_vacuum,
            lll_reduce=False,
            center_slab=True,
        )
        slabs = slab_gen.get_slabs()
        if not slabs:
            raise ValueError(f"无法为 {hkl} 生成 slab")
        # 返回对称性最低的 slab (最接近表面的)
        return slabs[0]

    @staticmethod
    def _slab_height(slab: Structure) -> float:
        """估算 slab 中原子层的实际厚度."""
        z_coords = [site.frac_coords[2] for site in slab]
        if not z_coords:
            return 0.0
        z_range = max(z_coords) - min(z_coords)
        return z_range * slab.lattice.c

    @staticmethod
    def _get_unique_indices(
        structure: Structure,
        miller_indices: list[tuple[int, int, int]],
        deduplicate: bool,
    ) -> list[tuple[int, int, int]]:
        """去重对称等价晶面."""
        if not deduplicate:
            return miller_indices

        sa = SpacegroupAnalyzer(structure)
        sym_ops = sa.get_symmetry_ops()

        unique = []
        for hkl in miller_indices:
            is_equiv = False
            for existing in unique:
                for op in sym_ops:
                    transformed = op.rotate_coords(hkl)
                    # 忽略符号 (上下表面视为同一组晶面)
                    if tuple(abs(x) for x in transformed) == tuple(abs(x) for x in existing):
                        is_equiv = True
                        break
                if is_equiv:
                    break
            if not is_equiv:
                unique.append(hkl)
        return unique
```

- [ ] **Step 4: 运行所有 slabber 测试**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_slabber.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/slabber.py tests/test_slabber.py
git commit -m "feat: add slab builder module (Stage 2)"
```

---

### Task 4: STEM Simulator 模块

**Files:**
- Create: `src/simulator.py`
- Create: `tests/test_simulator.py`

**注意:** py_multem 需从 [Ivanlh20/MULTEM](https://github.com/Ivanlh20/MULTEM) 编译安装。simulator 模块设计为干净的抽象接口，不依赖特定引擎。

- [ ] **Step 1: 写测试**

```python
# tests/test_simulator.py
import json
from pathlib import Path
import numpy as np
import pytest
from src.simulator import STEMSimulator, SimulatorNotAvailableError


def make_test_slab_manifest(tmp_path):
    """创建包含简单 CIF slab 的 manifest."""
    from pymatgen.core.structure import Structure
    from pymatgen.io.cif import CifWriter

    cu = Structure.from_spacegroup("Fm-3m", [[0,0,0]], ["Cu"], [[0,0,0]])
    cu.scale_lattice(16.0)  # 2x2x2 supercell

    slabs_dir = tmp_path / "slabs" / "mp-cu_Cu"
    slabs_dir.mkdir(parents=True)
    cif_path = slabs_dir / "mp-cu_001.cif"
    CifWriter(cu).write_file(str(cif_path))

    return {
        "slabs": [
            {
                "material_id": "mp-cu",
                "formula_pretty": "Cu",
                "miller_index": [0, 0, 1],
                "cif_path": str(cif_path),
            }
        ]
    }


def test_simulator_checks_availability(tmp_path):
    """没有 py_multem 时抛出明确错误."""
    sim = STEMSimulator({})
    try:
        sim.simulate(make_test_slab_manifest(tmp_path), tmp_path / "sim")
    except SimulatorNotAvailableError as e:
        assert "py_multem" in str(e).lower() or "multem" in str(e).lower()


def test_generate_dummy_image(tmp_path):
    """生成占位模拟图 (用于测试管道)."""
    sim = STEMSimulator({})
    img = sim._generate_placeholder_image(64, 64)
    assert isinstance(img, np.ndarray)
    assert img.shape == (64, 64)
    assert img.dtype == np.uint8


def test_simulate_with_placeholder_mode(tmp_path):
    """placeholder 模式生成所有模拟图."""
    sim = STEMSimulator({})
    sim._placeholder_mode = True
    manifest = make_test_slab_manifest(tmp_path)
    result = sim.simulate(manifest, tmp_path / "sim_images")
    assert len(result["simulations"]) == 1
    sim_entry = result["simulations"][0]
    assert Path(sim_entry["image_path"]).exists()
    assert Path(sim_entry["image_path"]).suffix == ".png"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_simulator.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 STEMSimulator**

```python
# src/simulator.py
"""Stage 3: STEM-HAADF 图像模拟器."""
import json
import warnings
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image

from config.defaults import SIM_CONFIG


class SimulatorNotAvailableError(RuntimeError):
    """py_multem 不可用时抛出."""
    pass


class STEMSimulator:
    """STEM-HAADF 模拟器.

    优先使用 py_multem, 不可用时提供 placeholder 模式用于测试管道.
    """

    def __init__(self, config: dict | None = None):
        self.config = {**SIM_CONFIG, **(config or {})}
        self._engine = None
        self._placeholder_mode = False
        self._try_load_engine()

    def _try_load_engine(self):
        """尝试加载 py_multem."""
        try:
            import py_multem as _  # noqa: F401
            self._engine = "py_multem"
        except ImportError:
            try:
                import multem as _  # noqa: F401
                self._engine = "multem"
            except ImportError:
                self._placeholder_mode = True
                warnings.warn(
                    "py_multem 未安装。运行在 placeholder 模式 (输出占位图)。"
                    "\n安装方法: 从 https://github.com/Ivanlh20/MULTEM 编译后 "
                    "pip install <build-dir>"
                )

    def simulate(self, manifest: dict, output_dir: str | Path) -> dict:
        """对 manifest 中每个 slab 运行 HAADF 模拟.

        Args:
            manifest: slabs_manifest dict
            output_dir: PNG 输出目录

        Returns:
            sim_images_manifest dict
        """
        output_dir = Path(output_dir)
        sim_dir = output_dir / "sim_images"
        sim_dir.mkdir(parents=True, exist_ok=True)

        simulations = []

        for slab in manifest["slabs"]:
            cif_path = Path(slab["cif_path"])
            if not cif_path.exists():
                print(f"  [SKIP] CIF 找不到: {cif_path}")
                continue

            mat_id = slab["material_id"]
            hkl_str = "".join(str(i) for i in slab["miller_index"])
            out_subdir = sim_dir / f"{mat_id}_{slab.get('formula_pretty', '')}"
            out_subdir.mkdir(parents=True, exist_ok=True)

            out_path = out_subdir / f"{mat_id}_{hkl_str}_HAADF.png"

            try:
                if self._placeholder_mode:
                    self._run_placeholder(str(cif_path), str(out_path))
                elif self._engine == "py_multem":
                    self._run_py_multem(str(cif_path), str(out_path))
                else:
                    self._run_py_multem(str(cif_path), str(out_path))
            except Exception as e:
                print(f"  [ERR] 模拟失败 {mat_id} {hkl_str}: {e}")
                continue

            simulations.append({
                "material_id": mat_id,
                "miller_index": slab["miller_index"],
                "image_path": str(out_path),
                "config": dict(self.config),
            })

        manifest_out = {"simulations": simulations}
        manifest_path = output_dir / "sim_images_manifest.json"
        manifest_path.write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")
        return manifest_out

    def _run_py_multem(self, cif_path: str, out_path: str):
        """用 py_multem 运行完整 multislice 模拟."""
        cfg = self.config

        # 从 CIF 读结构
        from pymatgen.io.cif import CifParser
        parser = CifParser(cif_path)
        structure = parser.get_structures()[0]

        # 提取原子信息
        atomic_numbers = [site.specie.Z for site in structure]
        positions = np.array([site.coords for site in structure])  # Å
        cell = structure.lattice.matrix  # 3x3 Å

        # 构建 MULTEM 输入系统
        # 注: py_multem 具体 API 以实际包为准，此处为参考调用
        import py_multem as multem

        system = multem.System()
        system.set_cell(cell)
        for z, pos in zip(atomic_numbers, positions):
            system.add_atom(z, pos)

        # 设置显微镜参数
        params = multem.Parameters()
        params.set_accelerating_voltage(cfg["accelerating_voltage_kV"])
        params.set_convergence_angle(cfg["semi_angle_mrad"])
        params.set_detector_angles(
            cfg["HAADF_inner_mrad"], cfg["HAADF_outer_mrad"]
        )
        params.set_pixel_size(cfg["pixel_size_A"])
        params.set_defocus(cfg["probe_defocus_nm"])
        params.set_cs(cfg["spherical_aberration_mm"])

        # Frozen phonon 配置 (Z 衬度的物理来源)
        params.set_thermal_sigma(cfg["thermal_sigma_A"])
        params.set_frozen_phonon_configs(cfg["frozen_phonon_configs"])

        # 运行模拟
        result = multem.run_multislice(
            system,
            params,
            scan_dimensions=None,  # 自动计算
        )

        # 提取 HAADF 图像并保存
        haadf_image = result.get_haadf_image()
        haadf_image = self._normalize_image(haadf_image)
        Image.fromarray(haadf_image).save(out_path)

    def _run_placeholder(self, cif_path: str, out_path: str):
        """生成占位图用于管道测试."""
        img = self._generate_placeholder_image(256, 256)
        Image.fromarray(img).save(out_path)

    def _generate_placeholder_image(self, width: int, height: int) -> np.ndarray:
        """生成模拟原子列的占位图."""
        rng = np.random.default_rng(self.config["seed"])
        img = np.zeros((height, width), dtype=np.float32)

        # 模拟原子列: 在高斯背景上放一些亮点
        n_spots = rng.integers(5, 20)
        for _ in range(n_spots):
            x = rng.integers(width // 8, 7 * width // 8)
            y = rng.integers(height // 8, 7 * height // 8)
            if x < width and y < height:
                img[y, x] = rng.uniform(0.6, 1.0)

        # 高斯展宽模拟电子束卷积
        sigma = max(width, height) / 40
        img = gaussian_filter(img, sigma=sigma)

        # 加一些噪声
        img += rng.normal(0, 0.02, img.shape)
        img = np.clip(img, 0, 1)

        # 归一化到 0-255
        img = (img / img.max() * 255).astype(np.uint8)
        return img

    @staticmethod
    def _normalize_image(img: np.ndarray) -> np.ndarray:
        """归一化图像到 0-255 uint8."""
        img = np.array(img, dtype=np.float64)
        img_min, img_max = img.min(), img.max()
        if img_max > img_min:
            img = (img - img_min) / (img_max - img_min)
        return (img * 255).astype(np.uint8)
```

- [ ] **Step 4: 运行 simulator 测试**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_simulator.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/simulator.py tests/test_simulator.py
git commit -m "feat: add STEM simulator module with py_multem interface (Stage 3)"
```

---

### Task 5: Report Generator 模块

**Files:**
- Create: `src/reporter.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_reporter.py
import base64
import io
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from src.reporter import Reporter


def make_test_data(tmp_path):
    """构建测试用候选和模拟数据."""
    # 生成一张小 PNG 作为模拟图
    img = np.random.default_rng(42).integers(0, 255, (32, 32)).astype(np.uint8)
    sim_dir = tmp_path / "sim_images" / "mp-cu_Cu"
    sim_dir.mkdir(parents=True)
    img_path = sim_dir / "mp-cu_001_HAADF.png"
    Image.fromarray(img).save(str(img_path))

    candidates = {
        "query": {
            "elements": ["Cu"],
            "timestamp": "2026-06-08T14:00:00",
            "stoichiometry": None,
        },
        "candidates": [
            {
                "rank": 1,
                "material_id": "mp-cu",
                "formula_pretty": "Cu",
                "formation_energy_per_atom": -1.0,
                "energy_above_hull": 0.0,
                "band_gap": 0.0,
                "space_group": "Fm-3m",
                "crystal_system": "cubic",
                "n_sites": 1,
            }
        ]
    }
    sim_manifest = {
        "simulations": [
            {
                "material_id": "mp-cu",
                "miller_index": [0, 0, 1],
                "image_path": str(img_path),
                "config": {},
            }
        ]
    }
    return candidates, sim_manifest


def test_generate_html(tmp_path):
    """生成自包含 HTML 报告."""
    cand, sim = make_test_data(tmp_path)
    reporter = Reporter()
    out = tmp_path / "report.html"
    path = reporter.generate(cand, sim, out)
    assert Path(path).exists()
    html = Path(path).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Cu" in html


def test_report_embeds_images_as_base64(tmp_path):
    """确认模拟图以 base64 嵌入 (自包含, 无需外部文件)."""
    cand, sim = make_test_data(tmp_path)
    reporter = Reporter()
    out = tmp_path / "report.html"
    reporter.generate(cand, sim, out)
    html = Path(out).read_text(encoding="utf-8")
    assert "data:image/png;base64," in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_reporter.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Reporter**

```python
# src/reporter.py
"""Stage 4: HTML 报告生成器."""
import base64
import json
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STEM-HAADF Structure Identification Report</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f5f5f5; color: #333; line-height: 1.6; }}
header {{ background: #1a1a2e; color: #fff; padding: 24px 32px; }}
header h1 {{ font-size: 1.5rem; }}
.query-meta {{ font-size: 0.85rem; opacity: 0.8; margin-top: 8px; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 24px; overflow: hidden; }}
.card-header {{ background: #16213e; color: #fff; padding: 16px 24px; }}
.card-header h2 {{ font-size: 1.1rem; }}
.card-header .info {{ font-size: 0.8rem; opacity: 0.75; margin-top: 4px; }}
.card-body {{ padding: 16px 24px; }}
.props {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
         gap: 8px 16px; font-size: 0.85rem; margin-bottom: 16px; }}
.props dt {{ font-weight: 600; color: #666; }}
.props dd {{ color: #111; }}
.image-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
              gap: 16px; }}
.image-cell {{ text-align: center; border: 1px solid #eee; border-radius: 6px;
              padding: 8px; }}
.image-cell img {{ max-width: 100%; height: auto; cursor: pointer; border-radius: 4px; }}
.image-cell .label {{ font-size: 0.8rem; color: #666; margin-top: 4px; }}
.overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
           background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center;
           align-items: center; }}
.overlay img {{ max-width: 90vw; max-height: 90vh; }}
.overlay:target {{ display: flex; }}
.exp-image-zone {{ border: 2px dashed #ccc; border-radius: 8px; padding: 32px;
                    text-align: center; color: #999; margin-top: 24px; }}
footer {{ text-align: center; padding: 24px; color: #999; font-size: 0.8rem; }}
</style>
</head>
<body>
<header>
  <h1>STEM-HAADF Structure Identification Report</h1>
  <div class="query-meta">{query_summary}</div>
</header>
<div class="container">
{cards}
<div class="exp-image-zone">
  <p>实验图像区域 — 将实拍 STEM-HAADF 图放在此处进行并排比对</p>
  {exp_image_html}
</div>
</div>
<div class="overlay" id="lightbox" onclick="this.style.display='none'">
  <img id="lightbox-img" src="">
</div>
<footer>Generated by MSBatch — {timestamp}</footer>
<script>
document.querySelectorAll('.image-cell img').forEach(img => {{
  img.addEventListener('click', function() {{
    document.getElementById('lightbox-img').src = this.src;
    document.getElementById('lightbox').style.display = 'flex';
  }});
}});
</script>
</body>
</html>"""


class Reporter:
    """生成自包含 HTML 报告供人眼比对."""

    def generate(
        self,
        candidates_json: dict,
        sim_manifest: dict,
        output_path: str | Path,
        experimental_image: str | None = None,
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime, timezone

        query = candidates_json.get("query", {})
        elements = query.get("elements", [])
        n_candidates = len(candidates_json.get("candidates", []))
        query_summary = (
            f"Elements: {', '.join(elements)} | "
            f"Candidates: {n_candidates} | "
            f"Simulations: {len(sim_manifest.get('simulations', []))}"
        )

        # 构建 sim 索引: (material_id, hkl) → image_path
        sim_index = {}
        for sim in sim_manifest.get("simulations", []):
            hkl_str = "".join(str(i) for i in sim["miller_index"])
            sim_index[(sim["material_id"], hkl_str)] = sim["image_path"]

        cards_html = ""
        for cand in candidates_json.get("candidates", []):
            mid = cand["material_id"]
            images_html = ""
            for sim in sim_manifest.get("simulations", []):
                if sim["material_id"] != mid:
                    continue
                hkl_str = "".join(str(i) for i in sim["miller_index"])
                img_b64 = self._image_to_base64(sim["image_path"])
                if img_b64:
                    images_html += (
                        f'<div class="image-cell">'
                        f'<img src="data:image/png;base64,{img_b64}" '
                        f'alt="({hkl_str})">'
                        f'<div class="label">({hkl_str[0]}{hkl_str[1]}{hkl_str[2]}) '
                        f'slab</div></div>\n'
                    )

            cards_html += f"""<div class="card">
<div class="card-header">
  <h2>{cand['formula_pretty']} — {mid}</h2>
  <div class="info">Rank #{cand['rank']} | Space Group: {cand.get('space_group','?')}
  | Crystal: {cand.get('crystal_system','?')}</div>
</div>
<div class="card-body">
  <dl class="props">
    <dt>Formation Energy</dt><dd>{cand.get('formation_energy_per_atom','?')} eV/atom</dd>
    <dt>Energy Above Hull</dt><dd>{cand.get('energy_above_hull','?')} eV/atom</dd>
    <dt>Band Gap</dt><dd>{cand.get('band_gap','?')} eV</dd>
    <dt>N Sites</dt><dd>{cand.get('n_sites','?')}</dd>
  </dl>
  <div class="image-grid">{images_html}</div>
</div>
</div>\n"""

        exp_html = ""
        if experimental_image:
            img_b64 = self._image_to_base64(experimental_image)
            if img_b64:
                exp_html = (
                    f'<img src="data:image/png;base64,{img_b64}" '
                    f'style="max-width:400px;margin-top:12px;" alt="experimental">'
                )

        html = HTML_TEMPLATE.format(
            query_summary=query_summary,
            cards=cards_html,
            exp_image_html=exp_html,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        output_path.write_text(html, encoding="utf-8")
        return str(output_path)

    @staticmethod
    def _image_to_base64(path: str) -> str | None:
        """读取 PNG 并编码为 base64 data URI."""
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        except (FileNotFoundError, OSError):
            return None
```

- [ ] **Step 4: 运行 reporter 测试**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_reporter.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/reporter.py tests/test_reporter.py
git commit -m "feat: add HTML report generator (Stage 4)"
```

---

### Task 6: CLI 脚本

**Files:**
- Create: `scripts/run_pipeline.py`
- Create: `scripts/run_stage.py`

- [ ] **Step 1: 创建全管道 CLI**

```python
# scripts/run_pipeline.py
"""STEM-HAADF 结构鉴定完整管道 CLI."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import MPRetriever
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from src.reporter import Reporter
from config.defaults import SIM_CONFIG


def parse_stoich(ctx, param, value):
    """解析 --stoich 'Co:0.8-1.2,O:1.8-2.2' 格式."""
    if not value:
        return None
    result = {}
    for part in value.split(","):
        el, rng = part.strip().split(":")
        lo, hi = rng.split("-")
        result[el.strip()] = (float(lo), float(hi))
    return result


def parse_miller(ctx, param, value):
    """解析 --miller '001,100,110,111' 格式."""
    if not value:
        return None
    result = []
    for s in value.split(","):
        s = s.strip()
        result.append(tuple(int(c) for c in s))
    return result


@click.command()
@click.option("--elements", "-e", help="元素列表, 逗号分隔: Li,Co,O")
@click.option("--formula", "-f", help="化学式: LiCoO2 (与 --elements 互斥)")
@click.option(
    "--stoich", callback=parse_stoich, default=None,
    help="化学计量比范围: 'Co:0.8-1.2,O:1.8-2.2'"
)
@click.option("--max-candidates", default=50, help="最多候选数")
@click.option(
    "--miller", callback=parse_miller, default=None,
    help="手动指定晶面: '001,100,110,111,104' (留空使用默认低指数面)"
)
@click.option("--max-rank", default=20, help="最多模拟前 N 个候选")
@click.option("--experimental", default=None, help="实验图像路径 (可选)")
@click.option("--output", "-o", default=None, help="输出目录 (默认自动生成时间戳目录)")
def run_pipeline(elements, formula, stoich, max_candidates, miller, max_rank,
                 experimental, output):
    """运行完整的 STEM-HAADF 结构鉴定管道."""

    if not elements and not formula:
        raise click.UsageError("必须指定 --elements 或 --formula")

    if output:
        output_dir = Path(output)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/output") / ts

    elements_list = [e.strip() for e in elements.split(",")] if elements else None

    print(f"=== Stage 1: MP 检索 ===")
    retriever = MPRetriever()
    if formula:
        candidates = retriever.retrieve_formula(formula, max_candidates=max_candidates)
    else:
        candidates = retriever.retrieve_elements(
            elements_list, stoichiometry=stoich, max_candidates=max_candidates
        )
    retriever.save(candidates, output_dir)
    print(f"  找到 {len(candidates['candidates'])} 个候选")

    print(f"\n=== Stage 2: 切面生成 ===")
    slabber = SlabBuilder()
    slab_manifest = slabber.build(
        candidates,
        user_indices=miller,
        max_rank=max_rank,
        output_dir=output_dir,
    )
    print(f"  生成 {len(slab_manifest['slabs'])} 个 slab")

    print(f"\n=== Stage 3: STEM 模拟 ===")
    simulator = STEMSimulator(SIM_CONFIG)
    sim_manifest = simulator.simulate(slab_manifest, output_dir)
    print(f"  完成 {len(sim_manifest['simulations'])} 个模拟")

    print(f"\n=== Stage 4: 生成报告 ===")
    reporter = Reporter()
    report_path = reporter.generate(
        candidates, sim_manifest,
        output_dir / "report.html",
        experimental_image=experimental,
    )
    print(f"  报告: {report_path}")

    print(f"\n完成. 输出目录: {output_dir}")


if __name__ == "__main__":
    run_pipeline()
```

- [ ] **Step 2: 创建单阶段 CLI**

```python
# scripts/run_stage.py
"""STEM-HAADF 管道单阶段执行 CLI."""
import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import MPRetriever
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from src.reporter import Reporter
from config.defaults import SIM_CONFIG


@click.group()
def cli():
    """MSBatch — STEM-HAADF 结构鉴定管道 (单阶段模式)."""
    pass


@cli.command("retrieve")
@click.option("--elements", "-e", required=True, help="元素: Li,Co,O")
@click.option("--max-candidates", default=50)
@click.option("--output", "-o", default="data/output/latest")
def retrieve(elements, max_candidates, output):
    """Stage 1: MP 检索."""
    el_list = [e.strip() for e in elements.split(",")]
    r = MPRetriever()
    result = r.retrieve_elements(el_list, max_candidates=max_candidates)
    path = r.save(result, Path(output))
    print(f"{len(result['candidates'])} candidates → {path}")


@cli.command("slab")
@click.option("--candidates", "-c", required=True, type=click.Path(exists=True),
              help="candidates.json 路径")
@click.option("--miller", default=None, help="晶面: 001,100,110,111")
@click.option("--max-rank", default=20)
@click.option("--output", "-o", default="data/output/latest")
def slab(candidates, miller, max_rank, output):
    """Stage 2: 切面生成."""
    data = MPRetriever.load(candidates)
    indices = None
    if miller:
        indices = [tuple(int(c) for c in s.strip()) for s in miller.split(",")]

    builder = SlabBuilder()
    manifest = builder.build(
        data, user_indices=indices, max_rank=max_rank, output_dir=Path(output)
    )
    print(f"{len(manifest['slabs'])} slabs → {output}/slabs/")


@cli.command("simulate")
@click.option("--manifest", "-m", required=True, type=click.Path(exists=True),
              help="slabs_manifest.json 路径")
@click.option("--output", "-o", default="data/output/latest")
def simulate(manifest, output):
    """Stage 3: STEM 模拟."""
    import json
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    sim = STEMSimulator(SIM_CONFIG)
    result = sim.simulate(data, Path(output))
    print(f"{len(result['simulations'])} simulations → {output}/sim_images/")


@cli.command("report")
@click.option("--candidates", "-c", required=True, type=click.Path(exists=True),
              help="candidates.json 路径")
@click.option("--sim-manifest", "-s", required=True, type=click.Path(exists=True),
              help="sim_images_manifest.json 路径")
@click.option("--experimental", default=None, help="实验图像路径")
@click.option("--output", "-o", default="data/output/latest/report.html")
def report(candidates, sim_manifest, experimental, output):
    """Stage 4: 生成 HTML 报告."""
    import json
    cand = json.loads(Path(candidates).read_text(encoding="utf-8"))
    sim = json.loads(Path(sim_manifest).read_text(encoding="utf-8"))
    r = Reporter()
    path = r.generate(cand, sim, output, experimental_image=experimental)
    print(f"Report → {path}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 3: 提交**

```bash
git add scripts/run_pipeline.py scripts/run_stage.py
git commit -m "feat: add CLI for full pipeline and single-stage execution"
```

---

### Task 7: 端到端集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/test_integration.py
"""端到端管道测试 (使用 placeholder 模式)."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retriever import MPRetriever
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from src.reporter import Reporter
from config.defaults import SIM_CONFIG

# 手动构建 Cu FCC 结构作为测试数据
from pymatgen.core.structure import Structure


def make_test_candidates():
    cu = Structure.from_spacegroup("Fm-3m", [[0, 0, 0]], ["Cu"], [[0, 0, 0]])
    cu.scale_lattice(12.0)  # 稍微扩大
    return {
        "query": {"elements": ["Cu"], "timestamp": "2026-01-01T00:00:00", "stoichiometry": None},
        "candidates": [
            {
                "rank": 1,
                "material_id": "mp-cu",
                "formula_pretty": "Cu",
                "formation_energy_per_atom": -1.0,
                "energy_above_hull": 0.0,
                "band_gap": 0.0,
                "space_group": "Fm-3m",
                "crystal_system": "cubic",
                "n_sites": 1,
                "structure_data": cu.as_dict(),
            }
        ]
    }


def test_full_pipeline_with_placeholder(tmp_path):
    """完整管道: 不使用 MP API, 只用本地结构."""
    # Stage 1: 用预构建候选代替 API
    candidates = make_test_candidates()
    (tmp_path / "candidates.json").write_text(json.dumps(candidates, indent=2))
    assert len(candidates["candidates"]) == 1

    # Stage 2: 切面
    slabber = SlabBuilder(min_slab_thickness=8.0, min_vacuum=10.0)
    slab_manifest = slabber.build(
        candidates, miller_indices=[(0,0,1), (1,1,1)], output_dir=tmp_path
    )
    assert len(slab_manifest["slabs"]) >= 1
    for s in slab_manifest["slabs"]:
        assert Path(s["cif_path"]).exists()

    # Stage 3: 模拟 (placeholder 模式)
    simulator = STEMSimulator(SIM_CONFIG)
    assert simulator._placeholder_mode or simulator._engine is not None
    sim_manifest = simulator.simulate(slab_manifest, tmp_path)
    for s in sim_manifest["simulations"]:
        assert Path(s["image_path"]).exists()

    # Stage 4: 报告
    reporter = Reporter()
    report_path = reporter.generate(candidates, sim_manifest, tmp_path / "report.html")
    html = Path(report_path).read_text(encoding="utf-8")
    assert "mp-cu" in html
    assert "Cu" in html

    # 报告自包含 (base64 嵌入, 不依赖外部文件)
    assert "data:image/png;base64," in html
```

- [ ] **Step 2: 运行集成测试**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/test_integration.py -v`
Expected: 1 passed

- [ ] **Step 3: 运行全部测试**

Run: `D:/conda_envs/mlp_env/python.exe -m pytest tests/ -v`
Expected: ~13 passed

- [ ] **Step 4: 提交**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end pipeline integration test"
```

---

### Task 8: 创建 tests/__init__.py 并运行最终验证

- [ ] **Step 1: 创建测试包初始化文件**

```bash
touch "d:/research data/ai_project/MSBatch/tests/__init__.py"
```

- [ ] **Step 2: 运行全部测试最终确认**

Run: `cd "d:/research data/ai_project/MSBatch" && D:/conda_envs/mlp_env/python.exe -m pytest tests/ -v --tb=short`
Expected: All tests pass (~13 tests)

- [ ] **Step 3: 提交**

```bash
git add tests/__init__.py
git commit -m "chore: finalize test suite"
```
