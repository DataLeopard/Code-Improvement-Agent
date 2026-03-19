"""Analysis modules for code improvement."""

from .structure import StructureAnalyzer
from .reusability import ReusabilityAnalyzer
from .clarity import ClarityAnalyzer
from .functionality import FunctionalityAnalyzer
from .security import SecurityAnalyzer
from .automation import AutomationAnalyzer

ALL_ANALYZERS = [
    StructureAnalyzer,
    ReusabilityAnalyzer,
    ClarityAnalyzer,
    FunctionalityAnalyzer,
    SecurityAnalyzer,
    AutomationAnalyzer,
]
