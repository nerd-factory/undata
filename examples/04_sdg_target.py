"""From an SDG target to variables you can fetch, by walking the framework."""

import undata
from undata import _endpoints as api


def children(t: undata.Transport, node: str) -> list[dict[str, str]]:
    body = api.node(t, node, "<-specializationOf")
    return body["data"][node]["arcs"]["specializationOf"]["nodes"]


with undata.Transport() as t:
    for indicator in children(t, "undata/g/sdgf/target-16-1"):
        print(indicator["name"][:72])
    print()
    for group in children(t, "undata/g/sdgf/ind-16-1-2"):
        print(f"{group['dcid']:<26} {group['name']}")
