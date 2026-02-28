import re

# Each entry: (canonical_merchant_key, [patterns to strip prefix from lowercased raw desc])
# The canonical name becomes merchant_key; first token of the remainder becomes sub_merchant_key.
# Order within each group: most specific first.
_PLATFORM_RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    ("aplpay", [
        re.compile(r"^aplpay\s+\S+\s+\*\s*"),  # "AplPay BT*DD *MERCHANT"
        re.compile(r"^aplpay\s+\S+?\*\s*"),     # "AplPay CODE*MERCHANT" (non-greedy)
        re.compile(r"^aplpay\s+"),              # "AplPay MERCHANT" (bare)
    ]),
    ("tst", [
        re.compile(r"^tst\s*\*\s*"),            # "TST*MERCHANT" / "TST* MERCHANT"
    ]),
    ("sq", [
        re.compile(r"^sq\s*\*\s*"),             # "SQ *MERCHANT"
    ]),
    ("paypal", [
        re.compile(r"^pp\s*\*\s*"),             # "PP*MERCHANT"
        re.compile(r"^paypal\s*\*\s*"),         # "PAYPAL *MERCHANT"
        re.compile(r"^paypal\s+"),              # "PAYPAL MERCHANT"
    ]),
    ("grubhub", [
        re.compile(r"^grubhub\s*\*\s*"),        # "GRUBHUB*RESTAURANT"
    ]),
    ("doordash", [
        re.compile(r"^doordash\s*\*\s*"),       # "DOORDASH*RESTAURANT"
    ]),
]

# Build a fast lookup: pattern → canonical name
_PATTERN_TO_MERCHANT: list[tuple[re.Pattern[str], str]] = [
    (pat, name)
    for name, patterns in _PLATFORM_RULES
    for pat in patterns
]


def parse_description(raw: str) -> tuple[str, str | None, str | None]:
    """
    Returns (normalized_description, merchant_key, sub_merchant_key).

    Platform transactions (AplPay, Grubhub, PayPal, TST…) use the platform
    name as merchant_key and the first real vendor token as sub_merchant_key.
    Everything else gets merchant_key = first token, sub_merchant_key = None.
    """
    lowered = raw.lower()

    platform_merchant: str | None = None
    remainder: str = lowered

    for pattern, canonical in _PATTERN_TO_MERCHANT:
        stripped = pattern.sub("", lowered, count=1)
        if stripped != lowered:
            platform_merchant = canonical
            remainder = stripped.strip()
            break

    # Normalize the remainder (or full description if no platform matched)
    normalized_remainder = _clean(remainder)
    normalized_full = _clean(lowered) if platform_merchant is None else (platform_merchant + (" " + normalized_remainder if normalized_remainder else ""))

    tokens = normalized_remainder.split()

    if platform_merchant:
        merchant = platform_merchant
        sub_merchant = tokens[0] if tokens else None
        # Full normalized form: "aplpay shake shack new york" etc.
        normalized = (platform_merchant + (" " + normalized_remainder if normalized_remainder else "")).strip()
    else:
        all_tokens = normalized_full.split()
        merchant = all_tokens[0] if all_tokens else None
        sub_merchant = None
        normalized = normalized_full

    return normalized, merchant, sub_merchant


def _clean(text: str) -> str:
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def amount_to_bucket(amount: float) -> str:
    """Categorize a transaction amount into a size bucket for split suggestions."""
    if amount < 20:
        return "xs"
    if amount < 75:
        return "sm"
    if amount < 250:
        return "md"
    return "lg"


# Kept for backward compatibility
def normalize_description(raw: str) -> str:
    normalized, _, _ = parse_description(raw)
    return normalized


def extract_merchant_keys(normalized: str) -> tuple[str | None, str | None]:
    tokens = normalized.split()
    if not tokens:
        return None, None
    return tokens[0], None
