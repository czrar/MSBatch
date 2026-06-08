"""STEM-HAADF structure identification — single-stage CLI."""
import json
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
    """MSBatch — STEM-HAADF structure identification (single-stage mode)."""
    pass


@cli.command("retrieve")
@click.option("--elements", "-e", required=True, help="Elements: Li,Co,O")
@click.option("--formula", "-f", help="Formula: LiCoO2")
@click.option("--max-candidates", default=50)
@click.option("--output", "-o", default="data/output/latest")
def retrieve(elements, formula, max_candidates, output):
    """Stage 1: Retrieve candidates from Materials Project."""
    el_list = [e.strip() for e in elements.split(",")] if elements else None
    r = MPRetriever()
    if formula:
        result = r.retrieve_formula(formula, max_candidates=max_candidates)
    else:
        result = r.retrieve_elements(el_list, max_candidates=max_candidates)
    path = r.save(result, Path(output))
    print(f"{len(result['candidates'])} candidates -> {path}")


@cli.command("slab")
@click.option("--candidates", "-c", required=True, type=click.Path(exists=True),
              help="Path to candidates.json")
@click.option("--miller", default=None, help="Miller indices: 001,100,110,111")
@click.option("--max-rank", default=20)
@click.option("--output", "-o", default="data/output/latest")
def slab(candidates, miller, max_rank, output):
    """Stage 2: Generate surface slabs."""
    data = MPRetriever.load(candidates)
    indices = None
    if miller:
        indices = [tuple(int(c) for c in s.strip()) for s in miller.split(",")]
    builder = SlabBuilder()
    manifest = builder.build(data, user_indices=indices, max_rank=max_rank,
                             output_dir=Path(output))
    print(f"{len(manifest['slabs'])} slabs -> {output}/slabs/")


@cli.command("simulate")
@click.option("--manifest", "-m", required=True, type=click.Path(exists=True),
              help="Path to slabs_manifest.json")
@click.option("--output", "-o", default="data/output/latest")
def simulate(manifest, output):
    """Stage 3: Run STEM-HAADF simulations."""
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    sim = STEMSimulator(SIM_CONFIG)
    result = sim.simulate(data, Path(output))
    print(f"{len(result['simulations'])} simulations -> {output}/sim_images/")


@cli.command("report")
@click.option("--candidates", "-c", required=True, type=click.Path(exists=True),
              help="Path to candidates.json")
@click.option("--sim-manifest", "-s", required=True, type=click.Path(exists=True),
              help="Path to sim_images_manifest.json")
@click.option("--experimental", default=None, help="Path to experimental image")
@click.option("--output", "-o", default="data/output/latest/report.html")
def report(candidates, sim_manifest, experimental, output):
    """Stage 4: Generate HTML report."""
    cand = json.loads(Path(candidates).read_text(encoding="utf-8"))
    sim = json.loads(Path(sim_manifest).read_text(encoding="utf-8"))
    r = Reporter()
    path = r.generate(cand, sim, output, experimental_image=experimental)
    print(f"Report -> {path}")


if __name__ == "__main__":
    cli()
