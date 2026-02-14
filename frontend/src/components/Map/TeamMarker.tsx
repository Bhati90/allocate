import React from 'react';
import { Team } from '../../types/index';
import { Users } from 'lucide-react';

interface TeamMarkerProps {
  team: Team;
  onClick?: () => void;
}

export function TeamMarker({ team, onClick }: TeamMarkerProps) {
  return (
    <div
      className="absolute cursor-pointer group"
      onClick={onClick}
    >
      <div className="relative">
        {/* Team marker */}
        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white shadow-lg group-hover:scale-110 transition-transform border-2 border-white">
          <Users className="w-5 h-5" />
        </div>
        
        {/* Tooltip on hover */}
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <div className="bg-gray-900 text-white text-xs rounded-lg py-2 px-3 whitespace-nowrap shadow-xl">
            <div className="font-semibold">{team.name}</div>
            <div className="text-gray-300">{team.total_workers} workers</div>
            <div className="text-gray-400">{team.base_location.village}</div>
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 rotate-45 w-2 h-2 bg-gray-900"></div>
          </div>
        </div>
      </div>
    </div>
  );
}
