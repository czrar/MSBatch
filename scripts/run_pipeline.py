"""STEM-HAADF structure identification — full pipeline CLI."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import MPRetriever
from src.slabber import SlabBuilder
from src.simulator import STEMSimulator
from src.reporter import Reporter
from config.defaults import SIM_CONFIG


def parse_stoich(ctx, param, value):
    if not value:
        return None
    result = {}
    for part in value.split(","):
        el, rng = part.strip().split(":")
        lo, hi = rng.split("-")
        result[el.strip()] = (float(lo), float(hi))
    return result


def parse_miller(ctx, param, value):
    if not value:
        return None
    result = []
    for s in value.split(","):
        s = s.strip()
        result.append(tuple(int(c) for c in s))
    return result


@click.command()
@click.option("--elements", "-e", help="Comma-separated elements: Li,Co,O")
@click.option("--formula", "-f", help="Chemical formula: LiCoO2")
@click.option("--stoich", callback=parse_stoich, default=None,
              help="Stoichiometry ranges: 'Co:0.8-1.2,O:1.8-2.2'")
@click.option("--max-candidates", default=50, help="Max candidates from MP")
@click.option("--miller", callback=parse_miller, default=None,
              help="Manual Miller indices: '001,100,110,111,104'")
@click.option("--max-rank", default=20, help="Max candidates to simulate")
@click.option("--experimental", default=None, help="Path to experimental image")
@click.option("--output", "-o", default=None, help="Output directory")
def run_pipeline(elements, formula, stoich, max_candidates, miller, max_rank,
                 experimental, output):
    """Run the complete STEM-HAADF structure identification pipeline."""
    if not elements and not formula:
        raise click.UsageError("Must specify --elements or --formula")

    if output:
        output_dir = Path(output)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/output") / ts

    elements_list = [e.strip() for e in elements.split(",")] if elements else None

    print("=== Stage 1: MP Retrieval ===")
    retriever = MPRetriever()
    if formula:
        candidates = retriever.retrieve_formula(formula, max_candidates=max_candidates)
    else:
        candidates = retriever.retrieve_elements(
            elements_list, stoichiometry=stoich, max_candidates=max_candidates
        )
    retriever.save(candidates, output_dir)
    n = len(candidates["candidates"])
    print(f"  Found {n} candidates")

    if n == 0:
        print("No candidates found. Exiting.")
        return

    print("\n=== Stage 2: Slab Generation ===")
    slabber = SlabBuilder()
    slab_manifest = slabber.build(
        candidates, user_indices=miller, max_rank=max_rank, output_dir=output_dir
    )
    print(f"  Generated {len(slab_manifest['slabs'])} slabs")

    print("\n=== Stage 3: STEM Simulation ===")
    simulator = STEMSimulator(SIM_CONFIG)
    sim_manifest = simulator.simulate(slab_manifest, output_dir)
    print(f"  Completed {len(sim_manifest['simulations'])} simulations")

    print("\n=== Stage 4: Report Generation ===")
    reporter = Reporter()
    report_path = reporter.generate(
        candidates, sim_manifest, output_dir / "report.html",
        experimental_image=experimental
    )
    print(f"  Report: {report_path}")
    print(f"\nDone. Output: {output_dir}")


if __name__ == "__main__":
    run_pipeline()
