import React from 'react';
import { Settings } from 'lucide-react';
import { useThresholds } from '../Settings'; // Adjust path if needed

const ThresholdPanel = ({ loading }) => {
  const { activeThresholds, mode } = useThresholds();

  // If nothing is selected, show default thresholds
  const entries = Object.entries(activeThresholds || {});

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
        <Settings size={20} className="mr-2" /> Anomaly Thresholds
      </h2>
      {loading ? (
        <div className="text-center text-gray-500">Loading thresholds...</div>
      ) : entries.length === 0 ? (
        <div className="text-center text-gray-500">No thresholds selected. Showing defaults.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {entries.map(([key, value]) => (
            <div key={key} className="bg-gray-50 p-3 rounded-md">
              <div className="text-sm text-gray-500">{key.replace(/Threshold$/, ' Threshold')}</div>
              <div className="font-bold text-lg text-blue-700">{value ?? 'N/A'}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ThresholdPanel;
