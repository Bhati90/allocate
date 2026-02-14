// components/MapView/LeafletHexagonMap.tsx
import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { HexagonCluster, MukkadamPosition } from '../../types/map';

type Props = {
  hexagons: HexagonCluster[];
  mukkadams: MukkadamPosition[];
  viewMode: 'penetration' | 'capacity' | 'demand';
  selectedHexId: string | null;
  onSelectHex: (id: string | null) => void;
};

export function LeafletHexagonMap({ hexagons, mukkadams, viewMode, selectedHexId, onSelectHex }: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const hexagonLayersRef = useRef<Map<string, L.Polygon>>(new Map());
  const markerLayersRef = useRef<Map<number, L.Marker>>(new Map());
  const [mapReady, setMapReady] = useState(false);

  // Initialize map
// components/MapView/LeafletHexagonMap.tsx - Fix initialization

useEffect(() => {
  if (mapRef.current) return;

  // Wait for DOM to be ready
  setTimeout(() => {
    const container = document.getElementById('map-container');
    if (!container) {
      console.error('Map container not found');
      return;
    }

    const map = L.map('map-container', {
      center: [20.0, 73.8],
      zoom: 10,
      zoomControl: true,
      scrollWheelZoom: true,
      preferCanvas: true, // ✅ Better performance
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    mapRef.current = map;
    
    // ✅ Force resize after initialization
    setTimeout(() => {
      map.invalidateSize();
    }, 100);
    
    setMapReady(true);
  }, 100);

  return () => {
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }
  };
}, []);

  // Generate hexagon coordinates
  const generateHexagonCoordinates = (centerLat: number, centerLng: number, radiusKm: number): L.LatLngExpression[] => {
    const points: L.LatLngExpression[] = [];
    const numPoints = 6;
    
    // Convert radius from km to degrees (approximate)
    const latRadius = radiusKm / 111; // 1 degree latitude ≈ 111 km
    const lngRadius = radiusKm / (111 * Math.cos(centerLat * Math.PI / 180));

    for (let i = 0; i < numPoints; i++) {
      const angle = (Math.PI / 3) * i - Math.PI / 6; // Start from top
      const lat = centerLat + latRadius * Math.sin(angle);
      const lng = centerLng + lngRadius * Math.cos(angle);
      points.push([lat, lng]);
    }

    return points;
  };

  const getHexagonColor = (hex: HexagonCluster) => {
    switch (viewMode) {
      case 'penetration':
        if (hex.market_penetration < 30) return { fill: '#10b981', stroke: '#059669' };
        if (hex.market_penetration < 60) return { fill: '#f59e0b', stroke: '#d97706' };
        return { fill: '#ef4444', stroke: '#dc2626' };

      case 'capacity':
        if (hex.capacity_utilization < 60) return { fill: '#10b981', stroke: '#059669' };
        if (hex.capacity_utilization < 90) return { fill: '#f59e0b', stroke: '#d97706' };
        return { fill: '#ef4444', stroke: '#dc2626' };

      case 'demand':
        if (hex.demand_score < 40) return { fill: '#10b981', stroke: '#059669' };
        if (hex.demand_score < 70) return { fill: '#f59e0b', stroke: '#d97706' };
        return { fill: '#ef4444', stroke: '#dc2626' };

      default:
        return { fill: '#6b7280', stroke: '#4b5563' };
    }
  };

  const getDisplayValue = (hex: HexagonCluster) => {
    switch (viewMode) {
      case 'penetration':
        return `${hex.market_penetration.toFixed(0)}%`;
      case 'capacity':
        return `${hex.capacity_utilization.toFixed(0)}%`;
      case 'demand':
        return `${hex.demand_score.toFixed(0)}`;
      default:
        return '';
    }
  };

  // Draw hexagons
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    const map = mapRef.current;

    // Clear existing hexagon layers
    hexagonLayersRef.current.forEach(layer => layer.remove());
    hexagonLayersRef.current.clear();

    // Draw hexagons
    hexagons.forEach((hex) => {
      if (hex.total_jobs === 0) return; // Skip empty hexagons

      const coordinates = generateHexagonCoordinates(hex.center_lat, hex.center_lng, hex.radius_km);
      const colors = getHexagonColor(hex);
      const isSelected = selectedHexId === hex.id;

      const polygon = L.polygon(coordinates, {
        color: colors.stroke,
        fillColor: colors.fill,
        fillOpacity: isSelected ? 0.8 : 0.5,
        weight: isSelected ? 4 : 2,
      }).addTo(map);

      // Add click handler
      polygon.on('click', () => {
        onSelectHex(hex.id);
      });

      // Create popup content
      const mukkadamsInHex = mukkadams.filter(m => m.cluster_id === hex.id);
      const popupContent = `
        <div class="p-3">
          <h3 class="font-bold text-lg mb-2">${hex.id}</h3>
          <div class="space-y-1 text-sm">
            <div><strong>${getDisplayValue(hex)}</strong> ${viewMode}</div>
            <div>Jobs: ${hex.total_jobs}</div>
            <div>Activities: ${hex.total_activities}</div>
            <div>Area: ${hex.booked_acres.toFixed(0)} acres</div>
            <div>Teams: ${mukkadamsInHex.length}</div>
            <div>Villages: ${hex.villages.join(', ')}</div>
            <div>Revenue: ₹${(hex.total_revenue / 1000).toFixed(0)}K</div>
            <div>Cost: ₹${(hex.total_cost / 1000).toFixed(0)}K</div>
          </div>
        </div>
      `;

      polygon.bindPopup(popupContent);

      // Add label
      const label = L.divIcon({
        className: 'hexagon-label',
        html: `
          <div class="text-center pointer-events-none" style="margin-top: -60px;">
            <div class="font-bold text-xs text-gray-700">${hex.id}</div>
            <div class="font-bold text-2xl" style="color: ${colors.stroke};">${getDisplayValue(hex)}</div>
            <div class="text-xs text-gray-600">${hex.booked_acres.toFixed(0)}ac / ${hex.total_jobs}j</div>
          </div>
        `,
        iconSize: [120, 80],
        iconAnchor: [60, 40],
      });

      const labelMarker = L.marker([hex.center_lat, hex.center_lng], {
        icon: label,
        interactive: false,
      }).addTo(map);

      // Store layer reference
      hexagonLayersRef.current.set(hex.id, polygon);
    });

  }, [mapReady, hexagons, viewMode, selectedHexId, mukkadams, onSelectHex]);

  // Draw mukkadam markers
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    const map = mapRef.current;

    // Clear existing markers
    markerLayersRef.current.forEach(marker => marker.remove());
    markerLayersRef.current.clear();

    // Add mukkadam markers
    mukkadams.forEach((mukkadam) => {
      const icon = L.divIcon({
        className: 'mukkadam-marker',
        html: `
          <div class="relative">
            <div class="w-8 h-8 rounded-full ${mukkadam.is_live_location ? 'bg-blue-600' : 'bg-gray-500'} 
                        border-2 border-white shadow-lg flex items-center justify-center text-white font-bold text-xs">
              ${mukkadam.crew_size}
            </div>
            ${mukkadam.is_live_location ? '<div class="absolute top-0 right-0 w-2 h-2 bg-green-400 rounded-full"></div>' : ''}
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      const marker = L.marker([mukkadam.latitude, mukkadam.longitude], {
        icon,
        title: mukkadam.name,
      }).addTo(map);

      // Create popup for mukkadam
      const popupContent = `
        <div class="p-3">
          <h4 class="font-bold mb-2">${mukkadam.name}</h4>
          <div class="space-y-1 text-sm">
            <div>Crew Size: ${mukkadam.crew_size}</div>
            <div>Location: ${mukkadam.is_live_location ? '🟢 Live' : '⚫ Estimated'}</div>
            ${mukkadam.current_allocation ? `
              <div class="mt-2 p-2 bg-blue-50 rounded">
                <div class="font-semibold">Current Work:</div>
                <div>${mukkadam.current_allocation.activity_name}</div>
                <div class="text-xs">${mukkadam.current_allocation.location}</div>
              </div>
            ` : ''}
            ${mukkadam.availability.is_available ? `
              <div class="text-green-600">Available: ${mukkadam.availability.available_days} days</div>
            ` : '<div class="text-red-600">Not Available</div>'}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      markerLayersRef.current.set(mukkadam.id, marker);
    });

  }, [mapReady, mukkadams]);

  // Update selection styling
  useEffect(() => {
    if (!mapReady) return;

    hexagonLayersRef.current.forEach((layer, hexId) => {
      const hex = hexagons.find(h => h.id === hexId);
      if (!hex) return;

      const colors = getHexagonColor(hex);
      const isSelected = selectedHexId === hexId;

      layer.setStyle({
        fillOpacity: isSelected ? 0.8 : 0.5,
        weight: isSelected ? 4 : 2,
      });
    });

  }, [selectedHexId, mapReady, hexagons, viewMode]);

  return (
    <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8">
      {/* Map Legend */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b-2 border-gray-200">
        <h3 className="text-2xl font-bold text-gray-900">Geographic Cluster Map</h3>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 bg-emerald-500 border-2 border-emerald-600 rounded"></div>
              <span className="text-gray-700 font-medium">
                {viewMode === 'penetration' && 'Low (<30%)'}
                {viewMode === 'capacity' && 'Available (<60%)'}
                {viewMode === 'demand' && 'Low (<40)'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 bg-amber-500 border-2 border-amber-600 rounded"></div>
              <span className="text-gray-700 font-medium">
                {viewMode === 'penetration' && 'Medium (30-60%)'}
                {viewMode === 'capacity' && 'Balanced (60-90%)'}
                {viewMode === 'demand' && 'Medium (40-70)'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 bg-red-500 border-2 border-red-600 rounded"></div>
              <span className="text-gray-700 font-medium">
                {viewMode === 'penetration' && 'High (>60%)'}
                {viewMode === 'capacity' && 'Overloaded (>90%)'}
                {viewMode === 'demand' && 'High (>70)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Leaflet Map Container */}
      <div 
        id="map-container" 
        className="w-full h-[700px] rounded-xl border-2 border-gray-300 overflow-hidden"
        style={{ zIndex: 0 }}
      />

      {/* Map Info */}
      <div className="mt-4 flex items-center justify-between text-xs text-gray-600">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-blue-600 rounded-full text-white flex items-center justify-center font-bold text-xs">
              12
            </div>
            <span>Team crew size</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-400 rounded-full"></div>
            <span>Live location</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
            <span>Estimated location</span>
          </div>
        </div>
        <div className="text-gray-500">
          Click on hexagons or team markers for details • Scroll to zoom • Drag to pan
        </div>
      </div>
    </div>
  );
}