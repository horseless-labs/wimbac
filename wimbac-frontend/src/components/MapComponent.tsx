import { useEffect, useRef } from 'react';
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

// Separate component for stop markers to handle the "Auto-Open" logic
function StopMarker({ stop, isSelected, reliabilityData, onClick }: { 
  stop: Stop, isSelected: boolean, reliabilityData: any, onClick: () => void 
}) {
  const markerRef = useRef<any>(null);

  // Force the popup open if this stop is the selected one
  useEffect(() => {
    if (isSelected && markerRef.current) {
      markerRef.current.openPopup();
    }
  }, [isSelected]);

  return (
    <CircleMarker
      ref={markerRef}
      center={[Number(stop.lat), Number(stop.lon)]}
      radius={isSelected ? 12 : 8} // Grow the marker if selected (The Halo)
      eventHandlers={{ click: onClick }}
      pathOptions={{ 
        color: isSelected ? '#111' : '#2c5aa0', 
        weight: isSelected ? 3 : 1,
        fillOpacity: isSelected ? 0.4 : 0.2 
      }}
    >
      <Popup minWidth={200}>
        <div>
          <strong>{stop.stop_name}</strong>
          <hr style={{ margin: '8px 0', border: '0', borderTop: '1px solid #eee' }} />
          
          {!reliabilityData ? (
            <div className="popup-muted">Loading on-time percentage...</div>
          ) : (
            <div className="popup-analytics">
              <div className="popup-analytics-title">On-time performance</div>
              <b>{reliabilityData.on_time_percentage}%</b> on time
              <div className="popup-muted">
                Based on {reliabilityData.distinct_trip_count || reliabilityData.sample_size} trips
              </div>
            </div>
          )}
        </div>
      </Popup>
    </CircleMarker>
  );
}

function MapEvents({ onMove }: { onMove: (bounds: any, zoom: number) => void }) {
  const map = useMapEvents({
    moveend: () => onMove(map.getBounds(), map.getZoom()),
  });
  return null;
}

export default function MapComponent({ stops, vehicles, selectedStop, reliabilityData, onStopClick, onMove }: MapProps) {
  return (
    <MapContainer center={[41.4993, -81.6944]} zoom={12} style={{ height: '100%', width: '100%' }}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <MapEvents onMove={onMove} />

      {/* Render Stops using the Sub-Component */}
      {stops.map((stop) => (
        <StopMarker
          key={`stop-${stop.stop_id}`}
          stop={stop}
          isSelected={selectedStop?.stop_id === stop.stop_id}
          reliabilityData={selectedStop?.stop_id === stop.stop_id ? reliabilityData : null}
          onClick={() => onStopClick(stop)}
        />
      ))}

      {/* Render Vehicles */}
      {vehicles.map((v) => (
        <CircleMarker
          key={`veh-${v.vehicle_id}`}
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