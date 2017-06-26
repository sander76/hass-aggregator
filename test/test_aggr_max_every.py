import unittest

from homeassistant.const import EVENT_TIME_CHANGED
from hass_aggregator import TimeChangeBucket, CONF_BUCKET, CONF_BUCKET_TRIGGER, \
    CONF_BUCKET_TRIGGER_TIME, CONF_BUCKET_SIZE, get_bucket


class TestAggrMaxEvery(unittest.TestCase):
    def setUp(self):
        self.aggregator = {
            CONF_BUCKET: {
                CONF_BUCKET_TRIGGER: CONF_BUCKET_TRIGGER_TIME,
                CONF_BUCKET_SIZE: 10
            }
        }
        self.time_bucket = get_bucket(self.aggregator)

    def test_type(self):
        self.assertIsInstance(self.time_bucket,TimeChangeBucket)

    def test_time_bucket(self):
        # self.aggr._old_bucket = 0
        self.time_bucket._current_minute = 1
        self.assertFalse(self.time_bucket.is_new_bucket())
        self.time_bucket._current_minute=10
        self.assertTrue(self.time_bucket.is_new_bucket())

