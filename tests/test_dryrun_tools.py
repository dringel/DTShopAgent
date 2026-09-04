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


class ProfileStatsTests(unittest.TestCase):
    """P0.2: aggregate claims are reconciled against ground truth.

    The ASIN/price/brand checks are per-claim and exempt anything that
    reads as a computed statistic (DERIVED_HINTS) — deliberately, since
    "average order value" is not any single order's amount. That left a
    gap the 30 Aug live bootstrap fell straight through: a wrong average,
    a double-counted cancelled duplicate inflating the order count, and a
    category split that does not sum to 100% all passed clean, because
    nothing computed what the real numbers were and compared. These
    tests cover order_stats() (the ground-truth arithmetic),
    stats_problems() (reconciliation against the mandatory Summary
    Stats block from agent/SOUL_bootstrap.md), and
    category_share_problems() (the internal-consistency-only check —
    capture_orders.py has no category field to reconcile against).
    """

    def setUp(self):
        # one multi-item order (O2, two line items sharing one total) is
        # the exact shape that caused the live double-count: a validator
        # that counts LINE ITEMS instead of distinct ORDER IDS would say
        # 3 orders here instead of 2
        self.items = [
            {"asin": "B0000001", "title": "boAt Stone Speaker",
             "order_id": "O1", "order_total": 304.0,
             "amounts_seen": [304.0]},
            {"asin": "B0000002", "title": "Pringles Potato Crisps",
             "order_id": "O2", "order_total": 900.0,
             "amounts_seen": [900.0]},
            {"asin": "B0000003", "title": "Colgate Toothpaste",
             "order_id": "O2", "order_total": 900.0,
             "amounts_seen": [900.0]},
        ]
        self.asins = {i["asin"] for i in self.items}
        self.titles = " | ".join(i["title"] for i in self.items).lower()
        self.amounts = {304.0, 900.0}

    def test_order_stats_counts_distinct_orders_not_line_items(self):
        truth = validate_profile.order_stats(self.items)
        self.assertEqual(truth["n_orders"], 2)          # O1, O2 — not 3
        self.assertEqual(truth["n_line_items"], 3)
        self.assertEqual(truth["total_spend"], 1204.0)   # 304 + 900, once
        self.assertAlmostEqual(truth["avg_order_value"], 602.0)

    def test_order_stats_ignores_items_with_no_order_id(self):
        items = self.items + [{"asin": "B0000004", "title": "no-order-id",
                                "order_total": 50.0}]
        truth = validate_profile.order_stats(items)
        self.assertEqual(truth["n_orders"], 2)           # unchanged
        self.assertEqual(truth["n_line_items"], 4)       # still counted

    def _profile(self, n_orders=2, n_items=3, total="1,204",
                 avg="602", categories="Grocery 40%, Beauty 60%"):
        return f"""# Purchase Profile: participant DT2026-999

## Summary Stats
Completed orders: {n_orders}
Purchased line items: {n_items}
Total spend: ₹{total}
Average order value: ₹{avg}

## Observations
Top categories: {categories}
- boAt Stone Speaker B0000001 — ₹304

## Inferences
- Buys the same snack brands repeatedly.
- Prefers mid-range electronics.
- Shows no seasonal spending spikes.
"""

    def test_well_formed_profile_has_no_stats_problems(self):
        problems = validate_profile.check(
            self._profile(), self.asins, self.titles, self.amounts,
            self.items, strict_brands=False)
        self.assertEqual([p for p in problems if p[0] == "STATS"], [])

    def test_double_counted_order_is_caught(self):
        profile = self._profile(n_orders=3)   # the live-log failure shape
        problems = validate_profile.stats_problems(profile, self.items)
        self.assertTrue(any(
            "Completed orders" in what for _, what, _ in problems))

    def test_wrong_average_is_caught_but_one_rupee_rounding_is_not(self):
        exact = self._profile(avg="602")
        rounded = self._profile(avg="602.7")     # within the ₹1 tolerance
        wrong = self._profile(avg="3,200")
        self.assertEqual(
            validate_profile.stats_problems(exact, self.items), [])
        self.assertEqual(
            validate_profile.stats_problems(rounded, self.items), [])
        problems = validate_profile.stats_problems(wrong, self.items)
        self.assertTrue(any(
            "Average order value" in what for _, what, _ in problems))

    def test_wrong_total_spend_is_caught(self):
        problems = validate_profile.stats_problems(
            self._profile(total="9,999"), self.items)
        self.assertTrue(any(
            "Total spend" in what for _, what, _ in problems))

    def test_missing_summary_stats_block_reports_every_field(self):
        profile = ("# Purchase Profile: participant DT2026-999\n"
                   "## Observations\nsomething\n"
                   "## Inferences\n- a\n- b\n- c\n")
        problems = validate_profile.stats_problems(profile, self.items)
        labels = {what for _, what, _ in problems}
        self.assertEqual(labels, {"Completed orders",
                                   "Purchased line items", "Total spend",
                                   "Average order value"})

    def test_price_ranges_are_derived_not_observations(self):
        # The SOUL asks for "typical price points per category", and the
        # 3 Sep live run supplied them as ranges and was hard-failed:
        # DERIVED_HINTS is matched per LINE, and the profile put the
        # "Typical Price Points" label on a header with the ranges on the
        # bullets below, so the exemption never reached them.
        for line in ("- Electronics: \u20b9350\u2013\u20b91,500 per item",
                     "- Beauty & Personal Care: \u20b9350\u2013400",
                     "- Snacks: \u20b9300\u2013500 per order"):
            with self.subTest(line=line):
                self.assertTrue(validate_profile.is_derived(line))

    def test_a_fabricated_per_item_price_is_still_caught(self):
        # The other half of the same live finding: a two-item order shows
        # only an ORDER total, and the agent split it evenly and presented
        # the halves as observed amounts. Exempting ranges must not exempt
        # this.
        items = [
            {"asin": "B0000010", "title": "Mixed Chips Pack", "order_id": "O9",
             "order_total": 488.0, "amounts_seen": [488.0]},
            {"asin": "B0000011", "title": "Protein Minis Bars", "order_id": "O9",
             "order_total": 488.0, "amounts_seen": [488.0]},
        ]
        line = ("10 Aug 2026 | Snacks > Chips | Brand | Mixed Chips Pack "
                "| 1 | \u20b9244.00")
        self.assertFalse(validate_profile.is_derived(line))
        problems = validate_profile.price_pairing_problems(line, items)
        self.assertTrue(any(kind == "PRICE" for kind, _, _ in problems))
        self.assertTrue(any("488" in why for _, _, why in problems),
                        "the report should name the real order amount")

    def test_both_price_checks_share_one_derived_rule(self):
        # They used to carry the same inline expression twice; a range rule
        # added to one and not the other would fail closed in one path and
        # open in the other.
        src = (REPO / "tools" / "validate_profile.py").read_text()
        self.assertIn("if not vals or is_derived(line):", src)   # pairing
        self.assertIn("derived = is_derived(line)", src)          # check()
        self.assertNotIn("any(h in line.lower() for h in DERIVED_HINTS)", src)

    def test_category_shares_must_sum_to_about_100(self):
        clean = self._profile(categories="Grocery 40%, Beauty 60%")
        broken = self._profile(
            categories="Grocery 40%, Beauty 30%, Home 45%")   # 115%
        self.assertEqual(
            validate_profile.category_share_problems(clean), [])
        problems = validate_profile.category_share_problems(broken)
        self.assertTrue(any(
            "Category percentages" in what for _, what, _ in problems))

    def test_category_shares_sum_across_one_line_not_per_line(self):
        # "Grocery 40%, Beauty 30%, Home 30%" is ONE line with THREE
        # shares — summing "lines" instead of "percentages found" would
        # silently skip this check entirely
        profile = self._profile(
            categories="Grocery 40%, Beauty 30%, Home 30%")
        self.assertEqual(
            validate_profile.category_share_problems(profile), [])
        broken = self._profile(
            categories="Grocery 40%, Beauty 30%, Home 45%")
        problems = validate_profile.category_share_problems(broken)
        self.assertEqual(len(problems), 1)

    def test_stats_block_rupee_lines_do_not_double_report_as_price(self):
        # Total spend/Average order value are sums/derived figures, not
        # any single order's amount — the old per-line PRICE loop must
        # skip them (stats_problems() is the one that reconciles them)
        problems = validate_profile.check(
            self._profile(), self.asins, self.titles, self.amounts,
            self.items, strict_brands=False)
        self.assertEqual([p for p in problems if p[0] == "PRICE"], [])

    def test_schema_header_words_are_not_flagged_as_brands(self):
        problems = validate_profile.check(
            self._profile(), self.asins, self.titles, self.amounts,
            self.items, strict_brands=False)
        flagged = {what for kind, what, _ in problems
                   if kind in ("BRAND", "brand?")}
        self.assertFalse(flagged & {"Stats", "Completed", "Purchased",
                                    "Total"})


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
