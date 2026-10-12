"""Read and build variable identifiers. No network needed."""

import undata

dcid = "undata/sdg/VC_DTH_TOTN.AGE--Y0T17__SEX--F"
parsed = undata.parse_dcid(dcid)
assert parsed is not None
print(parsed.agency_label, "|", parsed.code, "|", [str(d) for d in parsed.dimensions])
print(undata.describe_dcid(dcid))

# The same slice always gets the same identifier, whatever order you pass dimensions in.
print(undata.build_dcid("undata/sdg/VC_DTH_TOTN", {"SEX": "F", "AGE": "Y0T17"}))

# The "unknown" age band is its own slice. The named bands do not sum to the total.
print(undata.describe_dcid("undata/sdg/VC_DTH_TOTN.AGE--_U__SEX--_U"))
