# HASS aggregator

Work in progress..

An attempt to aggregate sensor data and have them written to the database.
It allows for minimizing the amount of data sent to the database without completely skipping any logging of sensor data.


```bash
yaml
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

average : not done
max : done
min : done
skip: done
cap : not done
sum : not done
cap : not done
sun : not done # special case with capping and skipping.
```

The original `entity_id` will be rewritten as `hass_aggregator_<domain>_<id>_<aggregator_name>`
