"""Performance benchmarks for the SPARQL serializer.

This module contains benchmarks to measure the performance characteristics
of the SPARQL serializer implementation.
"""

import time
import tracemalloc
from pathlib import Path

import pytest

from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer

SPEC_DATA_DIR = Path(__file__).parent / "data/sparql_spec_examples"

QUERIES = [
    "2.1_writing_a_simple_query.rq",
    "16.2.0_construct.rq",
    "12_subqueries.rq",
    "11.1_aggregate_example.rq",
    "9.2_property_path_sequence.rq",
]


def get_query(name):
    """Load a query from the spec examples directory."""
    path = SPEC_DATA_DIR / name
    with open(path) as f:
        return f.read()


def generate_nested_query(depth):
    """Generate a query with nested OPTIONAL clauses."""
    return (
        "SELECT * WHERE { " + "OPTIONAL { " * depth + "?s ?p ?o" + " } " * depth + "}"
    )


def generate_broad_query(triples):
    """Generate a query with many triples in the WHERE clause."""
    body = "\n".join([f"  ?s{i} ?p{i} ?o{i} ." for i in range(triples)])
    return f"SELECT * WHERE {{\n{body}\n}}"


def benchmark_serializer(tree, iterations=10):
    """Benchmark the serializer with the given tree.

    Args:
        tree: The parsed query tree
        iterations: Number of times to run serialization

    Returns:
        Tuple of (average_time_ms, peak_memory_kb)
    """
    # Warm-up run
    serializer = SparqlSerializer()
    serializer.visit_topdown(tree)
    _ = serializer.result

    # Start memory tracking
    tracemalloc.start()

    # Benchmark runs
    start_time = time.perf_counter()
    for _ in range(iterations):
        serializer = SparqlSerializer()
        serializer.visit_topdown(tree)
        _ = serializer.result
    end_time = time.perf_counter()

    # Get memory stats
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Calculate average time in milliseconds
    avg_time_ms = ((end_time - start_time) / iterations) * 1000
    peak_kb = peak / 1024

    return avg_time_ms, peak_kb


@pytest.mark.performance
def test_performance_benchmark():
    """Benchmark serializer performance on various queries."""
    print(f"\n{'Query Type':<30} | {'Time (ms)':<10} | {'Peak Mem (KB)':<15}")
    print("-" * 60)

    test_cases = []
    for q_name in QUERIES:
        test_cases.append((f"Spec: {q_name}", get_query(q_name)))

    test_cases.append(("Nested (depth 100)", generate_nested_query(100)))
    test_cases.append(("Broad (100 triples)", generate_broad_query(100)))

    for label, query_str in test_cases:
        tree = sparql_query_parser.parse(query_str)
        time_ms, peak_mem = benchmark_serializer(tree)
        print(f"{label:<30} | {time_ms:>10.2f} | {peak_mem:>15.2f}")


@pytest.mark.performance
def test_deep_nesting_performance():
    """Test performance on deeply nested query.

    This verifies the serializer can efficiently handle deep nesting
    without stack overflow issues.
    """
    depth = 300
    query = generate_nested_query(depth)
    tree = sparql_query_parser.parse(query)

    start = time.perf_counter()
    serializer = SparqlSerializer()
    serializer.visit_topdown(tree)
    result = serializer.result
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Verify we got output
    assert len(result) > 0
    assert "OPTIONAL" in result

    print(f"\nDeep nesting (depth={depth}): {elapsed_ms:.4f}ms")

    # Should complete in reasonable time (<200ms for 300 levels)
    assert elapsed_ms < 200, f"Deep nesting took {elapsed_ms:.2f}ms (expected <200ms)"


@pytest.mark.performance
def test_memory_efficiency():
    """Test memory efficiency over many iterations.

    Ensures the serializer doesn't have memory leaks and properly
    manages its internal state.
    """
    query = generate_nested_query(100)
    tree = sparql_query_parser.parse(query)

    tracemalloc.start()

    for _ in range(1000):
        serializer = SparqlSerializer()
        serializer.visit_topdown(tree)
        _ = serializer.result

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)

    print(f"\nMemory efficiency (1000 iterations): Peak {peak_mb:.2f}MB")

    # Peak memory should be reasonable (<50MB for 1000 iterations)
    assert peak_mb < 50, f"Memory usage {peak_mb:.2f}MB exceeds threshold"


@pytest.mark.performance
def test_performance_on_complex_queries():
    """Test performance on complex SPARQL query patterns."""
    complex_queries = [
        (
            "Property paths",
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/> SELECT * WHERE { "
            "?s foaf:knows+ ?o }",
        ),
        (
            "VALUES clause",
            "SELECT * WHERE { VALUES ?x { 1 2 3 4 5 } ?s ?p ?x }",
        ),
        (
            "BIND expression",
            "SELECT * WHERE { ?s ?p ?o . BIND(STRLEN(?o) AS ?len) FILTER(?len > 5) }",
        ),
    ]

    for label, query_str in complex_queries:
        tree = sparql_query_parser.parse(query_str)
        time_ms, _ = benchmark_serializer(tree, iterations=100)

        # Simple sanity check - should complete within 10ms per iteration
        assert time_ms < 10, f"{label}: Took {time_ms:.2f}ms (expected <10ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-s", "-v"])
