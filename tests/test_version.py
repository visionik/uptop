"""Test uptop package metadata."""

import uptop


def test_version() -> None:
    """Test that version is defined."""
    assert hasattr(uptop, "__version__")
    assert isinstance(uptop.__version__, str)
    assert uptop.__version__ == "0.1.0"
