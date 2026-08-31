"""Bundled, region-aware entities — merchant names, customers, cities, banks,
payment-reference generators, bank narration templates. No PII: names are common
components combined procedurally.
"""

from __future__ import annotations

import random
from datetime import datetime

_BRAND_HEAD = {
    "IN": ["Anand", "Bharat", "Deccan", "Ganga", "Himalaya", "Indus", "Kaveri",
           "Lotus", "Nilgiri", "Orchid", "Sahyadri", "Trishul", "Vindhya", "Marigold",
           "Saffron", "Neem", "Tulsi", "Kayaan", "Amber"],
    "US": ["Summit", "Cedar", "Harbor", "Prairie", "Redwood", "Cascade", "Beacon",
           "Copper", "Maple", "Granite", "Willow", "Sierra", "Hudson", "Aspen"],
    "EU": ["Nord", "Alpen", "Rhein", "Adria", "Lumen", "Verde", "Solstice",
           "Bruck", "Danube", "Meridian", "Falk", "Havel", "Lindau", "Nova"],
}
_BRAND_TAIL = {
    "IN": ["Traders", "Retail", "Bazaar", "Mercantile", "Enterprises", "Organics",
           "Apparel", "Wellness", "Essentials", "Nutrition", "& Co"],
    "US": ["Goods Co", "Supply", "Collective", "Labs", "Outfitters", "Provisions",
           "Trading Co", "Works", "& Sons", "Mercantile", "Brands"],
    "EU": ["GmbH", "Handel", "Manufaktur", "Kollektiv", "Studio", "Werke",
           "Vertrieb", "& Partner", "Group", "Atelier"],
}
_SUFFIX = {
    "IN": ["Pvt Ltd", "Pvt Ltd", "LLP", "India", ""],
    "US": ["Inc.", "LLC", "Inc.", "Co.", ""],
    "EU": ["GmbH", "GmbH", "S.à r.l.", "B.V.", "AG", ""],
}

CITIES = {
    "IN": ["Bengaluru", "Mumbai", "Pune", "Gurugram", "Hyderabad", "Chennai",
           "Noida", "Ahmedabad", "Kolkata", "Jaipur", "Indore", "Kochi"],
    "US": ["Austin, TX", "Denver, CO", "Seattle, WA", "Chicago, IL", "Atlanta, GA",
           "Boston, MA", "Portland, OR", "Nashville, TN", "Columbus, OH", "Phoenix, AZ"],
    "EU": ["Berlin", "Munich", "Hamburg", "Amsterdam", "Rotterdam", "Vienna",
           "Frankfurt", "Cologne", "Antwerp", "Dublin", "Lisbon", "Milan"],
}

_FIRST = {
    "IN": ["Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Ishaan", "Kavya", "Aditi",
           "Kabir", "Sara", "Vivaan", "Myra", "Advait", "Anika", "Rehan"],
    "US": ["James", "Olivia", "Liam", "Emma", "Noah", "Ava", "Mason", "Sophia",
           "Ethan", "Isabella", "Logan", "Mia", "Lucas", "Amelia"],
    "EU": ["Lukas", "Marie", "Jonas", "Sophie", "Elias", "Emilia", "Finn", "Mila",
           "Luca", "Hanna", "Noah", "Lena", "Paul", "Ida", "Sanne", "Bram"],
}
_LAST = {
    "IN": ["Sharma", "Iyer", "Nair", "Reddy", "Gupta", "Menon", "Patel", "Das",
           "Bose", "Rao", "Joshi", "Kulkarni", "Verma", "Bhat"],
    "US": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
           "Davis", "Martinez", "Anderson", "Taylor", "Thomas"],
    "EU": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
           "Jansen", "de Vries", "Bakker", "Rossi", "Novak", "Andersen"],
}

# (issuer code, bank name) per region — codes appear in card_issuer + narrations
BANKS = {
    "IN": [("HDFC", "HDFC Bank"), ("ICIC", "ICICI Bank"), ("SBIN", "State Bank of India"),
           ("UTIB", "Axis Bank"), ("KKBK", "Kotak Mahindra Bank"), ("YESB", "Yes Bank"),
           ("IDFB", "IDFC First Bank"), ("INDB", "IndusInd Bank")],
    "US": [("CHAS", "JPMorgan Chase"), ("BOFA", "Bank of America"), ("WFBI", "Wells Fargo"),
           ("CITI", "Citibank"), ("USBK", "U.S. Bank"), ("PNCB", "PNC Bank"),
           ("CAPI", "Capital One"), ("TDBK", "TD Bank")],
    "EU": [("DEUT", "Deutsche Bank"), ("COBA", "Commerzbank"), ("INGB", "ING"),
           ("BNPA", "BNP Paribas"), ("RABO", "Rabobank"), ("SANT", "Santander"),
           ("SOGE", "Société Générale"), ("UNCR", "UniCredit")],
}

MCC = {"d2c-brand": "5651", "saas": "5734", "marketplace": "5399", "travel": "4722"}


def _r(region: str) -> str:
    return region if region in _BRAND_HEAD else "US"


def brand(rng: random.Random, region: str = "IN") -> str:
    r = _r(region)
    name = f"{rng.choice(_BRAND_HEAD[r])} {rng.choice(_BRAND_TAIL[r])}"
    sfx = rng.choice(_SUFFIX[r])
    return f"{name} {sfx}".strip()


def customer(rng: random.Random, region: str = "IN") -> str:
    r = _r(region)
    return f"{rng.choice(_FIRST[r])} {rng.choice(_LAST[r])}"


def city(rng: random.Random, region: str = "IN") -> str:
    return rng.choice(CITIES[_r(region)])


def bank(rng: random.Random, region: str = "IN") -> tuple[str, str]:
    return rng.choice(BANKS[_r(region)])


def payment_ref(rng: random.Random, region: str) -> str:
    """A bank settlement reference in the local format."""
    if region == "IN":
        if rng.random() < 0.25:  # Razorpay alphanumeric style
            tail = "".join(rng.choice("abcdefghjkmnpqrstuvwxyz0123456789") for _ in range(6))
            return f"{rng.randint(10**6, 10**7)}{tail}"
        return f"{rng.randint(10**11, 10**12 - 1)}"
    if region == "US":
        return f"{rng.randint(10**14, 10**15 - 1)}"  # 15-digit ACH trace
    # EU End-to-End ID — up to 35 alnum
    return "E2E" + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(16))


def narration(rng: random.Random, region: str, rail: str, counterparty: str, ref: str) -> str:
    cp = counterparty.upper()[:24]
    b = bank(rng, region)[0]
    if region == "IN":
        if rail == "NEFT":
            return f"NEFT CR-{b}00{rng.randint(10000, 99999)}-{cp}-{ref}"
        if rail == "RTGS":
            return f"RTGS CR-{b}R{rng.randint(10**9, 10**10)}-{cp}-{ref}"
        if rail == "IMPS":
            return f"MMT/IMPS/{ref}/{cp}"
        return f"UPI/{ref}/Settlement/{cp}"
    if region == "US":
        if rail == "WIRE":
            return f"FEDWIRE CREDIT REF {ref} ORIG {cp}"
        return f"ORIG CO NAME:{cp} ORIG ID:{b} DESC:PAYOUT SEC:CCD TRACE#:{ref}"
    # EU
    if rail == "SEPA_INSTANT":
        return f"SEPA INST CT / {cp} / E2E {ref}"
    return f"SEPA CREDIT TRANSFER / {cp} / MANDATE {b} / EREF {ref}"


# kept for callers that still import utr()
def utr(rng: random.Random, region: str = "IN") -> str:
    return payment_ref(rng, region)


def window_holidays(region: str, year: int = 2026) -> list[datetime]:
    from .regions import REGIONS
    reg = REGIONS.get(region)
    if not reg:
        return []
    return [datetime(h.year, h.month, h.day) for h in reg.holidays]
