"""Bundled realistic entities — merchant names, banks, cities, narration
templates. No PII: names are common Indian business-name components combined
procedurally; nothing here maps to a real company or person.
"""

from __future__ import annotations

import random

_BRAND_HEAD = [
    "Anand", "Bharat", "Chandra", "Deccan", "Ganga", "Himalaya", "Indus", "Jyoti",
    "Kaveri", "Lotus", "Meghna", "Nilgiri", "Orchid", "Peacock", "Rajdhani",
    "Sahyadri", "Trishul", "Udaan", "Vindhya", "Zephyr", "Kayaan", "Marigold",
    "Saffron", "Neem", "Tulsi", "Amber", "Cobalt", "Copper",
]
_BRAND_TAIL = [
    "Traders", "Retail", "Commerce", "Bazaar", "Store", "Mercantile", "Enterprises",
    "Labs", "Technologies", "Solutions", "Ventures", "Organics", "Foods", "Apparel",
    "Living", "Wellness", "Essentials", "Collective", "& Co", "Nutrition",
]
_SUFFIX = ["Pvt Ltd", "LLP", "India", "Pvt Ltd", ""]

CITIES = [
    "Bengaluru", "Mumbai", "Pune", "Gurugram", "Hyderabad", "Chennai", "Noida",
    "Ahmedabad", "Kolkata", "Jaipur", "Indore", "Kochi", "Coimbatore", "Surat",
]

# 4-char issuer codes as they appear in Razorpay card_issuer + bank narrations
BANKS = [
    ("HDFC", "HDFC Bank"), ("ICIC", "ICICI Bank"), ("SBIN", "State Bank of India"),
    ("UTIB", "Axis Bank"), ("KKBK", "Kotak Mahindra Bank"), ("YESB", "Yes Bank"),
    ("PUNB", "Punjab National Bank"), ("IDFB", "IDFC First Bank"),
    ("RATN", "RBL Bank"), ("INDB", "IndusInd Bank"),
]

# MCC (merchant category code) by profile
MCC = {
    "d2c-brand": "5651", "saas": "5734", "marketplace": "5399", "travel": "4722",
}


def brand(rng: random.Random) -> str:
    name = f"{rng.choice(_BRAND_HEAD)} {rng.choice(_BRAND_TAIL)}"
    sfx = rng.choice(_SUFFIX)
    return f"{name} {sfx}".strip()


def customer(rng: random.Random) -> str:
    first = rng.choice([
        "Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Ishaan", "Kavya", "Reyansh",
        "Aditi", "Kabir", "Sara", "Vivaan", "Myra", "Advait", "Anika", "Rehan",
    ])
    last = rng.choice([
        "Sharma", "Iyer", "Nair", "Reddy", "Gupta", "Menon", "Patel", "Khan",
        "Das", "Bose", "Rao", "Joshi", "Kulkarni", "Verma", "Bhat", "Sethi",
    ])
    return f"{first} {last}"


def utr(rng: random.Random) -> str:
    """A bank UTR / RRN — 12 digits, occasionally alphanumeric (Razorpay style)."""
    if rng.random() < 0.25:
        return f"{rng.randint(10**9, 10**10 - 1)}{rng.choice('abcdefghjkmnpqrstuvwxyz')}{rng.choice('0123456789')}{rng.choice('abcdefghjkmnpqrstuvwxyz')}{rng.randint(100,999)}"
    return f"{rng.randint(10**11, 10**12 - 1)}"


# ---- bank narration templates (per rail) ----
def narration(rng: random.Random, rail: str, counterparty: str, ref: str) -> str:
    cp = counterparty.upper()[:22]
    if rail == "NEFT":
        return f"NEFT CR-{rng.choice(BANKS)[0]}00{rng.randint(10000, 99999)}-{cp}-{ref}"
    if rail == "RTGS":
        return f"RTGS CR-{rng.choice(BANKS)[0]}R{rng.randint(10**9, 10**10)}-{cp}-{ref}"
    if rail == "IMPS":
        return f"MMT/IMPS/{ref}/{cp}/{rng.choice(BANKS)[1].split()[0]}"
    if rail == "UPI":
        return f"UPI/{ref}/Settlement/{cp}/{rng.choice(BANKS)[0].lower()}"
    return f"{rail} {cp} {ref}"
