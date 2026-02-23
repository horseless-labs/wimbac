from flask import Flask, render_template, jsonify

# TODO: make this less sloppy later
from merge_feeds import *

app = Flask(__name__)

@app.route('/')
def home():
    """Serves the actual map"""
    return render_template("index.html")

@app.route('/data')
def get_bus_data():
    """The API endpoint the map calls every X seconds"""
    # Call existing merge function
    merged_data = merge_trip_updates_and_positions(update_url, pos_url)

    # Only use vehicles that have a map location
    live_vehicles = [v for v in merged_data if v.get('lat')]

    return jsonify(live_vehicles)

@app.route('/api/vehicles')
def api_vehicles():
    # call function from merge_feeds.py
    data = merge_trip_updates_and_positions(update_url, pos_url)

    valid_data = [v for v in data if v.get('lat') and v.get('lon')]
    return jsonify(valid_data)

if __name__ == '__main__':
    # 0.0.0.0 makes it accessible locally
    app.run(debug=True, host='0.0.0.0', port=5000)