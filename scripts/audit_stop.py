import requests
from google.transit import gtfs_realtime_pb2

# THE SCHEDULE FEED
UPDATE_URL = "https://gtfs-rt.gcrta.vontascloud.com/TMGTFSRealTimeWebService/TripUpdate/TripUpdates.pb"
HEADERS = {'User-Agent': 'WIMBAC-Transit-Monitor/1.0'}

def deep_audit(target_stop_id):
    target = str(target_stop_id).strip().zfill(5)
    print(f"--- Deep Auditing Schedule for Stop: {target} ---")
    
    try:
        response = requests.get(UPDATE_URL, headers=HEADERS, timeout=15)
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        trips_serving_stop = 0
        
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                tu = entity.trip_update
                # Look through every upcoming stop for this specific bus
                for stop_time in tu.stop_time_update:
                    if stop_time.stop_id == target:
                        trips_serving_stop += 1
                        print(f"FOUND: Route {tu.trip.route_id} (Trip {tu.trip.trip_id}) is heading to {target}")

        if trips_serving_stop == 0:
            print(f"\nRESULT: No active buses in the city have Stop {target} on their current itinerary.")
        else:
            print(f"\nRESULT: {trips_serving_stop} buses are currently scheduled for this stop.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deep_audit("02675")
    deep_audit("07746")