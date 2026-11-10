"""Mint and validate NOIDs."""

from random import randint

DIGIT = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
XDIGIT = DIGIT + [
    "b",
    "c",
    "d",
    "f",
    "g",
    "h",
    "j",
    "k",
    "m",
    "n",
    "p",
    "q",
    "r",
    "s",
    "t",
    "v",
    "w",
    "x",
    "z",
]
GENTYPES = ["r", "s", "z"]
DIGTYPES = ["d", "e"]
SHORT = ""
NOLIMIT = -1


class ValidationError(ValueError):
    """Raised when a NOID check character is invalid."""


class InvalidTemplateError(ValueError):
    """Raised when a NOID template is invalid."""


class NamespaceError(ValueError):
    """Raised when a counter exceeds the template namespace."""


def mint(
    template: str = "eeddeede",
    n: int | None = None,
    scheme: str | None = None,
    naa: str | None = None,
) -> str:
    """Mint a NOID from a template and optional counter.

    Args:
        template: NOID template, optionally prefixed by a namespace.
        n: Counter value. A random value is chosen when omitted.
        scheme: Optional identifier scheme to prepend.
        naa: Optional naming authority and subauthority to prepend.

    Returns:
        The minted NOID.

    Raises:
        InvalidTemplateError: If the template mask is invalid.
        NamespaceError: If the counter does not fit the template.
    """
    if "." in template:
        prefix, mask = template.rsplit(".", 1)
    else:
        mask = template
        prefix = ""

    _validate_mask(mask)

    if n is None:
        if mask[0] in GENTYPES:
            mask = mask[1:]
        prefix = SHORT + prefix
        n = randint(0, _get_total(mask) - 1)

    noid = prefix + _n2xdig(n, mask)
    if naa:
        noid = naa.strip("/") + "/" + noid
    if template[-1] == "k":
        noid += _check_digit(noid)
    if scheme:
        noid = scheme + noid

    return noid


def validate(value: str) -> bool:
    """Validate the final check character of a NOID.

    Args:
        value: NOID to validate, optionally with a scheme prefix.

    Returns:
        True when the check character is valid.

    Raises:
        ValidationError: If the value is empty or its check character is invalid.
    """
    if not value or _check_digit(value[:-1]) != value[-1]:
        character = value[-1] if value else ""
        raise ValidationError(f"Noid check character {character!r} doesn't match up for {value!r}.")
    return True


def _n2xdig(n: int, mask: str) -> str:
    """Convert a counter to the digit sequence allowed by a mask.

    Args:
        n: Counter value.
        mask: NOID template mask.

    Returns:
        The digit sequence corresponding to the counter within the mask.

    Raises:
        InvalidTemplateError: If the mask contains invalid characters.
        NamespaceError: If the counter exceeds the namespace defined by the mask.
    """
    req = n
    xdig = ""
    for character in mask[::-1]:
        if character == "e":
            div = len(XDIGIT)
        elif character == "d":
            div = len(DIGIT)
        else:
            continue
        value = n % div
        n //= div
        xdig += XDIGIT[value]

    if mask[0] == "z":
        character = mask[1]
        while n > 0:
            if character == "e":
                div = len(XDIGIT)
            elif character == "d":
                div = len(DIGIT)
            else:
                raise InvalidTemplateError(
                    f"Template mask is corrupt. Cannot process character: {character}"
                )
            value = n % div
            n //= div
            xdig += XDIGIT[value]

    if n > 0:
        raise NamespaceError(f"Cannot mint a noid for (counter = {req}) within this namespace.")

    return xdig[::-1]


def _validate_mask(mask: str) -> bool:
    """Validate the structure of a NOID template mask.

    Args:
        mask: NOID template mask to validate.

    Returns:
        True if the mask is valid.

    Raises:
        InvalidTemplateError: If the mask is invalid.
    """
    if not mask or mask[0] not in GENTYPES + DIGTYPES:
        raise InvalidTemplateError("Template is invalid.")
    if mask[-1] not in ("k", *DIGTYPES):
        raise InvalidTemplateError("Template is invalid.")
    if any(character not in DIGTYPES for character in mask[1:-1]):
        raise InvalidTemplateError("Template is invalid.")
    return True


def _get_total(mask: str) -> int:
    """Return namespace size, or NOLIMIT for a variable-length mask.

    Args:
        mask: NOID template mask.

    Returns:
        The total number of possible values for the given mask, or NOLIMIT if the mask is variable-length.

    Raises:
        InvalidTemplateError: If the mask contains invalid characters.
    """
    if mask[0] == "z":
        return NOLIMIT

    total = 1
    for character in mask:
        if character == "e":
            total *= len(XDIGIT)
        elif character == "d":
            total *= len(DIGIT)
    return total


def _check_digit(value: str) -> str:
    """Calculate the NOID check character for a value.
    
    Args:
        value: The value for which to calculate the check character.

    Returns:
        The NOID check character for the given value.
    """

    def ordinal(character: str) -> int:
        try:
            return XDIGIT.index(character)
        except ValueError:
            return 0

    while ":" in value:
        value = value.split(":", 1)[1].lstrip("/")
    return XDIGIT[
        sum(index * (position + 1) for position, index in enumerate(map(ordinal, value)))
        % len(XDIGIT)
    ]
