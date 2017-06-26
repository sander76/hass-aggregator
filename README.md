# HASS aggregator

Work in progress..

An attempt to aggregate sensor data and have them written to the database.
It allows for minimizing the amount of data sent to the database without completely skipping any logging of sensor data.

Put the file into the `custom_components` folder of your config. 
 Add a configuration to your `configuration.yaml`: 

```bash
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

```

The original `entity_id` will be rewritten as `hass_aggregator_<domain>_<id>_<aggregator_name>`
