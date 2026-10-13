"""See what data.un.org's search box makes of a question, before trusting its chart.

The search box always picks a place. When a question names no place it knows, it
uses a default one and says so only in small print. :func:`ask` shows the place it
chose, whether it chose it itself, and the indicators it picked.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from . import _endpoints as api
from . import _session
from .errors import PlaceGuessedWarning

__all__ = ["Answer", "ask"]


@dataclass(frozen=True, slots=True)
class Answer:
    """What the search box decided.

    Attributes:
        question: The question as asked.
        place: The place it answered about, by name.
        place_id: The place's id.
        place_was_guessed: True when the question named no place the search box
            recognised and it supplied one of its own.
        indicators: ``(id, name)`` for each indicator it chose.
        messages: Any notes the search box returned.
    """

    question: str
    place: str | None
    place_id: str | None
    place_was_guessed: bool
    indicators: list[tuple[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        if self.place is None:
            where = "  place         none"
        elif self.place_was_guessed:
            where = f"  place         {self.place}  <- GUESSED: your question did not name it"
        else:
            where = f"  place         {self.place}  (from your question)"
        lines = [f"Question: {self.question}", where]
        lines += [f"  indicator     {name}  [{dcid}]" for dcid, name in self.indicators[:8]]
        if len(self.indicators) > 8:  # noqa: PLR2004
            lines.append(f"  ...and {len(self.indicators) - 8} more")
        lines += [f"  note          {m}" for m in self.messages]
        return "\n".join(lines)


def ask(question: str) -> Answer:
    """Ask data.un.org's search box a question and see what it decided.

    Args:
        question: A question as you would type it on data.un.org.

    Returns:
        An :class:`Answer`. A :class:`~undata.PlaceGuessedWarning` is shown when the
        search box chose a place your question did not name.

    Example:
        >>> import undata as un
        >>> un.ask("child mortality in Bengal")  # doctest: +SKIP
        Question: child mortality in Bengal
          place         United States of America  <- GUESSED: your question did not name it
        ...
    """
    body = api.detect_and_fulfill(_session.transport(), question)
    place = body.get("place") or {}
    guessed = bool(place) and body.get("placeSource") != "CURRENT_QUERY"

    chosen: dict[str, str] = {}
    for category in (body.get("config") or {}).get("categories", []):
        for key, spec in (category.get("statVarSpec") or {}).items():
            dcid = spec.get("statVar") or key.removesuffix("_multiple_place_bar_block")
            chosen.setdefault(dcid, spec.get("name", dcid))

    answer = Answer(
        question=question,
        place=place.get("name"),
        place_id=place.get("dcid"),
        place_was_guessed=guessed,
        indicators=list(chosen.items()),
        messages=list(body.get("userMessages") or []),
    )
    if guessed:
        warnings.warn(
            f"data.un.org answered {question!r} about {answer.place}, a place your question "
            "did not name. Name the country exactly, or use un.get() with a country you choose.",
            PlaceGuessedWarning,
            stacklevel=2,
        )
    return answer
