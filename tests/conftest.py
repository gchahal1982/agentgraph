from __future__ import annotations

import sys
from pathlib import Path

SOTA_SCRIPTS = Path(__file__).parents[1] / "scripts" / "sota"
if str(SOTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SOTA_SCRIPTS))
