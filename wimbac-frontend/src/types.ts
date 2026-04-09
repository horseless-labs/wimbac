export interface Stop {
  stop_id: string;
  stop_name: string;
  lat: string | number;
  lon: string | number;
}

export interface Vehicle {
  vehicle_id: string;
  vehicle_label?: string;
  route_id: string;
  lat: number;
  lon: number;
}

export interface ReliabilityData {
  on_time_percentage: number;
  sample_size: number;
  confidence: string;
  matched_route_ids: string[];
}