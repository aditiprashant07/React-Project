import React from 'react';

const MetricCard = ({ title, value, icon: Icon, color, onInfo, infoOpen, explanation }) => (
  <div className="relative">
    <div
      className="bg-white rounded-lg shadow p-4 flex flex-col cursor-pointer hover:ring-2 hover:ring-blue-200 transition-all duration-200"
      onClick={onInfo}
    >
      <div className="flex justify-between items-center mb-2">
        <span className="text-gray-500 text-sm">{title}</span>
        <Icon size={18} className={`text-${color}-500`} />
      </div>
      <div className="flex items-baseline">
        <span className="text-2xl font-bold">{value}</span>
      </div>
    </div>
    {infoOpen && (
      <div className="absolute z-10 left-0 right-0 mt-2 bg-white border border-blue-300 rounded shadow-lg p-3 text-xs text-gray-700 animate-fade-in">
        <div className="font-semibold mb-1">{title}</div>
        <div>{explanation}</div>
        <button
          className="mt-2 text-blue-600 underline text-xs hover:text-blue-800"
          onClick={(e) => {
            e.stopPropagation();
            onInfo();
          }}
        >
          Close
        </button>
      </div>
    )}
  </div>
);

export default MetricCard;
