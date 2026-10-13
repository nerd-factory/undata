"""Before you trust a chart from data.un.org's search box, see what it decided."""

import undata as un

for question in ["child mortality in Bengal", "child mortality in Bangladesh"]:
    answer = un.ask(question)
    print(f"{question!r}: answered about {answer.place}; guessed = {answer.place_was_guessed}")
