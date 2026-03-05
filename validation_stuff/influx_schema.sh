influx query --host "$INFLUX_URL" --org "$INFLUX_ORG" --token "$INFLUX_TOKEN" '
import "influxdata/influxdb/schema"

m = schema.measurements(bucket:"wimbac")

f = schema.fieldKeys(bucket:"wimbac")
  |> sort(columns:[" _value"])

t = schema.tagKeys(bucket:"wimbac")
  |> sort(columns:[" _value"])

union(tables: [m, f, t])
'
