influx query --host "$INFLUX_URL" --org "$INFLUX_ORG" --token "$INFLUX_TOKEN" '
from(bucket:"wimbac")
  |> range(start: -30m)
  |> filter(fn:(r)=> r._measurement == "vehicle_status")
  |> filter(fn:(r)=> r._field == "lat" or r._field == "lon")
  |> group(columns:["vehicle_id","_field"])
  |> last()
  |> pivot(rowKey:["vehicle_id"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns:["vehicle_id","lat","lon"])
  |> limit(n: 50)
'
