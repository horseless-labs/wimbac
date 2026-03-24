#!/bin/bash

# Configuration - Change these or set them as ENV vars
BUCKET="${INFLUX_BUCKET:-wimbac}"
MEASUREMENT="${INFLUX_MEASUREMENT:-vehicle_status}"
INTERVAL="${1:-10}" # Refresh interval in seconds (default 10)

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Monitoring InfluxDB Ingestion for bucket: ${BUCKET}...${NC}"
echo "Press [CTRL+C] to stop."
echo "------------------------------------------------------------"

while true; do
    TIMESTAMP=$(date +"%H:%M:%S")

    # 1. Active Vehicles (Distinct IDs in last 2m)
    VEHICLES=$(influx query "from(bucket: \"$BUCKET\") |> range(start: -2m) |> filter(fn: (r) => r._measurement == \"$MEASUREMENT\") |> keep(columns: [\"vehicle_id\"]) |> distinct(column: \"vehicle_id\") |> count()" --raw 2>/dev/null | awk -F, '$1 == "" && $4 != "" && $4 !~ /_value/ {print $4; exit}')
    
    # 2. Total Points (Sum of counts in last 2m)
    POINTS=$(influx query "from(bucket: \"$BUCKET\") |> range(start: -2m) |> filter(fn: (r) => r._measurement == \"$MEASUREMENT\") |> count() |> group() |> sum()" --raw 2>/dev/null | awk -F, '$1 == "" && $4 != "" && $4 !~ /_value/ {print $4; exit}')

    # 3. Gaps (Minutes with 0 points in last 30m)
    GAPS=$(influx query "from(bucket: \"$BUCKET\") |> range(start: -30m) |> filter(fn: (r) => r._measurement == \"$MEASUREMENT\") |> aggregateWindow(every: 1m, fn: count, createEmpty: true)" --raw 2>/dev/null | awk -F, 'BEGIN {c=0} $1 == "" && $4 != "" && $4 !~ /_value/ {if($4 == 0) c++} END {print c}')

    # Default to 0 if variables are empty
    VEHICLES=${VEHICLES:-0}
    POINTS=${POINTS:-0}
    GAPS=${GAPS:-0}

    # Color logic for Gaps (Red if there are any gaps)
    GAP_COLOR=$GREEN
    [[ "$GAPS" -gt 0 ]] && GAP_COLOR=$RED

    # Output line
    printf "[%s] Vehicles: %-5s | Points(2m): %-7s | Gaps(30m): %b%s%b\n" \
        "$TIMESTAMP" "$VEHICLES" "$POINTS" "$GAP_COLOR" "$GAPS" "$NC"

    sleep "$INTERVAL"
done