from pathlib import Path

import pytest

from tests import files_from_data_directory

current_dir = Path(__file__).parent
data_dir = current_dir / "data/sparql_test_suite_from_rdf_tests"


@pytest.mark.parametrize(
    "file",
    [
        *files_from_data_directory(
            data_dir,
        )
    ],
)
def test(file: str, test_roundtrip):
    test_roundtrip(file)
