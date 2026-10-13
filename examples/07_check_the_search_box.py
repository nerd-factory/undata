"""See what data.un.org's search box decided, before you trust its chart."""

import undata as un

answer = un.ask("child mortality in Bengal")
print(answer.place, "| guessed:", answer.place_was_guessed)

answer = un.ask("child mortality in Bangladesh")
print(answer.place, "| guessed:", answer.place_was_guessed)
