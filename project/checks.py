"""Project checks run by `validate`. Yield failure messages; never change the model.

Most studies only need project/expectations.json (see README.md here). Add checks
below for rules that file cannot express; fea_checks.active_nodes(snapshot) lists
the unsuppressed Mechanical tree objects.
"""
from fea_checks import expectation_issues, load_expectations


def check(backend, snapshot):
    if backend == "workbench":
        if not snapshot.get("systems"):
            yield "Workbench has no analysis systems."
    elif not snapshot.get("analyses"):
        yield "Mechanical has no analyses."
    yield from expectation_issues(backend, snapshot, load_expectations())
