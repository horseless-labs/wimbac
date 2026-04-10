import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

import MapComponent from './components/MapComponent';
import Hint from './components/Hint';
import type { Stop, Vehicle } from './types';

// Adjust this to your Flask server's URL
//const API_BASE = "http://localhost:8000/api"; //local
const API_BASE = "/api" //production

function App() {
  const [stops, setStops] = useState<Stop[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedStop, setSelectedStop] = useState<Stop | null>(null);
  const [hintMessage, setHintMessage] = useState("<strong>Zoom in</strong> to see stops.");
  const [, setZoom] = useState(12);

  // Fetch stops when map moves
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

  // Polling for vehicles when a stop is selected
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
    return () => clearInterval(timer); // Cleanup on unselect or component unmount
  }, [selectedStop]);

  return (
    <div style={{ height: '100vh', width: '100vw', position: 'relative' }}>
      <Hint message={hintMessage} visible={true} />
      <MapComponent 
        stops={stops} 
        vehicles={vehicles} 
        selectedStop={selectedStop}
        onStopClick={setSelectedStop}
        onMove={handleMapMove}
      />
    </div>
  );
}

export default App;