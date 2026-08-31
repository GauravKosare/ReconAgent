"""Realistic multi-format reconciliation dataset generator.

Unlike ``data/generator/generate_dataset.py`` (a minimal, stable CI fixture),
this package models real settlement mechanics and emits data in the actual file
formats a finance team receives:

  * Razorpay Settlement Recon Report  (paise, unix ts, settlement_utr)
  * Bank statement  — SWIFT MT940 / ISO 20022 CAMT.053 / HDFC CSV / ICICI CSV
  * Internal ledger — Zoho Books sales export

See ``docs/DATA_MODEL.md`` for the schemas, the injected scenarios and sources.
"""

from .scenario import Scenario, build_scenario

__all__ = ["Scenario", "build_scenario"]
