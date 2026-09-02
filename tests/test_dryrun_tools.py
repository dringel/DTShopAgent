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
pack_evidence = load_tool("pack_evidence")


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


class PackRedactionTests(unittest.TestCase):
    """P0.1: the pack applies the SAME identity rules as the freeze.

    The 30 Aug live bootstrap leaked an account-holder name into agent-
    written Markdown. Freezing scrubs the two bootstrap artifacts; these
    cover the surfaces it never touched — transcripts, manifest values,
    and the rendered report — all of which funnel through redact_line.
    """

    PLANTED = [
        "# Purchase Profile: Vinita Gupta Rai",
        "Hello, Vinita",
        "Deliver to Vinita Gupta Rai",
        "Address: 12 MG Road, Kota 324005",
        "- Address: 12 MG Road",
        "Shipped to Kota 324005",
        "Account: amzn1.account.ABC-123",
        "call 9876543210 or 98765 43210",
    ]

    def setUp(self):
        # module-level by design (redact_line is the single choke point);
        # restored in tearDown so test order cannot matter
        self._saved = list(pack_evidence.NAME_PATS)
        pack_evidence.NAME_PATS[:] = scrub_profile.name_variants(
            ["Vinita Gupta Rai"])

    def tearDown(self):
        pack_evidence.NAME_PATS[:] = self._saved

    def test_pack_reuses_the_freeze_time_identity_rules(self):
        # The pack imports the scrubber's list rather than restating it,
        # so a rule added at freeze time reaches the pack automatically.
        # (Identity, not `is`: this test file loads scrub_profile once
        # and pack_evidence loads its own copy, so the two module objects
        # differ here while the rule source must not.)
        self.assertEqual(
            [pat.pattern for pat, _ in pack_evidence.IDENTITY_PATTERNS],
            [pat.pattern for pat, _ in scrub_profile.IDENTITY_PATTERNS])
        self.assertNotIn(
            "IDENTITY_PATTERNS = [",
            (REPO / "tools" / "pack_evidence.py").read_text(),
            "the pack must import the rules, never restate them")

    def test_planted_identity_is_removed_and_rescans_clean(self):
        for line in self.PLANTED:
            with self.subTest(line=line):
                self.assertGreater(
                    pack_evidence.scan_text_for_leaks(line), 0,
                    "the scan must see the leak BEFORE redaction")
                out, _ = pack_evidence.redact_text(line)
                for secret in ("Vinita", "Gupta", "Rai", "Kota", "324005",
                               "9876543210", "98765 43210",
                               "amzn1.account", "12 MG Road"):
                    self.assertNotIn(secret, out)
                self.assertEqual(pack_evidence.scan_text_for_leaks(out), 0)

    def test_redaction_is_idempotent(self):
        # the fail-closed scan treats any hit as a real leak, so a rule
        # that re-matched its own output would block every pack
        for line in self.PLANTED:
            with self.subTest(line=line):
                once, _ = pack_evidence.redact_text(line)
                twice, n = pack_evidence.redact_text(once)
                self.assertEqual(once, twice)
                self.assertEqual(n, 0)

    def test_hashes_and_ordinary_text_are_left_alone(self):
        digest = "a3f5b2c1d4e6f7a8b9c0" + "d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6"
        title = "Wireless Mouse 1200 DPI, 2 AA batteries"
        for keep in (digest, title):
            with self.subTest(keep=keep):
                out, n = pack_evidence.redact_text(keep)
                self.assertEqual(out, keep)
                self.assertEqual(n, 0)
                self.assertEqual(pack_evidence.scan_text_for_leaks(keep), 0)

    def test_manifest_values_are_redacted_recursively(self):
        manifest = {"rationale": ["Deliver to Vinita Gupta Rai"],
                    "nested": {"note": "Address: 12 MG Road, Kota 324005"},
                    "sha256": "b" * 64,
                    "count": 7}
        out, n = pack_evidence.redact_obj(manifest)
        self.assertGreater(n, 0)
        self.assertEqual(out["sha256"], "b" * 64)   # hash untouched
        self.assertEqual(out["count"], 7)
        blob = json.dumps(out)
        for secret in ("Vinita", "Gupta", "Rai", "Kota", "324005"):
            self.assertNotIn(secret, blob)

    def test_name_marker_is_never_counted_as_a_surviving_name(self):
        out, _ = pack_evidence.redact_text("Deliver to Vinita")
        self.assertIn("[REDACTED-NAME]", out)
        self.assertEqual(pack_evidence.scan_text_for_leaks(out), 0)

    def test_bootstrap_transcripts_are_excluded_with_a_reason(self):
        decision = pack_evidence.BOOTSTRAP_TRANSCRIPTS
        self.assertFalse(decision["collected"])
        self.assertIn("order history", decision["reason"])


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

    def test_order_card_skips_both_cancellation_spellings(self):
        for spelling in ("Cancelled", "Canceled"):
            with self.subTest(spelling=spelling):
                with self.assertRaisesRegex(ValueError, "cancelled order"):
                    capture_orders.parse_card({
                        "asin": "B012345678",
                        "title": "Duplicate snack order",
                        "card_text": (
                            "Order # 123-1234567-1234567 " + spelling),
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
