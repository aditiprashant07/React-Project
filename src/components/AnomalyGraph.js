import React from 'react';
import {
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Scatter
} from 'recharts';

const AnomalyGraph = ({ data, selectedAnomaly }) => {
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const point = payload[0].payload;
      const isAnomaly =
        point.isAnomaly ||
        point.isZScoreAnomaly ||
        point.isMADAnomaly ||
        point.isEWMAAnomaly ||
        point.isHampelAnomaly ||
        point.isRateAnomaly;

      // Format timestamp if available
      let timestampDisplay = '';
      if (point.timestamp) {
        const dateObj = new Date(point.timestamp);
        if (!isNaN(dateObj)) {
          timestampDisplay = dateObj.toLocaleString();
        } else {
          timestampDisplay = point.timestamp;
        }
      }

      return (
        <div className="bg-white p-2 rounded shadow border">
          <p className="text-xs text-gray-500">
            Time: {label}
            {timestampDisplay && (
              <span className="block text-gray-400">({timestampDisplay})</span>
            )}
          </p>
          <p className={`font-bold ${isAnomaly ? 'text-red-600' : 'text-blue-700'}`}>
            Value: {point.value}
            {isAnomaly && (
              <span className="ml-2 px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs font-semibold">Anomaly</span>
            )}
          </p>
          {isAnomaly && (
            <>
              {point.zScore !== undefined && <p className="text-xs">Z-Score: {point.zScore.toFixed(2)}</p>}
              {point.madScore !== undefined && <p className="text-xs">MAD: {point.madScore.toFixed(2)}</p>}
              {point.ewmaScore !== undefined && <p className="text-xs">EWMA: {point.ewmaScore.toFixed(2)}</p>}
              {point.hampelScore !== undefined && <p className="text-xs">Hampel: {point.hampelScore.toFixed(2)}</p>}
              {point.rateChange !== undefined && <p className="text-xs">Rate Change: {point.rateChange.toFixed(2)}</p>}
            </>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="displayTime"
          tickFormatter={(value) => {
            // If displayTime is a string with both date and time, extract only the time part
            // Otherwise, format as needed
            if (!value) return '';
            // Try to parse as Date if possible
            const date = new Date(value);
            if (!isNaN(date)) {
              return date.toLocaleTimeString();
            }
            // If already a time string, return as is
            if (typeof value === 'string' && value.length > 5 && value.includes(':')) {
              // e.g. "5/27/2025, 12:34:56 PM" or "12:34:56 PM"
              const match = value.match(/(\d{1,2}:\d{2}:\d{2}\s*[APMapm\.]*)/);
              return match ? match[1] : value;
            }
            return value;
          }}
        />
        <YAxis />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#cccccc"
          strokeWidth={1}
          dot={({ cx, cy, payload }) => {
            const isAnomaly =
              payload.isZScoreAnomaly ||
              payload.isMADAnomaly ||
              payload.isEWMAAnomaly ||
              payload.isHampelAnomaly ||
              payload.isRateAnomaly ||
              payload.isAnomaly;

            return (
              <circle
                cx={cx}
                cy={cy}
                r={4}
                fill={isAnomaly ? 'red' : 'blue'}
                stroke="none"
              />
            );
          }}
          name="Sensor Value"
        />
        {selectedAnomaly && (
          <Scatter
            data={[{ x: selectedAnomaly.displayTime, y: selectedAnomaly.value }]}
            fill="black"
            shape="star"
            size={200}
            isAnimationActive={false}
            name="Selected Anomaly Point"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
};

export default AnomalyGraph;
