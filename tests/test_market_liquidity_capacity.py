import unittest
from types import SimpleNamespace
from collector.market_liquidity_capacity import execution_costs_bps, NOTIONALS_USD

class CapacityTests(unittest.TestCase):
    def test_flat_book_spread(self):
        b = SimpleNamespace(mid=100.0, bids={99.9:10000.0}, asks={100.1:10000.0})
        cost = execution_costs_bps(b)
        self.assertAlmostEqual(cost["sell_cost_500000_bps"], 10.0, places=7)
        self.assertAlmostEqual(cost["buy_cost_500000_bps"], 10000*(1-100.0/100.1), places=7)
    def test_thin_book_nonfillable(self):
        b = SimpleNamespace(mid=100.0, bids={99.0:150.0}, asks={101.0:150.0})
        cost = execution_costs_bps(b)
        self.assertIsNotNone(cost["sell_cost_10000_bps"])
        self.assertIsNone(cost["sell_cost_50000_bps"])
        self.assertIsNone(cost["buy_cost_50000_bps"])
    def test_quote_conversion(self):
        b = SimpleNamespace(mid=100.0, bids={99.9:6000.0, 99.8:6000.0},
                            asks={100.1:6000.0, 100.2:6000.0})
        result = execution_costs_bps(b, quote_to_usdt=0.99)
        self.assertTrue(0 < result["sell_cost_500000_bps"] < 50)
        self.assertTrue(0 < result["buy_cost_500000_bps"] < 50)
    def test_all_notional_columns(self):
        b = SimpleNamespace(mid=100.0, bids={99.0:1000000.0}, asks={101.0:1000000.0})
        result = execution_costs_bps(b)
        self.assertEqual(len(result), 2 * len(NOTIONALS_USD))
        self.assertTrue(all(value is not None for value in result.values()))
