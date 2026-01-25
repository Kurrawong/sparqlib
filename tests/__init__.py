from collections.abc import Iterator
from pathlib import Path

import pytest
from _pytest.mark import ParameterSet

TEST_DIR = Path(__file__).parent


def files_from_data_directory(
    data_directory: Path, xfail: dict[Path, str] | None = None
) -> Iterator[str | ParameterSet]:
    """Return an iterator of files for a paramtrized test.

    Currently, hardcoded to return files ending in .rq.
    This may be generalised to accept any file suffixes in the future.

    :param data_directory: The directory of files.
    :param xfail: A dictionary of file paths and the reason on why the test should
        be xfailed.
    """
    if xfail is None:
        xfail = {}

    file_paths = list(data_directory.glob("**/*.rq")) + list(
        data_directory.glob("**/*.ru")
    )

    for file_path in file_paths:
        value = file_path.resolve()
        if value not in xfail:
            yield str(value)
        else:
            yield pytest.param(
                str(value), marks=pytest.mark.xfail(reason=xfail[file_path.resolve()])
            )
