"""LECTRIS: OCR output, read back into clean, ordered text.

``clean()`` runs a profile's layout and text rules and returns the text with every edit it
made; ``lectris.io`` reads OCR formats; ``lectris.report`` renders what changed;
``lectris.metrics`` measures OCR against a reference.
"""

from importlib.metadata import PackageNotFoundError, version

from lectris import io, metrics, report
from lectris.edits import Edit, Revision
from lectris.errors import FormatError, LectrisError
from lectris.lexicon import Lexicon
from lectris.model import Block, Box, Document, Line, Page, Word
from lectris.pipeline import CleanBlock, Profile, Result, Step, clean
from lectris.profiles import PROFILES

try:
    __version__ = version("lectris")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0"

__all__ = [
    "PROFILES",
    "Block",
    "Box",
    "CleanBlock",
    "Document",
    "Edit",
    "FormatError",
    "LectrisError",
    "Lexicon",
    "Line",
    "Page",
    "Profile",
    "Result",
    "Revision",
    "Step",
    "Word",
    "__version__",
    "clean",
    "io",
    "metrics",
    "report",
]
