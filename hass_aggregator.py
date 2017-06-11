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
        method: cap
        upper: <upper value to cap.>
        lower: <lower value to cap.>

average
max
min
cap
sum
sun # special case with capping and skipping.
"""

import asyncio
import logging

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.entity import async_generate_entity_id, Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'hass_aggregator'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = [AggregatedEntity(hass, aggregator)
                for aggregator in config[DOMAIN]]

    @callback
    def aggregate(_event):
        new_state = _event.data.get('new_state')
        if new_state:
            for entity in entities:
                entity.aggregate(new_state)

    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        aggregate
    )
    yield from component.async_add_entities(entities)
    return True


class BaseAggrFunction():
    def __init__(self, name, range=None):
        self._temp_state = None
        self._name = name
        self._attributes = {"method": name}
        if range:
            self._range = range
            self._attributes['range'] = range
            self._current_range = 0

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

    def aggregate(self, state):
        raise NotImplemented


class AggrSkip(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, 'skip',
                                  range=aggregator.get('range'))

    def aggregate(self, state):
        if self._check_range():
            return state
        else:
            return None


class AggrMax(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, 'max', range=aggregator.get('range'))

    def _check_max(self, new_val):
        if self._temp_state is None:
            self._temp_state = new_val
        else:
            self._temp_state = max(self._temp_state, new_val)

    def aggregate(self, state):
        self._check_max(state)
        if self._check_range():
            return self._temp_state
        else:
            return None


class AggrMin(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, 'min', range=aggregator.get('range'))

    def _check_min(self, new_val):
        if self._temp_state is None:
            self._temp_state = new_val
        else:
            self._temp_state = min(self._temp_state, new_val)

    def aggregate(self, state):
        self._check_min(state)
        if self._check_range():
            return self._temp_state
        else:
            return None


def get_aggregator(aggregator: dict) -> BaseAggrFunction:
    _method = aggregator.get('method')
    if _method == 'skip':
        return AggrSkip(aggregator)
    elif _method == 'max':
        return AggrMax(aggregator)
    elif _method == 'min':
        return AggrMin(aggregator)


class AggregatedEntity(Entity):
    def __init__(self, hass, aggregator):
        self._state = STATE_UNKNOWN
        self.aggregator = get_aggregator(aggregator.get('aggregator'))

        self.id_to_aggregate = (aggregator.get('entity_id')).replace('.', ' ')
        self.aggregated_id = '{} {}'.format(self.id_to_aggregate,
                                            self.aggregator.name)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            self.aggregated_id,
            hass=hass)

    def aggregate(self, new_state):
        if new_state.entity_id == self.id_to_aggregate:
            _state = self.aggregator.aggregate(new_state.state)
            if _state:
                self._state = _state

    @property
    def state_attributes(self):
        return self.aggregator._attributes

    @property
    def state(self):
        return self._state
