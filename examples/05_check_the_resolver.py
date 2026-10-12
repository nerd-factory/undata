"""See which place the site's search box decided you meant, before trusting its chart."""

import undata
from undata import _endpoints as api

with undata.Transport() as t:
    for question in ["child mortality in Bengal", "child mortality in Bangladesh"]:
        place = api.detect_and_fulfill(t, question)["place"]
        print(f"{question!r:<34} -> {place['dcid']}  ({place['name']})")
