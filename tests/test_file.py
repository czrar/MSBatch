"""Placeholder test for MSBatch."""


def test_imports():
    """Verify all core dependencies can be imported."""
    import pymatgen
    from mp_api.client import MPRester
    import abtem
    import click
    from PIL import Image

    assert pymatgen is not None
    assert MPRester is not None
    assert abtem is not None
    assert click is not None
    assert Image is not None
