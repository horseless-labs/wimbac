influx query --host "$INFLUX_URL" --org "$INFLUX_ORG" --token "$INFLUX_TOKEN" '
import "influxdata/influxdb/schema"

fields =
  schema.fieldKeys(bucket:"wimbac", predicate: (r) => r._measurement == "vehicle_status")
    |> set(key: "kind", value: "field")

tags =
  schema.tagKeys(bucket:"wimbac", predicate: (r) => r._measurement == "vehicle_status")
    |> set(key: "kind", value: "tag")

union(tables:[fields, tags])
  |> keep(columns:["kind", "_value"])
  |> sort(columns:["kind","_value"])
'
