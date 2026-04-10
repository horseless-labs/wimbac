import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

import MapComponent from './components/MapComponent';
import Hint from './components/Hint';
import type { Stop, Vehicle } from './types';

// Relative path for Nginx production
const API_BASE = "/api"; 

function App() {
  const [stops, setStops] = useState<Stop[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedStop, setSelectedStop] = useState<Stop | null>(null);
  const [hintMessage, setHintMessage] = useState("<strong>Zoom in</strong> to see stops.");
  const [, setZoom] = useState(12);
  const [reliabilityData, setReliabilityData] = useState<any | null>(null);

  // 1. The unified click handler
  const handleStopSelection = useCallback(async (stop: Stop) => {
    setSelectedStop(stop);
    setReliabilityData(null); // Show loading state in popup
    setVehicles([]);          // Clear buses immediately for the new stop

    try {
      const { data } = await axios.get(`${API_BASE}/analytics/stop-reliability`, {
        params: { 
          stop_id: stop.stop_id, 
          timestamp: new Date().toISOString() 
        }
      });
      setReliabilityData(data);
    } catch (e) {
      console.error("Error fetching reliability", e);
      setReliabilityData({ error: "Could not load analytics" });
    }
  }, []);

  const handleMapMove = useCallback(async (bounds: any, newZoom: number) => {
    setZoom(newZoom);
    if (newZoom < 13) {
      setStops([]);
      setHintMessage("<strong>Zoom in</strong> to see stops.");
      return;
    }

    try {
      const { data } = await axios.get(`${API_BASE}/stops`, {
        params: {
          min_lat: bounds.getSouth(),
          max_lat: bounds.getNorth(),
          min_lon: bounds.getWest(),
          max_lon: bounds.getEast(),
        }
      });
      setStops(data);
      if (!selectedStop) setHintMessage("<strong>Click a stop</strong> to show nearby buses.");
    } catch (e) {
      console.error("Error fetching stops", e);
    }
  }, [selectedStop]);

  useEffect(() => {
    if (!selectedStop) {
      setVehicles([]);
      return;
    }

    const fetchVehicles = async () => {
      try {
        const { data } = await axios.get(`${API_BASE}/vehicles_near`, {
          params: { lat: selectedStop.lat, lon: selectedStop.lon, r_m: 800 }
        });
        setVehicles(data);
        setHintMessage(`<strong>${selectedStop.stop_name}</strong><br>${data.length} bus(es) nearby.`);
      } catch (e) {
        console.error("Error fetching vehicles", e);
      }
    };

    fetchVehicles();
    const timer = setInterval(fetchVehicles, 15000);
    return () => clearInterval(timer);
  }, [selectedStop]);

  return (
    <div style={{ height: '100vh', width: '100vw', margin: 0, padding: 0 }}>
      <Hint message={hintMessage} visible={true} />
      <MapComponent 
        stops={stops} 
        vehicles={vehicles} 
        selectedStop={selectedStop}
        reliabilityData={reliabilityData} // 2. Pass this down to show in the popup
        onStopClick={handleStopSelection} // 3. Switch from setSelectedStop to our new function
        onMove={handleMapMove}
      />
    </div>
  );
}

export default App;