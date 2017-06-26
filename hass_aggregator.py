"""yaml
hass-aggregator:
    - entity_id: <an id>
      aggregator:
        bucket:
          trigger: state
          size: 10
    - entity_id: <an id>
      aggregator:
        bucket:
          trigger: time
          size: 10 #minutes
        methods:
          - max
          - min
          - average
        active:
          trigger: time
          after: 5
          before: 23

sun # special case with capping and skipping.
"""

import asyncio
import logging

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNKNOWN, \
    EVENT_TIME_CHANGED, ATTR_ENTITY_ID
from homeassistant.core import callback, split_entity_id
from homeassistant.helpers.entity import async_generate_entity_id, Entity
from homeassistant.helpers.entity_component import EntityComponent

CONF_BUCKET = 'bucket'
CONF_BUCKET_TRIGGER = 'trigger'
CONF_BUCKET_SIZE = 'size'
CONF_METHODS = 'methods'
CONF_METHOD_MAX = 'max'
CONF_METHOD_MIN = 'min'
CONF_METHOD_AVG = 'avg'
CONF_AGGREGATOR = 'aggregator'
CONF_ACTIVE = 'active'
CONF_BUCKET_TRIGGER_TIME = 'time'
CONF_BUCKET_TRIGGER_STATE = 'state'

ATTR_TRIGGER_ATTRIBUTE_CHANGE = 'attribute_change'
ATTR_TRIGGER_TIME_CHANGE = 'time_change'

DOMAIN = 'hass_aggregator'

ATTR_NEW_STATE = 'new_state'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = [AggregatedEntity(hass, aggregator)
                for aggregator in config[DOMAIN]]

    @callback
    def aggregate_state(_event):
        for entity in entities:
            entity.aggregate_state(_event)

    @callback
    def aggregate_time(_event):
        for entity in entities:
            entity.aggregate_time(_event)

    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        aggregate_state
    )
    hass.bus.async_listen(
        EVENT_TIME_CHANGED,
        aggregate_time
    )
    yield from component.async_add_entities(entities)
    return True


class ActiveBase:
    def __init__(self):
        self._active = True
        self_previous_state = True

    @property
    def is_active(self):
        return self._active

    def check_active(self, event):
        """method should check if active and set previous value
        as the previous state"""
        return

    @property
    def has_changed(self):
        """Check whether previous and current active values are different"""
        return False


class TimeActive(ActiveBase):
    def __init__(self):
        ActiveBase.__init__(self)

    def check_active(self, event):
        if event.event_type == EVENT_TIME_CHANGED:
            _current_hour = event.data.get('now').hour



class BucketBase:
    def __init__(self, aggregator):
        self._trigger = aggregator.get(CONF_BUCKET_TRIGGER)
        self._size = aggregator.get(CONF_BUCKET_SIZE)
        self._values = []

    def _update_value(self, state_event):
        _val = state_event.data.get(ATTR_NEW_STATE).state
        self._values.append(_val)

    def get_state_attributes(self):
        return {CONF_BUCKET_TRIGGER: self._trigger,
                CONF_BUCKET_SIZE: self._size}

    @property
    def values(self):
        return self._values

    def update_bucket(self, state_event, time_event):
        raise NotImplemented

    def is_new_bucket(self):
        raise NotImplemented

    def flush(self):
        self._values = []


class AttributeChangeBucket(BucketBase):
    def __init__(self, aggregator):
        # Range meaning the amount of attribute values to collect before
        # taking action.
        BucketBase.__init__(self, aggregator)

    def update_bucket(self, state_event, time_event):
        if state_event:
            self._update_value(state_event)

    def is_new_bucket(self):
        return len(self._values) >= self._size


class TimeChangeBucket(BucketBase):
    def __init__(self, aggregator):
        # Range meaning the time range in minutes in which data is to be
        # collected.
        BucketBase.__init__(self, aggregator)
        self._current_bucket = None
        self._current_minute = None

    def update_bucket(self, state_event, time_event):
        if state_event:
            self._update_value(state_event)
        else:
            self._current_minute = time_event.data.get('now').minute

    def is_new_bucket(self):
        if self._current_minute is None:
            _LOGGER.error("no current minute set yet")
            return False
        _bucket = int(self._current_minute / self._size)
        if self._current_bucket is None:
            self._current_bucket = _bucket
            return False
        if _bucket == self._current_bucket:
            return False
        self._current_bucket = _bucket
        return True


def get_bucket(aggregator: dict) -> BucketBase:
    _bucket = aggregator.get(CONF_BUCKET)
    _trigger = _bucket.get(CONF_BUCKET_TRIGGER)
    if _trigger == CONF_BUCKET_TRIGGER_STATE:
        return AttributeChangeBucket(_bucket)
    elif _trigger == CONF_BUCKET_TRIGGER_TIME:
        return TimeChangeBucket(_bucket)
    else:
        _LOGGER.error("undefined bucket")


def get_active_parser(aggregator: dict) -> ActiveBase:
    _active = aggregator.get(CONF_ACTIVE)
    return ActiveBase()


def aggr_max(values):
    return max(values)


def aggr_min(values):
    return min(values)


def aggr_avg(values):
    return sum(values) / len(values)


class AggregatedEntity(Entity):
    def __init__(self, hass, aggregator):
        self._state = STATE_UNKNOWN
        _aggregator = aggregator.get(CONF_AGGREGATOR)
        self._active = get_active_parser(_aggregator)
        self._bucket = get_bucket(_aggregator)
        self._methods = _aggregator.get(CONF_METHODS)
        self.id_to_aggregate = aggregator.get(ATTR_ENTITY_ID)
        _slug_entity_id = ' '.join(split_entity_id(self.id_to_aggregate))
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            _slug_entity_id,
            hass=hass)
        self._state_attributes = self._bucket.get_state_attributes()

    def aggregate_time(self, time_event):
        self._bucket.update_bucket(None, time_event)
        self._aggregate(time_event)

    def aggregate_state(self, state_event):
        if state_event.data.get(ATTR_ENTITY_ID) == self.id_to_aggregate:
            self._bucket.update_bucket(state_event,
                                       None)
            self._aggregate(state_event)

    def _aggregate(self, event):
        self._active.check_active(event)
        if self._active.is_active:
            if self._bucket.is_new_bucket():
                self._process()
        elif self._active.has_changed:
            self._process()

    def _process(self):
        _values = self._bucket.values
        self._bucket.flush()
        self._state_attributes['no_of_values'] = len(_values)
        if len(_values) == 0:
            # get the state of a value.
            _state = self.hass.states.get(self.id_to_aggregate)
            _values.append(_state.state)
        for _method in self._methods:
            if _method == CONF_METHOD_AVG:
                self._state_attributes[CONF_METHOD_AVG] = aggr_avg(_values)
            elif _method == CONF_METHOD_MAX:
                self._state_attributes[CONF_METHOD_MAX] = aggr_max(_values)
            elif _method == CONF_METHOD_MIN:
                self._state_attributes[CONF_METHOD_MIN] = aggr_min(_values)
        self._state = _values[-1]

    # process the collected data using the attached methods.

    @property
    def state_attributes(self):
        return self._state_attributes

    @property
    def state(self):
        return self._state
