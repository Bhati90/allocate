// components/MapView/HexagonGrid.tsx
import React, { useRef, useEffect } from 'react';
import type { HexagonCluster, MukkadamPosition } from '../../types/map';

type Props = {
  hexagons: HexagonCluster[];
  mukkadams: MukkadamPosition[];
  viewMode: 'penetration' | 'capacity' | 'demand';
  selectedHexId: string | null;
  onSelectHex: (id: string | null) => void;
};

export function HexagonGrid({ hexagons, mukkadams, viewMode, selectedHexId, onSelectHex }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Calculate bounds from hexagons
  const bounds = {
    minLat: Math.min(...hexagons.map(h => h.center_lat - 0.15)),
    maxLat: Math.max(...hexagons.map(h => h.center_lat + 0.15)),
    minLng: Math.min(...hexagons.map(h => h.center_lng - 0.15)),
    maxLng: Math.max(...hexagons.map(h => h.center_lng + 0.15)),
  };

  const latRange = bounds.maxLat - bounds.minLat;
  const lngRange = bounds.maxLng - bounds.minLng;

  // Convert lat/lng to pixel coordinates
  const latLngToPixel = (lat: number, lng: number, width: number, height: number) => {
    const padding = 60;
    const x = ((lng - bounds.minLng) / lngRange) * (width - padding * 2) + padding;
    const y = height - (((lat - bounds.minLat) / latRange) * (height - padding * 2) + padding);
    return { x, y };
  };

  // Draw hexagon path
  const drawHexagon = (ctx: CanvasRenderingContext2D, x: number, y: number, size: number) => {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i;
      const hx = x + size * Math.cos(angle);
      const hy = y + size * Math.sin(angle);
      if (i === 0) ctx.moveTo(hx, hy);
      else ctx.lineTo(hx, hy);
    }
    ctx.closePath();
  };

  const getHexagonColor = (hex: HexagonCluster) => {
    switch (viewMode) {
      case 'penetration':
        if (hex.market_penetration < 30) return { fill: '#d1fae5', stroke: '#10b981', text: '#065f46' };
        if (hex.market_penetration < 60) return { fill: '#fef3c7', stroke: '#f59e0b', text: '#92400e' };
        return { fill: '#fee2e2', stroke: '#ef4444', text: '#991b1b' };

      case 'capacity':
        if (hex.capacity_utilization < 60) return { fill: '#d1fae5', stroke: '#10b981', text: '#065f46' };
        if (hex.capacity_utilization < 90) return { fill: '#fef3c7', stroke: '#f59e0b', text: '#92400e' };
        return { fill: '#fee2e2', stroke: '#ef4444', text: '#991b1b' };

      case 'demand':
        if (hex.demand_score < 40) return { fill: '#d1fae5', stroke: '#10b981', text: '#065f46' };
        if (hex.demand_score < 70) return { fill: '#fef3c7', stroke: '#f59e0b', text: '#92400e' };
        return { fill: '#fee2e2', stroke: '#ef4444', text: '#991b1b' };

      default:
        return { fill: '#e5e7eb', stroke: '#9ca3af', text: '#374151' };
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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw background map outline
    ctx.fillStyle = '#f0f9ff';
    ctx.fillRect(0, 0, width, height);

    // Draw grid lines
    ctx.strokeStyle = '#e0e7ff';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      // Vertical lines
      const x = (width / 10) * i;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Horizontal lines
      const y = (height / 10) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Draw Nashik district label
    ctx.fillStyle = '#1e40af';
    ctx.font = 'bold 24px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Nashik District', width / 2, 40);

    // Draw compass
    ctx.fillStyle = '#374151';
    ctx.font = 'bold 16px system-ui';
    ctx.textAlign = 'right';
    ctx.fillText('N ↑', width - 20, 30);

    // Draw scale
    ctx.fillStyle = '#374151';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'left';
    ctx.fillText('15km radius per cluster', 20, height - 20);

    // Draw hexagons
    const hexSize = Math.min(width, height) / 15;

    hexagons.forEach((hex) => {
      const { x, y } = latLngToPixel(hex.center_lat, hex.center_lng, width, height);
      const colors = getHexagonColor(hex);
      const isSelected = selectedHexId === hex.id;
      const hasData = hex.total_jobs > 0;

      // Draw hexagon
      drawHexagon(ctx, x, y, hexSize);
      
      if (hasData) {
        ctx.fillStyle = colors.fill;
        ctx.fill();
        ctx.strokeStyle = isSelected ? '#3b82f6' : colors.stroke;
        ctx.lineWidth = isSelected ? 4 : 2;
        ctx.stroke();
      } else {
        ctx.fillStyle = '#f3f4f6';
        ctx.globalAlpha = 0.3;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = '#d1d5db';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      if (hasData) {
        // Draw hex ID
        ctx.fillStyle = colors.text;
        ctx.font = 'bold 11px system-ui';
        ctx.textAlign = 'center';
        ctx.fillText(hex.id, x, y - 15);

        // Draw main value
        ctx.font = 'bold 20px system-ui';
        ctx.fillText(getDisplayValue(hex), x, y + 5);

        // Draw area info
        ctx.font = '9px system-ui';
        ctx.fillText(`${hex.booked_acres.toFixed(0)}ac / ${hex.total_jobs}j`, x, y + 20);

        // Draw team count
        const mukkadamsInHex = mukkadams.filter(m => m.cluster_id === hex.id);
        if (mukkadamsInHex.length > 0) {
          ctx.fillStyle = '#3b82f6';
          ctx.beginPath();
          ctx.arc(x + hexSize - 10, y - hexSize + 10, 12, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 10px system-ui';
          ctx.fillText(mukkadamsInHex.length.toString(), x + hexSize - 10, y - hexSize + 14);
        }

        // Draw village count
        if (hex.villages.length > 0) {
          ctx.fillStyle = '#ffffff';
          ctx.strokeStyle = '#9ca3af';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(x, y + hexSize - 5, 15, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = '#374151';
          ctx.font = 'bold 9px system-ui';
          ctx.fillText(`📍${hex.villages.length}`, x, y + hexSize - 2);
        }

        // High demand indicator
        if (hex.demand_score > 70) {
          ctx.fillStyle = '#ef4444';
          ctx.beginPath();
          ctx.arc(x - hexSize + 10, y - hexSize + 10, 10, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 12px system-ui';
          ctx.fillText('🔥', x - hexSize + 10, y - hexSize + 13);
        }
      }
    });

    // Draw village names
    ctx.fillStyle = '#6b7280';
    ctx.font = '10px system-ui';
    const drawnVillages = new Set();
    hexagons.forEach((hex) => {
      if (hex.villages.length > 0 && hex.total_jobs > 0) {
        const { x, y } = latLngToPixel(hex.center_lat, hex.center_lng, width, height);
        hex.villages.slice(0, 2).forEach((village, idx) => {
          if (!drawnVillages.has(village)) {
            ctx.textAlign = 'center';
            ctx.fillText(village, x, y + hexSize + 25 + (idx * 12));
            drawnVillages.add(village);
          }
        });
      }
    });

  }, [hexagons, mukkadams, viewMode, selectedHexId]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const width = canvas.width;
    const height = canvas.height;
    const hexSize = Math.min(width, height) / 15;

    // Find clicked hexagon
    for (const hex of hexagons) {
      if (hex.total_jobs === 0) continue;
      
      const { x, y } = latLngToPixel(hex.center_lat, hex.center_lng, width, height);
      const distance = Math.sqrt((clickX - x) ** 2 + (clickY - y) ** 2);

      if (distance <= hexSize) {
        onSelectHex(hex.id);
        return;
      }
    }

    onSelectHex(null);
  };

  return (
    <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8">
      {/* Map Legend */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b-2 border-gray-200">
        <h3 className="text-2xl font-bold text-gray-900">Cluster Map</h3>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 bg-emerald-100 border-2 border-emerald-400 rounded"></div>
              <span className="text-gray-700 font-medium">
                {viewMode === 'penetration' && 'Low (<30%)'}
                {viewMode === 'capacity' && 'Available (<60%)'}
                {viewMode === 'demand' && 'Low (<40)'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 bg-amber-100 border-2 border-amber-400 rounded"></div>
              <span className="text-gray-700 font-medium">
                {viewMode === 'penetration' && 'Medium (30-60%)'}
                {viewMode === 'capacity' && 'Balanced (60-90%)'}
                {viewMode === 'demand' && 'Medium (40-70)'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 bg-rose-100 border-2 border-rose-400 rounded"></div>
              <span className="text-gray-700 font-medium">
                {viewMode === 'penetration' && 'High (>60%)'}
                {viewMode === 'capacity' && 'Overloaded (>90%)'}
                {viewMode === 'demand' && 'High (>70)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Canvas Map */}
      <div className="relative bg-white rounded-xl border-2 border-gray-300 overflow-hidden">
        <canvas
          ref={canvasRef}
          width={1200}
          height={800}
          className="w-full cursor-pointer"
          onClick={handleCanvasClick}
          style={{ display: 'block' }}
        />
      </div>

      {/* Map Info */}
      <div className="mt-4 flex items-center justify-between text-xs text-gray-600">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-blue-500 rounded-full text-white flex items-center justify-center font-bold text-xs">
              3
            </div>
            <span>Team count</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-white border border-gray-400 rounded-full flex items-center justify-center">
              📍2
            </div>
            <span>Village count</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-red-500 rounded-full text-white flex items-center justify-center">
              🔥
            </div>
            <span>High demand</span>
          </div>
        </div>
        <div className="text-gray-500">
          Click on any cluster to view details
        </div>
      </div>
    </div>
  );
}