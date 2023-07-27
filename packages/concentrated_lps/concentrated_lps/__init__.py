from pathlib import Path

import sys

# This is the directory where the "tests" module is located
# i.e. we are now in "packages/concentrated_lps/concentrated_lps/__init__.py".
#     its parent directory is "packages/concentrated_lps/concentrated_lps",
#     its parent directory is "packages/concentrated_lps",
#     its parent is "packages", and
#     its parent is the root directory of the project.
directory = Path(__file__).absolute().parent.parent.parent.parent

# Add the parent directory to sys.path
sys.path.append(directory.as_posix())

# Import the module from the root directory
from tests import geclp

__all__ = ["geclp"]
