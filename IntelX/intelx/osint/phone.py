"""Phone-number public-format analysis (TASK-IG-INT-04).

The honest, keyless subset of the PhoneInfoga pattern (corpus item
DaLY8BGDYWp): offline E.164 parsing and validation against a country
calling-code table. What this module deliberately does NOT do:

  * Carrier / line-type lookup — no keyless authoritative source exists;
    commercial APIs (Twilio Lookup, Numverify, ...) require paid keys.
    ``PhoneInfo.carrier_lookup`` says exactly that instead of guessing.
  * "Disposable number" verdicts from blocklist folklore — not emitted.

Everything returned is derived from the number itself (format facts), and
is labelled as such.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Country calling code -> (ISO, country name). Longest-prefix match wins.
_CALLING_CODES: dict[str, tuple[str, str]] = {
    "1": ("US/CA", "United States / Canada (NANP)"),
    "7": ("RU/KZ", "Russia / Kazakhstan"),
    "20": ("EG", "Egypt"),
    "27": ("ZA", "South Africa"),
    "33": ("FR", "France"),
    "34": ("ES", "Spain"),
    "39": ("IT", "Italy"),
    "44": ("GB", "United Kingdom"),
    "49": ("DE", "Germany"),
    "52": ("MX", "Mexico"),
    "55": ("BR", "Brazil"),
    "61": ("AU", "Australia"),
    "65": ("SG", "Singapore"),
    "81": ("JP", "Japan"),
    "82": ("KR", "South Korea"),
    "86": ("CN", "China"),
    "91": ("IN", "India"),
    "92": ("PK", "Pakistan"),
    "94": ("LK", "Sri Lanka"),
    "971": ("AE", "United Arab Emirates"),
    "880": ("BD", "Bangladesh"),
    "977": ("NP", "Nepal"),
    "966": ("SA", "Saudi Arabia"),
    "974": ("QA", "Qatar"),
    "965": ("KW", "Kuwait"),
    "968": ("OM", "Oman"),
    "60": ("MY", "Malaysia"),
    "62": ("ID", "Indonesia"),
    "63": ("PH", "Philippines"),
    "84": ("VN", "Vietnam"),
    "66": ("TH", "Thailand"),
    "90": ("TR", "Türkiye"),
    "98": ("IR", "Iran"),
    "234": ("NG", "Nigeria"),
    "254": ("KE", "Kenya"),
    "31": ("NL", "Netherlands"),
    "41": ("CH", "Switzerland"),
    "46": ("SE", "Sweden"),
    "64": ("NZ", "New Zealand"),
}

CARRIER_LOOKUP_NOTE = (
    "unavailable: carrier and line-type lookup has no keyless authoritative "
    "source (commercial APIs require paid keys); not guessed"
)


@dataclass(frozen=True)
class PhoneInfo:
    raw_input: str
    digits: str  # digits only, as dialled internationally
    e164: str  # "+<digits>" when well-formed, else ""
    valid_format: bool
    country_iso: str
    country_name: str
    calling_code: str
    national_number: str
    problems: list[str]
    carrier_lookup: str = CARRIER_LOOKUP_NOTE

    def to_dict(self) -> dict:
        return {
            "raw_input": self.raw_input,
            "e164": self.e164,
            "valid_format": self.valid_format,
            "country_iso": self.country_iso,
            "country_name": self.country_name,
            "calling_code": self.calling_code,
            "national_number": self.national_number,
            "problems": self.problems,
            "carrier_lookup": self.carrier_lookup,
        }


def parse_phone(raw: str) -> PhoneInfo:
    """Parse and validate a phone number's public format (offline)."""
    problems: list[str] = []
    digits = re.sub(r"\D", "", raw or "")
    if raw.strip().startswith("00"):
        digits = re.sub(r"\D", "", raw)[2:]
    if not digits:
        problems.append("no digits in input")
    if digits and not (7 <= len(digits) <= 15):
        problems.append(f"length {len(digits)} is outside the E.164 range of 7-15 digits")

    calling_code = ""
    country_iso = ""
    country_name = ""
    for code in sorted(_CALLING_CODES, key=len, reverse=True):
        if digits.startswith(code):
            calling_code = code
            country_iso, country_name = _CALLING_CODES[code]
            break
    if digits and not calling_code:
        problems.append("no known country calling code prefix")

    national = digits[len(calling_code) :] if calling_code else ""
    if calling_code == "91" and national and len(national) != 10:
        problems.append(f"Indian national numbers are 10 digits; got {len(national)}")
    if calling_code == "1" and national and len(national) != 10:
        problems.append(f"NANP national numbers are 10 digits; got {len(national)}")

    valid = not problems and bool(calling_code)
    return PhoneInfo(
        raw_input=raw,
        digits=digits,
        e164=f"+{digits}" if valid else "",
        valid_format=valid,
        country_iso=country_iso,
        country_name=country_name,
        calling_code=calling_code,
        national_number=national,
        problems=problems,
    )


__all__ = ["CARRIER_LOOKUP_NOTE", "PhoneInfo", "parse_phone"]
