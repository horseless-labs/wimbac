import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { Stop, Vehicle } from '../types';

interface MapProps {
  stops: Stop[];
  vehicles: Vehicle[];
  selectedStop: Stop | null;
  reliabilityData: any;
  onStopClick: (stop: Stop) => void;
  onMove: (bounds: any, zoom: number) => void;
}

function MapEvents({ onMove }: { onMove: (bounds: any, zoom: number) => void }) {
  const map = useMapEvents({
    moveend: () => {
      onMove(map.getBounds(), map.getZoom());
    },
  });
  return null;
}

export default function MapComponent({ 
  stops, 
  vehicles, 
  selectedStop, 
  reliabilityData, 
  onStopClick, 
  onMove 
}: MapProps) {
  return (
    <MapContainer 
      center={[41.4993, -81.6944]} 
      zoom={12} 
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <MapEvents onMove={onMove} />

      {/* 1. Selected Stop Halo & Analytics */}
      {selectedStop && (
        <CircleMarker 
          center={[Number(selectedStop.lat), Number(selectedStop.lon)]}
          radius={12}
          pathOptions={{ color: '#111', weight: 3, fillOpacity: 0 }}
        >
          <Popup>
            <div style={{ minWidth: '200px' }}>
              <strong>{selectedStop.stop_name}</strong>
              <hr style={{ margin: '8px 0', border: '0', borderTop: '1px solid #eee' }} />
              
              {!reliabilityData ? (
                <div className="popup-muted">Loading on-time percentage...</div>
              ) : reliabilityData.error ? (
                <div className="popup-muted">{reliabilityData.error}</div>
              ) : (
                <div className="popup-analytics">
                  <div className="popup-analytics-title">On-time performance</div>
                  <div className="popup-analytics-row">
                    <b>{reliabilityData.on_time_percentage}%</b> on time
                  </div>
                  <div className="popup-muted">
                    Based on {reliabilityData.distinct_trip_count || reliabilityData.sample_size} trips
                  </div>
                </div>
              )}
            </div>
          </Popup>
        </CircleMarker>
      )}

      {/* 2. Render All Stops (This is where onStopClick is used!) */}
      {stops.map((stop) => (
        <CircleMarker
          key={stop.stop_id}
          center={[Number(stop.lat), Number(stop.lon)]}
          radius={8}
          /* onStopClick is READ here - if this line is missing, the map won't be interactive */
          eventHandlers={{ click: () => onStopClick(stop) }}
          pathOptions={{ 
            color: selectedStop?.stop_id === stop.stop_id ? '#000' : '#2c5aa0', 
            fillOpacity: 0.2 
          }}
        />
      ))}

      {/* 3. Render Vehicles */}
      {vehicles.map((v) => (
        <CircleMarker
          key={v.vehicle_id}
          center={[v.lat, v.lon]}
          radius={10}
          pathOptions={{ color: '#ffffff', fillColor: '#2a9d8f', fillOpacity: 0.9, weight: 2 }}
        >
          <Popup>
            🚌 <b>{v.vehicle_label || "Bus"}</b><br/>
            Route: {v.route_id}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}