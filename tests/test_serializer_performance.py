"""Performance benchmarks comparing recursive vs iterative serializers.

This module contains comprehensive benchmarks to measure and compare the performance
characteristics of the recursive and iterative SPARQL serializers.
"""

import time
import tracemalloc
from pathlib import Path

import pytest

from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer
from sparql.serializer_iterative import IterativeSparqlSerializer

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
    with open(path, "r") as f:
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


def benchmark_serializer(serializer_class, tree, iterations=10):
    """Benchmark a serializer with the given tree.

    Args:
        serializer_class: The serializer class to benchmark
        tree: The parsed query tree
        iterations: Number of times to run serialization

    Returns:
        Tuple of (average_time_ms, peak_memory_kb)
    """
    # Warm-up run
    serializer = serializer_class()
    serializer.visit_topdown(tree)
    _ = serializer.result

    # Start memory tracking
    tracemalloc.start()

    # Benchmark runs
    start_time = time.perf_counter()
    for _ in range(iterations):
        serializer = serializer_class()
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
def test_performance_comparison():
    """Compare performance of recursive vs iterative serializers on various queries."""
    print(
        f"\n{'Query Type':<30} | {'Implementation':<15} | {'Time (ms)':<10} | {'Peak Mem (KB)':<15}"
    )
    print("-" * 80)

    test_cases = []
    for q_name in QUERIES:
        test_cases.append((f"Spec: {q_name}", get_query(q_name)))

    test_cases.append(("Nested (depth 100)", generate_nested_query(100)))
    test_cases.append(("Broad (100 triples)", generate_broad_query(100)))

    for label, query_str in test_cases:
        tree = sparql_parser.parse(query_str)

        # Benchmark both implementations
        rec_time, peak_rec = benchmark_serializer(SparqlSerializer, tree)
        iter_time, peak_iter = benchmark_serializer(IterativeSparqlSerializer, tree)

        print(
            f"{label:<30} | {'Recursive':<15} | {rec_time:>10.2f} | {peak_rec:>15.2f}"
        )
        print(
            f"{label:<30} | {'Iterative':<15} | {iter_time:>10.2f} | {peak_iter:>15.2f}"
        )

        # Comparison
        speedup = (rec_time / iter_time - 1) * 100
        mem_diff = (peak_iter / peak_rec - 1) * 100
        print(
            f"{'Speedup:':<30} {speedup:>+6.1f}% | {'Mem Change:':<15} {mem_diff:>+6.1f}%"
        )
        print("-" * 80)


@pytest.mark.performance
def test_performance_bounds():
    """Verify iterative serializer meets performance requirements (within 20% of recursive)."""
    test_queries = [
        ("Simple", "SELECT * WHERE { ?s ?p ?o }"),
        ("Moderate", "SELECT * WHERE { ?s ?p ?o . OPTIONAL { ?s ?p2 ?o2 } }"),
        ("Complex nested", generate_nested_query(50)),
        ("Complex broad", generate_broad_query(50)),
    ]

    for label, query_str in test_queries:
        tree = sparql_parser.parse(query_str)

        rec_time, _ = benchmark_serializer(SparqlSerializer, tree, iterations=50)
        iter_time, _ = benchmark_serializer(
            IterativeSparqlSerializer, tree, iterations=50
        )

        # Calculate performance ratio
        performance_ratio = iter_time / rec_time

        # Assert iterative is within acceptable bounds
        # Note: Performance ratio < 1.0 means iterative is faster
        # We allow up to 20% slower (ratio <= 1.20)
        assert performance_ratio <= 1.20, (
            f"{label}: Iterative serializer is {((performance_ratio - 1) * 100):.1f}% "
            f"slower than recursive (exceeds 20% threshold)"
        )


@pytest.mark.performance
def test_memory_bounds():
    """Verify iterative serializer has acceptable memory usage."""
    test_queries = [
        ("Simple", "SELECT * WHERE { ?s ?p ?o }"),
        ("Nested", generate_nested_query(100)),
        ("Broad", generate_broad_query(100)),
    ]

    for label, query_str in test_queries:
        tree = sparql_parser.parse(query_str)

        _, rec_mem = benchmark_serializer(SparqlSerializer, tree, iterations=50)
        _, iter_mem = benchmark_serializer(
            IterativeSparqlSerializer, tree, iterations=50
        )

        # Calculate memory ratio
        memory_ratio = iter_mem / rec_mem if rec_mem > 0 else 1.0

        # Allow iterative to use more memory for its explicit stack (up to 2x)
        # In practice, it often uses less memory on complex queries
        assert memory_ratio <= 2.0, (
            f"{label}: Iterative serializer uses {((memory_ratio - 1) * 100):.1f}% "
            f"more memory than recursive (exceeds 100% threshold)"
        )


@pytest.mark.performance
def test_deep_nesting_performance():
    """Test performance of iterative serializer on deeply nested query.

    This demonstrates that the iterative serializer can efficiently handle
    deep nesting that would cause RecursionError in the recursive version.
    """
    # Build a deeply nested OPTIONAL query (300 levels - safe for both)
    depth = 300
    query = generate_nested_query(depth)
    tree = sparql_parser.parse(query)

    # Benchmark iterative serializer
    start = time.perf_counter()
    serializer = IterativeSparqlSerializer()
    serializer.visit_topdown(tree)
    result = serializer.result
    iterative_time = (time.perf_counter() - start) * 1000

    # Verify we got output
    assert len(result) > 0
    assert "OPTIONAL" in result

    print(f"\nDeep nesting (depth={depth}):")
    print(f"  Iterative: {iterative_time:.4f}ms")

    # Should complete in reasonable time (< 200ms for 300 levels)
    assert (
        iterative_time < 200
    ), f"Deep nesting took {iterative_time:.2f}ms (expected < 200ms)"


@pytest.mark.performance
def test_memory_efficiency():
    """Test memory efficiency of iterative serializer over many iterations.

    This test ensures the iterative serializer doesn't have memory leaks
    and properly manages its internal state.
    """
    query = generate_nested_query(100)
    tree = sparql_parser.parse(query)

    tracemalloc.start()

    # Run serialization 1000 times
    for _ in range(1000):
        serializer = IterativeSparqlSerializer()
        serializer.visit_topdown(tree)
        _ = serializer.result

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)

    print(f"\nMemory efficiency (1000 iterations):")
    print(f"  Peak memory: {peak_mb:.2f}MB")

    # Peak memory should be reasonable (< 50MB for 1000 iterations)
    assert peak_mb < 50, f"Memory usage {peak_mb:.2f}MB exceeds threshold"


@pytest.mark.performance
def test_performance_on_complex_queries():
    """Test performance on more complex SPARQL query patterns."""
    complex_queries = [
        (
            "Property paths",
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/> SELECT * WHERE { ?s foaf:knows+ ?o }",
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
        tree = sparql_parser.parse(query_str)

        rec_time, _ = benchmark_serializer(SparqlSerializer, tree, iterations=100)
        iter_time, _ = benchmark_serializer(
            IterativeSparqlSerializer, tree, iterations=100
        )

        performance_ratio = iter_time / rec_time

        # Iterative should be within 20% of recursive performance
        assert (
            performance_ratio <= 1.20
        ), f"{label}: Iterative is {((performance_ratio - 1) * 100):.1f}% slower"


if __name__ == "__main__":
    pytest.main([__file__, "-s", "-v"])
