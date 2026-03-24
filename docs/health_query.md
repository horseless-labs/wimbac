printf "vehicles: "; influx query '
from(bucket: "wimbac")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> keep(columns: ["vehicle_id"])
  |> distinct(column: "vehicle_id")
  |> count()
' --raw 2>/dev/null | awk -F, '$1 == "" && $4 != "" && $4 !~ /_value/ {print $4; exit}'; \
printf " | points_last_2m: "; influx query '
from(bucket: "wimbac")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> count()
  |> group()
  |> sum()
' --raw 2>/dev/null | awk -F, '$1 == "" && $4 != "" && $4 !~ /_value/ {print $4; exit}'; \
printf " | gaps_last_30m: "; influx query '
from(bucket: "wimbac")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> aggregateWindow(every: 1m, fn: count, createEmpty: true)
' --raw 2>/dev/null | awk -F, '
  BEGIN {count=0}
  $1 == "" && $4 != "" && $4 !~ /_value/ { if($4 == 0) count++ }
  END {print count}
'