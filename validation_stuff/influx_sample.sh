influx query --host "$INFLUX_URL" --org "$INFLUX_ORG" --token "$INFLUX_TOKEN" '
from(bucket:"wimbac")
  |> range(start: -15m)
  |> filter(fn:(r)=> r._measurement == "vehicle_status")
  |> filter(fn:(r)=> r._field == "lat" or r._field == "lon" or r._field == "bearing" or r._field == "speed")
  |> keep(columns: ["_time","_field","_value","vehicle_id","route_id","next_stop_id"])
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 50)
'
