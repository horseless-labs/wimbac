import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from 'react-leaflet';
import type { Stop, Vehicle } from '../types';
import 'leaflet/dist/leaflet.css';

interface MapProps {
  stops: Stop[];
  vehicles: Vehicle[];
  selectedStop: Stop | null;
  onStopClick: (stop: Stop) => void;
  onMove: (bounds: any, zoom: number) => void;
}

function MapEvents({ onMove }: { onMove: (bounds: any, zoom: number) => void }) {
  const map = useMapEvents({
    moveend: () => onMove(map.getBounds(), map.getZoom()),
  });
  return null;
}

export default function MapComponent({ stops, vehicles, selectedStop, onStopClick, onMove }: MapProps) {
  return (
    <MapContainer center={[41.4993, -81.6944]} zoom={12} style={{ height: '100vh', width: '100%' }}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <MapEvents onMove={onMove} />

        /* Selected Stop Halo */
        {selectedStop && (
        <CircleMarker 
            center={[Number(selectedStop.lat), Number(selectedStop.lon)]}
            radius={12} // Move radius here, outside of pathOptions
            pathOptions={{ color: '#111', weight: 3, fillOpacity: 0 }}
        />
        )}

        /* Render Stops */
        {stops.map((stop) => (
        <CircleMarker
            key={stop.stop_id}
            center={[Number(stop.lat), Number(stop.lon)]}
            radius={8} // Move radius here
            eventHandlers={{ click: () => onStopClick(stop) }}
            pathOptions={{ color: '#2c5aa0', fillOpacity: 0.2 }}
        />
        ))}

        /* Render Vehicles */
        {vehicles.map((v) => (
        <CircleMarker
            key={v.vehicle_id}
            center={[v.lat, v.lon]}
            radius={10} // Move radius here
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