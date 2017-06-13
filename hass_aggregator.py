"""yaml
hass-aggregator:
    - entity_id: <an id>
      aggregator:
        method: skip
        range: 10
    - entity_id: <an id>
      aggregator:
        method: max
        range: 4
    - entity_id: <an id>
      aggregator:
        method: maxevery
        cycle: 10 minutes
    - entity_id: <an id>
      aggregator:
        method: cap
        upper: <upper value to cap.>
        lower: <lower value to cap.>

average
max
maxevery
min
minevery
cap
sum
sun # special case with capping and skipping.
"""

import asyncio
import logging

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNKNOWN, \
    EVENT_TIME_CHANGED, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers.entity import async_generate_entity_id, Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'hass_aggregator'

ATTR_NEW_STATE = 'new_state'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)

CONF_METHOD = 'method'
CONF_METHOD_EVERY = 'every'
CONF_METHOD_MAX = 'max'
CONF_METHOD_MIN = 'min'
CONF_METHOD_SKIP = 'skip'
CONF_METHOD_MAX_EVERY = 'maxevery'
CONF_CYCLE = 'cycle'
CONF_RANGE = 'range'


@asyncio.coroutine
def async_setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = [AggregatedEntity(hass, aggregator)
                for aggregator in config[DOMAIN]]

    @callback
    def aggregate(_event):
        # new_state = _event.data.get('new_state')
        if _event.event_type == EVENT_STATE_CHANGED or _event.event_type == EVENT_TIME_CHANGED:
            for entity in entities:
                entity.aggregate(_event)

    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        aggregate
    )
    hass.bus.async_listen(
        EVENT_TIME_CHANGED,
        aggregate
    )
    yield from component.async_add_entities(entities)
    return True


class BaseAggrFunction:
    def __init__(self, name, range_=None, cycle=None):
        self._temp_state = None
        self._name = name
        self._timed = False
        self._old_bucket_value = None
        self._attributes = {CONF_METHOD: name}
        if range_:
            self._range = range_
            self._attributes[CONF_RANGE] = range_
            self._current_range = 0
        if cycle:
            self._cycle = cycle
            self._attributes[CONF_CYCLE] = cycle

    @property
    def timed(self):
        return self._timed

    @property
    def name(self):
        return self._name

    def _check_range(self):
        if self._current_range == self._range:
            self._current_range = 0
            return True
        else:
            self._current_range += 1
            return False

    def _is_new_time_bucket(self, state):
        minute = state.get('now').minute
        _bucket = int(minute / self._cycle)
        if _bucket == self._old_bucket_value:
            return False
        else:
            self._old_bucket_value=_bucket


    def aggregate(self, state):
        raise NotImplemented


class AggrMaxEvery(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, CONF_METHOD_MAX_EVERY,
                                  cycle=aggregator.get(CONF_CYCLE))
        self._timed = True


    def _check_max(self, new_val):
        if self._temp_state is None:
            self._temp_state = new_val
        else:
            self._temp_state = max(self._temp_state, new_val)

    def aggregate(self, event):
        if event.event_type == EVENT_TIME_CHANGED:
            if self._is_new_time_bucket(event):
                if self._temp_state is not None:
                    self._old_bucket_value = self._temp_state
                    self._temp_state = None
                return self._old_bucket_value
            else:
                return None
        else:
            self._check_max(event.data.get(ATTR_NEW_STATE).state)


class AggrSkip(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, CONF_METHOD_SKIP,
                                  range_=aggregator.get(CONF_RANGE))

    def aggregate(self, event):
        if self._check_range():
            return event.data.get(ATTR_NEW_STATE).state
        else:
            return None


class AggrMax(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, CONF_METHOD_MAX,
                                  range_=aggregator.get(CONF_RANGE))

    def _check_max(self, new_val):
        if self._temp_state is None:
            self._temp_state = new_val
        else:
            self._temp_state = max(self._temp_state, new_val)

    def aggregate(self, event):
        self._check_max(event.data.get(ATTR_NEW_STATE).state)
        if self._check_range():
            return self._temp_state
        else:
            return None


class AggrMin(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, CONF_METHOD_MIN,
                                  range_=aggregator.get(CONF_RANGE))

    def _check_min(self, new_val):
        if self._temp_state is None:
            self._temp_state = new_val
        else:
            self._temp_state = min(self._temp_state, new_val)

    def aggregate(self, event):
        self._check_min(event.data.get(ATTR_NEW_STATE).state)
        if self._check_range():
            return self._temp_state
        else:
            return None


def get_aggregator(aggregator: dict) -> BaseAggrFunction:
    _method = aggregator.get(CONF_METHOD)
    if _method == CONF_METHOD_SKIP:
        return AggrSkip(aggregator)
    elif _method == CONF_METHOD_MAX:
        return AggrMax(aggregator)
    elif _method == CONF_METHOD_MIN:
        return AggrMin(aggregator)
    elif _method == CONF_METHOD_MAX_EVERY:
        return AggrMaxEvery(aggregator)
    else:
        _LOGGER.error("undefined aggregator method.")


class AggregatedEntity(Entity):
    def __init__(self, hass, aggregator):
        self._state = STATE_UNKNOWN
        self.aggregator = get_aggregator(aggregator.get('aggregator'))

        self.id_to_aggregate = aggregator.get(ATTR_ENTITY_ID)
        self.aggregated_id = '{} {}'.format(
            self.id_to_aggregate.replace('.', ' '),
            self.aggregator.name)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            self.aggregated_id,
            hass=hass)

    def aggregate(self, event):
        _state = None

        _entity_id = event.data.get(ATTR_ENTITY_ID)
        _check_by_id = _entity_id == self.id_to_aggregate
        if ((self.aggregator.timed and event.event_type == EVENT_TIME_CHANGED)
            or _check_by_id):
            _state = self.aggregator.aggregate(event)
        if _state:
            self._state = _state

    @property
    def state_attributes(self):
        return self.aggregator._attributes

    @property
    def state(self):
        return self._state
