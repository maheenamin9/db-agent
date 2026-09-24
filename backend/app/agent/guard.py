"""A fast, pre-LLM check for an obviously destructive request ("delete the
customer named X"). This is a latency/UX optimization, NOT the safety boundary —
Task 12's validate_sql is what actually enforces read-only access, regardless of
whether this guard catches anything. Its only job is to avoid burning a
multi-minute LLM round trip on a question that's unambiguously asking for a write.

Deliberately simple, and deliberately narrow: natural language is far more
ambiguous than SQL, so this only flags a leading imperative verb ("Delete the
customer...", "Please update the price..."). It does NOT flag the verb appearing
elsewhere in a genuine question — "Which orders were deleted last month?" starts
with "Which", not a command, and must be allowed through. A destructive request
phrased indirectly enough to dodge this will still be caught by validate_sql once
SQL is actually generated for it — just slower, not unsafely.
"""

import re

# Common leading filler that doesn't change the sentence's intent.
_LEADING_FILLER = re.compile(
    r"^\s*(please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+|"
    r"i\s+want\s+you\s+to\s+|i'd\s+like\s+you\s+to\s+|go\s+ahead\s+and\s+)+",
    re.IGNORECASE,
)
_FIRST_WORD = re.compile(r"[a-zA-Z']+")

# Verbs that, leading a sentence, overwhelmingly signal a command to change data
# rather than a question about it — analytical questions lead with "what", "how
# many", "which", "list", "show", "find", "who", not these.
DESTRUCTIVE_VERBS = {
    "delete", "remove", "drop", "update", "insert", "alter", "truncate", "modify",
    "change", "add", "create", "set", "edit", "rename", "grant", "revoke",
    "execute", "replace", "overwrite", "clear", "erase", "wipe", "purge",
}


def destructive_intent(question: str) -> str | None:
    """Returns a reason string if `question` reads as a command to change data,
    else None."""
    stripped = _LEADING_FILLER.sub("", question.strip())
    match = _FIRST_WORD.match(stripped)
    if match and match.group(0).lower() in DESTRUCTIVE_VERBS:
        return (
            "this assistant can only read data — it never deletes, modifies, "
            "inserts, or creates anything, so no action was taken"
        )
    return None
