import copy
import json
import unittest

from price_change_detector import PriceChangeDetector
from spotify import detect_currency, extract_price_number, extract_spotify_prices
from spotify_rate_converter import process_spotify_data, sort_by_family_plan_cny
from validate_price_coverage import validate


def next_page(components):
    payload = {"props": {"pageProps": {"components": components}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + '</script>'


def offer(name, primary, secondary=None):
    return dict(planId="PREMIUM_" + name.upper(), isRecurringProduct=True,
                primaryPriceDescription=primary, secondaryPriceDescription=secondary)


def export_record(name, value):
    return dict(plan="Premium " + name, price_cny=value, price_number=str(value),
                price=f"BDT {value}/month", currency="BDT")


class SpotifyPricesTests(unittest.TestCase):
    def test_voyager_recurring_bangladesh_and_invalid_components(self):
        html = next_page([None, {"name": "SpotlightSection", "attributes": {"plans": [
            [], offer("individual", "BDT 0 for 3 months", "BDT 219/month after"),
            offer("family", "BDT 379 / month"), offer("student", "BDT 109 for 2 months"),
            offer("duo", "BDT 200 / month") | {"isRecurringProduct": False},
        ]}}])
        self.assertEqual([(x["plan"], extract_price_number(x["price"])) for x in extract_spotify_prices(html)],
                         [("Premium Individual", 219), ("Premium Family", 379)])

    def test_legacy_and_explicit_currency(self):
        html = next_page({"storefront": {"plans": [offer("family", "US$5.79 / month")]}})
        self.assertEqual(extract_spotify_prices(html)[0]["price"], "US$5.79 / month")
        self.assertEqual(detect_currency("US$5.79 / month", "HK"), "USD")
        self.assertEqual(extract_price_number("VND 149\u202f000 / month"), 149000)

    def test_currency_resolves_market_symbols_without_guessing_usd(self):
        examples = (
            ("RM 27.90 / month", "MY", "MYR"), ("Ksh 669 / month", "KE", "KES"),
            ("TSh 13,000 / month", "TZ", "TZS"), ("毎月 $298", "TW", "TWD"),
            ("$8.250 al mes", "CL", "CLP"), ("229 kr. / month", "DK", "DKK"),
            ("219 kr / month", "NO", "NOK"), ("US$ 5.79 / month", "MY", "USD"),
            ("€9.97/month", "BG", "EUR"), ("S/ 32.90 al mes", "PE", "PEN"),
            ("12,50 DT/mois", "TN", "TND"), ("Rp 59.900/month", "ID", "IDR"),
            ("$23.99 / month", "CA", "CAD"), ("$19.99 / month", None, ""),
            ("GH₵43 / month", "GH", "GHS"), ("half price for 2 months", "MY", ""),
        )
        for price, market, expected in examples:
            with self.subTest(price=price, market=market):
                self.assertEqual(detect_currency(price, market), expected)

    def test_card_prices_stay_with_their_own_plans(self):
        html = """<div><h3>Student</h3><p>HK$0 for 1 month</p><p>HK$48/month after</p></div>
                  <div><h3>Duo</h3><p>HK$98 / month</p></div>
                  <div><h3>Family</h3><p>HK$128 / month</p></div>
                  <div><h3>Individual</h3><div><p>HK$98 / month</p></div></div>"""
        plans = extract_spotify_prices(html)
        for plan in plans:
            plan["currency"] = detect_currency(plan["price"], "HK")
            plan["price_number"] = extract_price_number(plan["price"])
        plans.append(dict(plan="Premium Individual", source="regex_parsing", price="$98", price_number=98, currency="HKD"))
        data = {"HK": {"plans": plans}}
        out = process_spotify_data(data, {"CNY": 7, "HKD": 7})
        self.assertEqual({p["plan"]:p["price_cny"] for p in out["HK"]["plans"]},
                         {"Premium Student": 48, "Premium Duo": 98, "Premium Family": 128, "Premium Individual": None})
        self.assertEqual(sort_by_family_plan_cny(out, data)["_top_10_cheapest_premium_family"]["data"][0]["price_number"], "128")

    def test_nonempty_ranking_does_not_hide_coverage_loss(self):
        baseline = {str(i): {"plans": [export_record(p, i + 1) for p in ("Family", "Individual", "Duo", "Student")]}
                    for i in range(20)}
        candidate = {k: v for k, v in baseline.items() if int(k) < 10}
        candidate["_top_10_cheapest_premium_family"] = {"updated_at":"2026-11-26", "data":[
            {"country_code":str(i), "price_cny":i+1} for i in range(10)]}
        with self.assertRaisesRegex(ValueError, "coverage check failed"):
            validate(candidate, baseline, "2026-11-26")
        healthy = copy.deepcopy(baseline)
        healthy["_top_10_cheapest_premium_family"] = candidate["_top_10_cheapest_premium_family"]
        validate(healthy, baseline, "2026-11-26")

    def test_change_detector_uses_plans_and_ignores_fx_only(self):
        old = {"BD": {"plans": [export_record("Family", 10), export_record("Duo", 8)]}}
        new = {"BD": {"plans": [export_record("Family", 12) | {"price_cny": 6},
                                export_record("Duo", 8) | {"price_cny": 4}]}}
        changes = PriceChangeDetector().compare_prices(old, new)
        self.assertEqual([(c["plan"],c["type"],c["old_price_cny"],c["new_price_cny"]) for c in changes],
                         [("Premium Family","price_change",5.0,6.0)])


if __name__ == "__main__":
    unittest.main()
