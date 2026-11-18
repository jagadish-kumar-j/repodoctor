"""Tests for the satisfies() version checker."""

from repodoctor.checkers.versions import satisfies


# --- Node.js spec formats ---


def test_satisfies_node_exact():
    assert satisfies("v18.17.0", "18.17.0") is True
    assert satisfies("v18.17.1", "18.17.0") is False


def test_satisfies_node_gte():
    assert satisfies("v18.17.0", ">=18") is True
    assert satisfies("v16.0.0", ">=18") is False


def test_satisfies_node_caret():
    assert satisfies("v18.17.0", "^18.0.0") is True
    assert satisfies("v19.0.0", "^18.0.0") is False


def test_satisfies_node_tilde():
    assert satisfies("v18.17.0", "~18.17.0") is True
    assert satisfies("v18.16.0", "~18.17.0") is False


def test_satisfies_node_18x():
    assert satisfies("v18.17.0", "18.x") is True
    assert satisfies("v20.0.0", "18.x") is False


def test_satisfies_node_v18():
    assert satisfies("v18.17.0", "v18") is True
    assert satisfies("v20.0.0", "v18") is False


def test_satisfies_node_range():
    assert satisfies("v18.17.0", ">=18 <21") is True
    assert satisfies("v21.0.0", ">=18 <21") is False


# --- Python spec formats ---


def test_satisfies_python_gte():
    assert satisfies("3.13.14", ">=3.10") is True
    assert satisfies("3.9.0", ">=3.10") is False


def test_satisfies_python_exact():
    assert satisfies("3.13.14", "3.13.14") is True
    assert satisfies("3.13.15", "3.13.14") is False


# --- Failing cases (at least 3) ---


def test_failing_node_exact_mismatch():
    assert satisfies("v16.0.0", "18.17.0") is False


def test_failing_node_gte_mismatch():
    assert satisfies("v16.0.0", ">=18") is False


def test_failing_python_version_mismatch():
    assert satisfies("3.9.0", ">=3.10") is False


# --- Unparseable cases (at least 2) ---


def test_unparseable_garbage():
    assert satisfies("v18.0.0", "!!!") is None


def test_unparseable_random_string():
    assert satisfies("v18.0.0", "not-a-valid-spec") is None


def test_unparseable_none_spec():
    assert satisfies("v18.0.0", None) is None
