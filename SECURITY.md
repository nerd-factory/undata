# Security policy

undata is a read-only client for a public, unauthenticated API. It handles no
credentials and writes nothing except an optional local cache.

If you find a vulnerability — for example, a way for a crafted API response to cause
code execution or write outside the cache directory — please report it privately through
[GitHub security advisories](https://github.com/nerd-factory/undata/security/advisories/new)
rather than a public issue. Expect an acknowledgement within a week.

Only the latest release receives fixes while the package is below 1.0.
