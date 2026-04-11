influx query 'import "influxdata/influxdb/schema"
schema.measurements(bucket: "wimbac")'

influx query 'import "influxdata/influxdb/schema"
schema.tagKeys(bucket: "wimbac")'

influx query 'import "influxdata/influxdb/schema"
schema.fieldKeys(bucket: "wimbac")'

influx query 'import "influxdata/influxdb/schema"
schema.tagValues(bucket: "wimbac", tag: "vehicle_id")'

schema.measurements(bucket: "wimbac")'
Result: _result
Table: keys: []
         _value:string
----------------------
           stop_events
stop_events_backfil...
        vehicle_status


schema.tagKeys(bucket: "wimbac")'
Result: _result
Table: keys: []
         _value:string
----------------------
                _start
                 _stop
                _field
          _measurement
          direction_id
          next_stop_id
              route_id
            start_date
               stop_id
               trip_id
            vehicle_id
         vehicle_label


schema.fieldKeys(bucket: "wimbac")'
Result: _result
Table: keys: []
         _value:string
----------------------
               bearing
         delay_seconds
                   lat
                   lon
    next_stop_sequence
               on_time
scheduled_departure...
             speed_mps
          tu_timestamp
          vp_timestamp