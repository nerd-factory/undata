"""Names, UN names, codes and regions all work. Unknown names are never guessed."""

import undata as un

print(un.countries("Western Africa").head(4).to_string(index=False))

for name in ["Vietnam", "Türkiye", "Ivory Coast", "COD", "Bengal"]:
    try:
        print(f"{name!r:<14} ->", un.places.resolve(name).name)
    except un.PlaceNotFoundError as error:
        print(f"{name!r:<14} -> {error}")
