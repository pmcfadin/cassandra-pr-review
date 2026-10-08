"""PMD rules whose result depends on type resolution (the compiled classes and jars of the PR's build).

`cpr/config/pmd-type-rules.json` maps rule name -> where we learned it: "docs" (PMD's rule text says it needs the
classpath or resolved types) or "measured" (the rule's count changed when the same files ran with and without an
aux classpath). Without type info these rules can misfire, so the report
greys them and the check ignores them.
"""

import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "pmd-type-rules.json")


def load(path=PATH):
    """{rule: source}."""
    with open(path) as f:
        data = json.load(f)
    return dict(data.get("rules") or {})


def measured_diff(without, with_types):
    """Rules whose violation count differs between two {rule: count} runs -> {rule: [without, with]}."""
    return {r: [without.get(r, 0), with_types.get(r, 0)] for r in sorted(set(without) | set(with_types))
            if without.get(r, 0) != with_types.get(r, 0)}
