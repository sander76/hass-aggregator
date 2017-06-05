"""yaml
hass-aggregator
    - entity_id: <an id>
      aggregator:
        method: skip
        range: 10
    - entity_id: <an id>
      aggregator:
        method: average
        range: 4
    - entity_id: <an id>
      aggregator:
        method: cap
        upper: <upper value to cap.>
        lower: <lower value to cap.>

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

DOMAIN = 'hass-aggregator'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entities = []

    @callback
    def aggregate(_event):
        new_state = _event.date.get('new_state')
        if new_state:
            for entity in entities:
                entity.aggregate(new_state)

    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        aggregate
    )
    return True


class BaseAggrFunction():
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    def aggregate(self,state):
        raise NotImplemented


class AggrSkip(BaseAggrFunction):
    def __init__(self, aggregator):
        BaseAggrFunction.__init__(self, 'skip')
        self.range = aggregator.get('range')
        self.current_range = 0

    def aggregate(self, state):
        if self.current_range == self.range:
            self.current_range = 0
            return state
        else:
            self.current_range += 1
            return None


def get_aggregator(aggregator: dict) -> BaseAggrFunction:
    _method = aggregator.get('method')
    if _method == 'skip':
        return AggrSkip(aggregator)


class AggregatedEntity(Entity):
    def __init__(self, hass, aggregator):
        self._state = STATE_UNKNOWN
        self.aggregator = get_aggregator(aggregator.get('aggregator'))

        self.id_to_aggregate = aggregator.get('id_to_aggregate')
        self.aggregated_id = '{}.{}'.format(self.id_to_aggregate,
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
    def state(self):
        return self._state
