import sys
from pathlib import Path

# The pipeline scripts import each other flat (import config, import
# logger_config), so src/python has to be importable as a top-level location.
SRC = Path(__file__).resolve().parents[1] / "src" / "python"
sys.path.insert(0, str(SRC))
