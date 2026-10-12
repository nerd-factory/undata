"""Turn place names into identifiers, and notice when a name matches nothing."""

import undata
from undata import _endpoints as api

NAMES = ["Bangladesh", "Viet Nam", "Côte d'Ivoire", "Bengal"]

with undata.Transport() as t:
    body = api.resolve(t, NAMES)

for entity in body["entities"]:
    candidates = [c["dcid"] for c in entity.get("candidates", [])]
    print(f"{entity['node']:<15} {candidates or 'no match'}")
