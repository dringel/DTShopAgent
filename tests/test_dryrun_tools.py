#!/usr/bin/env python3
"""Focused regression tests for the post-dry-run safety tools."""

import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_tool(name):
    """Import a standalone tool without requiring tools to be a package."""
    path = REPO / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture_orders = load_tool("capture_orders")
capture_tokens = load_tool("capture_tokens")
scrub_profile = load_tool("scrub_profile")
validate_profile = load_tool("validate_profile")


class ScrubProfileTests(unittest.TestCase):
    def test_scrub_is_deterministic_and_keeps_age(self):
        text = """# Purchase Profile: Vinita Gupta Rai
Age: 31
Hello, Vinita
Address: Kota 324005
Phone: +91 98765 43210
Email: vinita@example.com
Account: amzn1.account.ABC-123
"""
        pats = scrub_profile.name_variants(["Vinita Gupta Rai"])
        out, count = scrub_profile.scrub(text, "DT2026-999", pats)

        self.assertGreaterEqual(count, 6)
        self.assertIn("participant DT2026-999", out)
        self.assertIn("Age: 31", out)
        for secret in ("Vinita", "Gupta", "Rai", "Kota", "324005",
                       "98765", "vinita@example.com", "amzn1.account"):
            self.assertNotIn(secret, out)

        again, second_count = scrub_profile.scrub(
            out, "DT2026-999", pats)
        self.assertEqual(again, out)
        self.assertEqual(second_count, 0)


class OrderValidationTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"asin": "B012345678", "title": "boAt Stone Speaker",
             "order_total": 304.0, "amounts_seen": [304.0]},
            {"asin": "B087654321", "title": "Pringles Potato Crisps",
             "order_total": 504.0, "amounts_seen": [504.0]},
        ]
        self.asins = {item["asin"] for item in self.items}
        self.titles = " | ".join(item["title"] for item in self.items).lower()
        self.amounts = {304.0, 504.0}

    def test_order_card_parser_keeps_reconciliation_fields(self):
        parsed = capture_orders.parse_card({
            "asin": "B012345678",
            "title": "boAt Stone Speaker",
            "card_text": (
                "Ordered on 18 August 2026 Order # 123-1234567-1234567 "
                "Order Total ₹1,299.00 Item ₹304.00"),
        })
        self.assertEqual(parsed["order_id"], "123-1234567-1234567")
        self.assertEqual(parsed["order_date"], "18 August 2026")
        self.assertEqual(parsed["order_total"], 1299.0)
        self.assertEqual(parsed["amounts_seen"], [1299.0, 304.0])

    def test_order_card_chooses_title_not_image_price_or_action_link(self):
        parsed = capture_orders.parse_card({
            "asin": "B012345678",
            "title_candidates": [
                "-56%",
                "₹999.00₹999.00",
                "See all buying options",
                "Wipro 16A Wi-Fi Smart Plug with Energy Monitoring",
            ],
            "card_text": "Order # 123-1234567-1234567 ₹999.00",
        })
        self.assertEqual(
            parsed["title"],
            "Wipro 16A Wi-Fi Smart Plug with Energy Monitoring")

    def test_order_card_rejects_page_wide_multi_order_container(self):
        with self.assertRaisesRegex(ValueError, "multiple order ids"):
            capture_orders.parse_card({
                "asin": "B012345678",
                "title": "A real product",
                "card_text": (
                    "Order # 123-1234567-1234567 ₹999.00 "
                    "Order # 456-7654321-7654321 ₹589.00"),
            })

    def test_profile_checker_catches_invention_and_cross_order_price(self):
        profile = """# Purchase Profile: participant DT2026-999
- boAt Stone Speaker B012345678 — ₹504
- Invented Heater B099999999 — ₹999
- Nykaa preference
"""
        problems = validate_profile.check(
            profile, self.asins, self.titles, self.amounts,
            self.items, strict_brands=False)
        kinds = [problem[0] for problem in problems]

        self.assertIn("ASIN", kinds)
        self.assertIn("PRICE", kinds)
        self.assertIn("brand?", kinds)
        self.assertTrue(any(
            "real amount" in why for kind, _, why in problems
            if kind == "PRICE"))
        self.assertFalse(any(kind == "BRAND" for kind in kinds))


class TokenCaptureTests(unittest.TestCase):
    def test_scan_accepts_json_and_jsonl_usage_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "session.json").write_text(json.dumps({
                "usage": {"input_tokens": 100, "output_tokens": 20,
                          "cache_creation_input_tokens": 7}
            }), encoding="utf-8")
            (root / "events.jsonl").write_text(
                json.dumps({"prompt_tokens": 10, "completion_tokens": 5})
                + "\nnot-json\n"
                + json.dumps({"nested": {"inputTokens": 3,
                                          "outputTokens": 2,
                                          "cache_read_input_tokens": 4}})
                + "\n", encoding="utf-8")

            usage = capture_tokens.scan(root)

        self.assertEqual(usage, {
            "input": 113, "output": 27, "cache": 11,
            "records": 3, "files": 2,
        })

    def test_sonnet_rate_switches_after_intro_cutoff(self):
        intro, intro_basis = capture_tokens.price_for(
            "claude-sonnet-5-20260801", date(2026, 8, 31))
        standard, standard_basis = capture_tokens.price_for(
            "claude-sonnet-5-20260801", date(2026, 9, 1))

        self.assertEqual((intro, intro_basis), ((2.0, 10.0),
                                               "introductory"))
        self.assertEqual((standard, standard_basis), ((3.0, 15.0),
                                                     "standard"))


if __name__ == "__main__":
    unittest.main()
