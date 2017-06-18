import unittest

from homeassistant.const import EVENT_TIME_CHANGED

from hass_aggregator import AggrMaxEvery, ATTR_METHOD, CONF_METHOD_MAX_EVERY, \
    ATTR_CYCLE, ATTR_AGGREGATOR


class TestAggrMaxEvery(unittest.TestCase):
    def setUp(self):
        _aggregator = {ATTR_METHOD: CONF_METHOD_MAX_EVERY,
                       ATTR_CYCLE: 10}
        self.aggr = AggrMaxEvery(_aggregator)

    def test_time_bucket(self):
        # self.aggr._old_bucket = 0
        _bucket = self.aggr._is_new_time_bucket(1)
        self.assertFalse(_bucket)
        self.assertEqual(self.aggr._current_bucket,0)
        _bucket = self.aggr._is_new_time_bucket(5)
        self.assertFalse(_bucket)
        _bucket = self.aggr._is_new_time_bucket(11)
        self.assertTrue(_bucket)
        self.assertEqual(1, self.aggr._current_bucket)

    def test_max(self):
        self.aggr._check_max(1)
        self.assertEqual(self.aggr._temp_state, 1)
        self.aggr._check_max(3)
        self.assertEqual(self.aggr._temp_state, 3)

    def test_aggregate(self):
        _val = self.aggr._aggregate(EVENT_TIME_CHANGED, 11, 3)
        self.assertIsNone(_val)
        self.assertEqual(self.aggr._current_bucket, 1)
        _val = self.aggr._aggregate('', 15, 7)
        self.assertIsNone(_val)
        self.assertEqual(self.aggr._temp_state, 7)
        _val = self.aggr._aggregate('', 15, 5)
        self.assertIsNone(_val)
        self.assertEqual(self.aggr._temp_state, 7)
        self.assertEqual(self.aggr._last_recorded_value, 5)
        _val = self.aggr._aggregate(EVENT_TIME_CHANGED,20,5)
        self.assertEqual(_val,7)
        self.assertEqual(self.aggr._last_recorded_value,5)

