"""Words and marks that several text rules must agree on.

Kept in one place so that de-hyphenation, unwrapping and the noise rule never disagree about
what a line-end hyphen, a conjunction after a suspended hyphen, or a section break is.
"""

import re
from typing import Final

#: Marks that end a line where a word was hyphenated: the hyphen-minus, the soft hyphen
#: (U+00AD), the hyphen (U+2010), the non-breaking hyphen (U+2011), the not sign that Fraktur
#: and some OCR engines use as a hyphen (U+00AC, ALTO's ``HYP`` often holds it), and the double
#: oblique hyphen (U+2E17).
LINE_END_HYPHENS: Final = frozenset("-\u00ad\u2010\u2011\u00ac\u2e17")

#: Conjunctions that follow a suspended hyphen: ``pre- and post-war``, ``Ein- und Ausgang``.
#: A hyphen before one of them is not a word split by the line. French ``et`` and Dutch ``en``
#: and ``of`` are left out on purpose: they are also the last syllable of common English words
#: split at a line end (``pock-et``, ``chick-en``), which would then never be joined.
CONJUNCTIONS: Final = frozenset({"and", "or", "nor", "und", "oder", "sowie", "ou"})

#: French words joined to the word before them by a real hyphen: ``fait-il``, ``peut-être``,
#: ``qu'est-ce``, ``celle-ci``. A line-end hyphen before one of them is kept. The list is short
#: on purpose: a longer one would stop words genuinely split before such a syllable from being
#: joined (``cou-leur``).
CLITICS: Final = frozenset(
    {
        "il",
        "ils",
        "elle",
        "elles",
        "on",
        "ce",
        "je",
        "tu",
        "nous",
        "vous",
        "être",
        "ci",
        "là",
    }
)

#: A section break set as three or more asterisks (``* * *``, ``***``): typography the author
#: put there, which the noise rule keeps and unwrapping keeps on a line of its own.
SECTION_BREAK: Final = re.compile(r"[ \t]*(?:\*[ \t]*){3,}")
