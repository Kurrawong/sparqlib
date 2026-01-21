import os
import warnings
from unittest.mock import patch

import pytest

import sparql
from sparql import IterativeSparqlSerializer, SparqlSerializer, get_serializer


def test_get_serializer_defaults_to_iterative():
    # Default behavior (env var not set or "true")
    serializer = get_serializer()
    assert isinstance(serializer, IterativeSparqlSerializer)


def test_get_serializer_explicit_recursive():
    serializer = get_serializer(use_iterative=False)
    assert isinstance(serializer, SparqlSerializer)


def test_get_serializer_explicit_iterative():
    serializer = get_serializer(use_iterative=True)
    assert isinstance(serializer, IterativeSparqlSerializer)


def test_recursive_serializer_deprecation_warning():
    with pytest.warns(DeprecationWarning, match="is deprecated"):
        SparqlSerializer()


def test_iterative_serializer_no_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        IterativeSparqlSerializer()
        # Filter for DeprecationWarning specifically from this class
        dep_warnings = [
            x
            for x in w
            if issubclass(x.category, DeprecationWarning)
            and "IterativeSparqlSerializer" in str(x.message)
        ]
        assert len(dep_warnings) == 0
