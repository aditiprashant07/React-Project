import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart, Bar } from 'recharts';
import { Search, Calendar, Zap, Database, AlertCircle, Settings, RefreshCw, BarChart2, TrendingUp, Star } from 'lucide-react';
import _ from 'lodash';
import infinity from './Infinity.png';

// Helper to calculate median
function median(arr) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

// Helper for MAD (Median Absolute Deviation)
function mad(arr, med = null) {
  if (!arr.length) return 0;
  const m = med !== null ? med : median(arr);
  return median(arr.map(v => Math.abs(v - m)));
}

// Helper for Hampel filter (rolling median and MAD)
function hampelScores(arr, window = 7, threshold = 3) {
  if (arr.length < window) return [];
  const scores = [];
  for (let i = 0; i < arr.length; i++) {
    const start = Math.max(0, i - Math.floor(window / 2));
    const end = Math.min(arr.length, i + Math.ceil(window / 2));
    const windowArr = arr.slice(start, end);
    const med = median(windowArr);
    const madVal = mad(windowArr, med) || 1e-6; // Prevent division by zero
    const score = Math.abs(arr[i] - med) / (1.4826 * madVal); // 1.4826 is a scaling factor for consistency with normal distribution
    scores.push(score);
  }
  return scores;
}

// Generate mock data
const generateMockData = () => {
  const now = new Date();
  const data = [];
  for (let i = 0; i < 100; i++) {
    const timestamp = new Date(now.getTime() - (99 - i) * 15 * 60000); // 15-minute intervals
    let value = 70 + Math.sin(i / 5) * 15 + (Math.random() * 5); // Base value with sine wave and noise
    const isAnomaly = i === 30 || i === 70 || (i > 85 && i < 90); // Introduce specific anomalies
    if (isAnomaly) {
      value = value + (Math.random() > 0.5 ? 1 : -1) * Math.random() * 30; // Significant spike or dip
    }
    data.push({
      timestamp: timestamp.toISOString(),
      displayTime: `${timestamp.getHours()}:${String(timestamp.getMinutes()).padStart(2, '0')}`,
      value: parseFloat(value.toFixed(2)),
      isAnomaly // Original mock anomaly flag
    });
  }
  return data;
};

// Z-Score anomaly detection
function calculateZScore(data, threshold = 3) {
  if (data.length < 2) return { count: 0, scores: [] };
  const values = data.map(d => d.value);
  const mean = _.mean(values);
  const std = Math.sqrt(_.mean(values.map(v => Math.pow(v - mean, 2)))) || 0.1; // Prevent division by zero
  const scores = data.map(d => ({
    ...d,
    zScore: (d.value - mean) / std,
    isZScoreAnomaly: Math.abs((d.value - mean) / std) > threshold
  }));
  return {
    count: scores.filter(d => d.isZScoreAnomaly).length,
    scores
  };
}

// MAD anomaly detection
function calculateMAD(data, threshold = 3) {
  if (data.length < 2) return { count: 0, scores: [] };
  const values = data.map(d => d.value);
  const med = median(values);
  const madVal = mad(values, med) || 1e-6; // Prevent division by zero
  const scores = data.map(d => ({
    ...d,
    madScore: Math.abs(d.value - med) / madVal,
    isMADAnomaly: Math.abs(d.value - med) / madVal > threshold
  }));
  return {
    count: scores.filter(d => d.isMADAnomaly).length,
    scores
  };
}

// EWMA anomaly detection
function calculateEWMA(data, alpha = 0.1, lambdaParam = 0.94, threshold = 2) {
  if (data.length < 2) return { count: 0, scores: [] };
  let ewma = data[0].value;
  let ewmstd = 1.0;
  const values = data.map(d => d.value);
  const mean = _.mean(values);
  const std = Math.sqrt(_.mean(values.map(v => Math.pow(v - mean, 2)))) || 1.0;
  ewma = mean; // Initialize EWMA with global mean for stability
  ewmstd = std; // Initialize EWMA standard deviation with global std

  const scores = [];
  data.forEach((d, idx) => {
    if (idx === 0) {
      scores.push({ ...d, ewma, ewmstd, ewmaScore: 0, isEWMAAnomaly: false });
      return;
    }
    ewma = alpha * d.value + (1 - alpha) * ewma;
    const diff = d.value - ewma;
    ewmstd = Math.sqrt(lambdaParam * (ewmstd ** 2) + (1 - lambdaParam) * (diff ** 2));
    const ewmaScore = Math.abs(d.value - ewma) / (ewmstd || 0.1); // Prevent division by zero
    const isEWMAAnomaly = ewmaScore > threshold;
    scores.push({ ...d, ewma, ewmstd, ewmaScore, isEWMAAnomaly });
  });
  return {
    count: scores.filter(d => d.isEWMAAnomaly).length,
    scores
  };
}

// Hampel anomaly detection
function calculateHampel(data, window = 7, threshold = 3) {
  if (data.length < window) return { count: 0, scores: [] };
  const values = data.map(d => d.value);
  const hampelScoresArr = hampelScores(values, window, threshold);
  const scores = data.map((d, idx) => ({
    ...d,
    hampelScore: hampelScoresArr[idx] || 0,
    isHampelAnomaly: (hampelScoresArr[idx] || 0) > threshold
  }));
  return {
    count: scores.filter(d => d.isHampelAnomaly).length,
    scores
  };
}

// Rate of Change anomaly detection
function calculateRateOfChange(data, threshold = 20) {
  if (data.length < 2) return { count: 0, scores: [] };
  const scores = data.map((d, idx) => {
    if (idx === 0) return { ...d, rateChange: 0, isRateAnomaly: false };
    const rateChange = Math.abs(d.value - data[idx - 1].value);
    return {
      ...d,
      rateChange,
      isRateAnomaly: rateChange > threshold
    };
  });
  return {
    count: scores.filter(d => d.isRateAnomaly).length,
    scores
  };
}

// Explanations for metric cards
const metricExplanations = {
  "Z-SCORE Anomalies": "Z-Score detects anomalies by measuring how many standard deviations a value is from the mean. Points with a Z-Score above a threshold are flagged as anomalies.",
  "MAD Anomalies": "MAD (Median Absolute Deviation) identifies anomalies by measuring how far a value deviates from the median. It is robust to outliers and less sensitive to extreme values than standard deviation.",
  "EWMA Anomalies": "EWMA (Exponentially Weighted Moving Average) detects anomalies by comparing each value to a smoothed average, highlighting sudden shifts or trends that deviate significantly from the expected path.",
  "HAMPEL Anomalies": "The Hampel filter uses a rolling median and MAD to spot outliers within a moving window. It's particularly effective for time series data with localized anomalies and is robust to noise.",
  "RATE-OF-CHANGE": "Rate of Change flags anomalies when the absolute difference between consecutive readings exceeds a set threshold. This is useful for detecting sudden, rapid changes in sensor values.",
  "Maximum Value": "Shows the highest sensor value recorded within the currently selected time range. This can indicate peak activity or potential sensor spikes."
};

const MetricCard = ({ title, value, icon: Icon, trend, color, onInfo, infoOpen }) => (
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
        {trend && (
          <span className={`ml-2 text-xs ${trend > 0 ? 'text-green-500' : 'text-red-500'}`}>
            {trend > 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
    </div>
    {infoOpen && (
      <div className="absolute z-10 left-0 right-0 mt-2 bg-white border border-blue-300 rounded shadow-lg p-3 text-xs text-gray-700 animate-fade-in">
        <div className="font-semibold mb-1">{title}</div>
        <div>{metricExplanations[title]}</div>
        <button
          className="mt-2 text-blue-600 underline text-xs hover:text-blue-800"
          onClick={e => { e.stopPropagation(); onInfo(); }}
        >
          Close
        </button>
      </div>
    )}
  </div>
);

const AnomalyTable = ({ anomalies, onRowClick }) => {
  if (anomalies.length === 0) {
    return <div className="bg-gray-50 rounded-lg p-6 text-center text-gray-500">No anomalies detected in the current time range.</div>;
  }
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Deviation</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {anomalies.map((anomaly, index) => {
            const date = new Date(anomaly.timestamp);
            const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
            // Assuming 70 is a rough baseline for percentage deviation calculation for mock data
            const deviation = ((anomaly.value - 70) / 70 * 100).toFixed(1);
            return (
              <tr
                key={index}
                className="hover:bg-blue-50 cursor-pointer transition-colors duration-150"
                onClick={onRowClick ? () => onRowClick(anomaly) : undefined}
              >
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formattedDate}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{anomaly.value}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{deviation}%</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                    Anomaly
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

function IoTAnomalyDetectionDashboard() {
  const [data, setData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDateRange, setSelectedDateRange] = useState('Last 24 hours');
  const [customRange, setCustomRange] = useState({ start: '', end: '' });
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);
  const [openMetricInfo, setOpenMetricInfo] = useState(null);

  useEffect(() => {
    setLoading(true);
    setTimeout(() => {
      const newData = generateMockData();
      setData(newData);
      setLoading(false);
    }, 1000);
  }, []);

  useEffect(() => {
    if (!data.length) return;
    let filtered = data;
    const now = new Date();
    if (selectedDateRange === 'Last 24 hours') {
      const since = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      filtered = data.filter(d => new Date(d.timestamp) >= since);
    } else if (selectedDateRange === 'Last 7 days') {
      const since = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      filtered = data.filter(d => new Date(d.timestamp) >= since);
    } else if (selectedDateRange === 'Last 30 days') {
      const since = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      filtered = data.filter(d => new Date(d.timestamp) >= since);
    } else if (selectedDateRange === 'Custom' && customRange.start && customRange.end) {
      const start = new Date(customRange.start);
      const end = new Date(customRange.end);
      filtered = data.filter(d => {
        const t = new Date(d.timestamp);
        return t >= start && t <= end;
      });
    }
    setFilteredData(filtered);
    setSelectedAnomaly(null);
  }, [data, selectedDateRange, customRange]);

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        const newData = generateMockData();
        setData(newData);
      }, 30000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  // Calculate metrics for the currently filtered data
  const zScoreResult = calculateZScore(filteredData, 3);
  const madResult = calculateMAD(filteredData, 3);
  const ewmaResult = calculateEWMA(filteredData, 0.1, 0.94, 2);
  const hampelResult = calculateHampel(filteredData, 7, 3);
  const rateResult = calculateRateOfChange(filteredData, 20);

  const avgValue = filteredData.length ? _.meanBy(filteredData, 'value').toFixed(1) : 0;
  const maxValue = filteredData.length ? _.maxBy(filteredData, 'value').value.toFixed(1) : 0;

  // Calculate statistics for filteredData to enrich data points
  const values = filteredData.map(d => d.value);
  const mean = _.mean(values);
  const std = Math.sqrt(_.mean(values.map(v => Math.pow(v - mean, 2)))) || 0.1;
  const medianVal = median(values);
  const madVal = mad(values, medianVal) || 1e-6;

  // Calculate EWMA and EWMA std for each point to be included in tooltip
  let ewma = mean;
  let ewmstd = std;
  const alpha = 0.1;
  const lambdaParam = 0.94;
  const ewmaScores = [];
  filteredData.forEach((d, idx) => {
    if (idx === 0) {
      ewmaScores.push({ ewma, ewmstd, ewmaScore: 0 });
      return;
    }
    ewma = alpha * d.value + (1 - alpha) * ewma;
    const diff = d.value - ewma;
    ewmstd = Math.sqrt(lambdaParam * (ewmstd ** 2) + (1 - lambdaParam) * (diff ** 2));
    const ewmaScore = Math.abs(d.value - ewma) / (ewmstd || 0.1);
    ewmaScores.push({ ewma, ewmstd, ewmaScore });
  });

  // Add all scores to each data point for display in graph tooltip and table
  const scoredData = filteredData.map((d, idx) => {
    const zScore = (d.value - mean) / std;
    const absDeviation = Math.abs(d.value - mean);
    const ewmaScore = ewmaScores[idx]?.ewmaScore || 0;
    const rateOfChange = idx === 0 ? 0 : Math.abs(d.value - filteredData[idx - 1].value);
    const hampelScore = (hampelResult.scores[idx] && hampelResult.scores[idx].hampelScore) || 0;
    const madScore = (madResult.scores[idx] && madResult.scores[idx].madScore) || 0;
    return {
      ...d,
      zScore,
      absDeviation,
      ewmaScore,
      rateOfChange,
      hampelScore,
      madScore,
      isZScoreAnomaly: (zScoreResult.scores[idx] && zScoreResult.scores[idx].isZScoreAnomaly),
      isMADAnomaly: (madResult.scores[idx] && madResult.scores[idx].isMADAnomaly),
      isEWMAAnomaly: (ewmaResult.scores[idx] && ewmaResult.scores[idx].isEWMAAnomaly),
      isHampelAnomaly: (hampelResult.scores[idx] && hampelResult.scores[idx].isHampelAnomaly),
      isRateAnomaly: (rateResult.scores[idx] && rateResult.scores[idx].isRateAnomaly),
    };
  });

  // Combine all anomalies for the table display
  const allAnomalies = scoredData.filter(
    (d) =>
      d.isZScoreAnomaly ||
      d.isMADAnomaly ||
      d.isEWMAAnomaly ||
      d.isHampelAnomaly ||
      d.isRateAnomaly
  );

  // Filter anomalies for the table by search term
  const filteredAnomalies = allAnomalies.filter(anomaly => {
    if (!search) return true;
    const date = new Date(anomaly.timestamp);
    const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
    const deviation = ((anomaly.value - 70) / 70 * 100).toFixed(1);
    return (
      formattedDate.toLowerCase().includes(search.toLowerCase()) ||
      anomaly.value.toString().includes(search) ||
      deviation.includes(search)
    );
  });

  // Custom tooltip for both graphs
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const point = payload[0].payload;
      const isAnomaly =
        point.isAnomaly || point.isZScoreAnomaly || point.isMADAnomaly || point.isEWMAAnomaly || point.isHampelAnomaly || point.isRateAnomaly;
      return (
        <div className="bg-white p-2 rounded shadow border">
          <p className="text-xs text-gray-500">{`Time: ${label}`}</p>
          <p className={`font-bold ${isAnomaly ? 'text-red-600' : 'text-blue-700'}`}>
            Value: {point.value}
            {isAnomaly && (
              <span className="ml-2 px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs font-semibold">
                Anomaly
              </span>
            )}
          </p>
          {point.zScore !== undefined && <p className="text-xs">Z-Score: {point.zScore.toFixed(2)}</p>}
          {point.madScore !== undefined && <p className="text-xs">MAD Score: {point.madScore.toFixed(2)}</p>}
          {point.ewmaScore !== undefined && <p className="text-xs">EWMA Score: {point.ewmaScore.toFixed(2)}</p>}
          {point.hampelScore !== undefined && <p className="text-xs">Hampel Score: {point.hampelScore.toFixed(2)}</p>}
          {point.rateChange !== undefined && <p className="text-xs">Rate Change: {point.rateChange.toFixed(2)}</p>}
        </div>
      );
    }
    return null;
  };

  // Helper to map anomaly score to color
  function getHeatColor(score, maxScore) {
    if (score === null || score === undefined) return "#e5e7eb";
    const ratio = Math.min(Math.abs(score) / (maxScore || 1), 1);
    if (ratio < 0.33) return "#60a5fa";
    if (ratio < 0.66) return "#fde047";
    return "#ef4444";
  }

  // Find max anomaly score for color scaling
  const maxAnomalyScore = Math.max(
    ...scoredData.map(d =>
      Math.max(
        Math.abs(d.zScore || 0),
        Math.abs(d.madScore || 0),
        Math.abs(d.ewmaScore || 0),
        Math.abs(d.hampelScore || 0),
        Math.abs(d.rateOfChange || 0)
      )
    )
  );

  // Filtered data for graph and table based on selection
  const displayedScoredData = selectedAnomaly
    ? scoredData.filter(d => d.timestamp === selectedAnomaly.timestamp)
    : scoredData;

  const displayedAnomalies = selectedAnomaly
    ? filteredAnomalies.filter(d => d.timestamp === selectedAnomaly.timestamp)
    : filteredAnomalies;

  // The graph itself: Line chart with heatmap bar
  const renderGraph = () => {
    if (loading) {
      return (
        <div className="h-80 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      );
    }
    return (
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart
          data={displayedScoredData}
          onClick={e => {
            if (
              e &&
              e.activePayload &&
              e.activePayload.length > 0 &&
              e.activePayload[0].payload
            ) {
              setSelectedAnomaly(e.activePayload[0].payload);
            }
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="displayTime"
            minTickGap={20}
            tickFormatter={(tick) => tick}
            tick={{ fontSize: 10, fill: '#6b7280' }}
            axisLine={{ stroke: '#d1d5db' }}
            tickLine={{ stroke: '#d1d5db' }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#6b7280' }}
            axisLine={{ stroke: '#d1d5db' }}
            tickLine={{ stroke: '#d1d5db' }}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
          <Legend verticalAlign="top" height={36} />
          {/* Heatmap bar: color by anomaly score (zScore here) */}
          <Bar
            dataKey="zScore"
            barSize={16}
            shape={(props) => {
              const { x, y, width, height, payload } = props;
              const color = getHeatColor(payload.zScore, maxAnomalyScore);
              return (
                <rect
                  x={x}
                  y={y}
                  width={width}
                  height={height}
                  fill={color}
                  rx={3}
                  ry={3}
                  style={{ opacity: 0.7 }}
                />
              );
            }}
            legendType="none"
          />
          {/* Line for sensor value */}
          <Line
            type="monotone"
            dataKey="value"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            name="Sensor Value"
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  };

  // Render anomaly details card if an anomaly is selected
  const renderAnomalyDetails = () => {
    if (!selectedAnomaly) return null;
    const dateObj = new Date(selectedAnomaly.timestamp);
    return (
      <div className="mb-4 p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded animate-fade-in">
        <div className="font-bold text-yellow-800 mb-1">Anomaly Details</div>
        <div className="text-sm text-gray-700">
          <div><span className="font-semibold">Timestamp:</span> {selectedAnomaly.timestamp}</div>
          <div><span className="font-semibold">Value:</span> {selectedAnomaly.value}</div>
          <div><span className="font-semibold">Date:</span> {dateObj.toLocaleString()}</div>
          {selectedAnomaly.zScore !== undefined && <div><span className="font-semibold">Z-Score:</span> {selectedAnomaly.zScore.toFixed(2)}</div>}
          {selectedAnomaly.madScore !== undefined && <div><span className="font-semibold">MAD Score:</span> {selectedAnomaly.madScore.toFixed(2)}</div>}
          {selectedAnomaly.ewmaScore !== undefined && <div><span className="font-semibold">EWMA Score:</span> {selectedAnomaly.ewmaScore.toFixed(2)}</div>}
          {selectedAnomaly.hampelScore !== undefined && <div><span className="font-semibold">Hampel Score:</span> {selectedAnomaly.hampelScore.toFixed(2)}</div>}
          {selectedAnomaly.rateChange !== undefined && <div><span className="font-semibold">Rate Change:</span> {selectedAnomaly.rateChange.toFixed(2)}</div>}
        </div>
        <button
          className="mt-2 text-blue-600 underline text-xs hover:text-blue-800"
          onClick={() => setSelectedAnomaly(null)}
        >
          Show Full Graph
        </button>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out forwards;
        }
      `}</style>
      <header className="flex items-center justify-between px-6 py-4 bg-white shadow-md">
        <div className="flex items-center space-x-3">
          <img src={infinity} alt="Logo" className="h-8 w-8" />
          <span className="font-bold text-xl text-blue-700">IoT Anomaly Dashboard</span>
        </div>
        <div className="flex items-center space-x-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Search anomalies..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1 rounded-md border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          </div>
          <button
            className={`flex items-center px-3 py-1 rounded-md text-sm transition-colors duration-200 ${autoRefresh ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
            onClick={() => setAutoRefresh(r => !r)}
          >
            <RefreshCw className="mr-1" size={16} />
            {autoRefresh ? 'Auto-refreshing' : 'Manual Refresh'}
          </button>
          <Settings className="text-gray-400 hover:text-gray-600 cursor-pointer" size={20} />
        </div>
      </header>

      <main className="px-6 py-6">
        {/* Date Range Selector */}
        <div className="flex items-center space-x-2 mb-4">
          <Calendar className="text-gray-600" size={18} />
          <div className="flex space-x-1">
            {['Last 24 hours', 'Last 7 days', 'Last 30 days', 'Custom'].map((range) => (
              <button
                key={range}
                className={`px-3 py-1 text-sm rounded-md transition-colors duration-200 ${selectedDateRange === range ? 'bg-blue-600 text-white shadow' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                onClick={() => setSelectedDateRange(range)}
              >
                {range}
              </button>
            ))}
          </div>
          {selectedDateRange === 'Custom' && (
            <div className="flex items-center space-x-2 ml-4">
              <input
                type="datetime-local"
                value={customRange.start}
                onChange={e => setCustomRange(r => ({ ...r, start: e.target.value }))}
                className="border rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200"
              />
              <span>to</span>
              <input
                type="datetime-local"
                value={customRange.end}
                onChange={e => setCustomRange(r => ({ ...r, end: e.target.value }))}
                className="border rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200"
              />
            </div>
          )}
        </div>

        {/* Anomaly Details Card (appears when an anomaly is selected) */}
        {renderAnomalyDetails()}

        {/* Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <MetricCard
            title="Z-SCORE Anomalies"
            value={zScoreResult.count}
            icon={BarChart2}
            color="orange"
            trend={null}
            onInfo={() => setOpenMetricInfo(openMetricInfo === "Z-SCORE Anomalies" ? null : "Z-SCORE Anomalies")}
            infoOpen={openMetricInfo === "Z-SCORE Anomalies"}
          />
          <MetricCard
            title="MAD Anomalies"
            value={madResult.count}
            icon={AlertCircle}
            color="red"
            trend={null}
            onInfo={() => setOpenMetricInfo(openMetricInfo === "MAD Anomalies" ? null : "MAD Anomalies")}
            infoOpen={openMetricInfo === "MAD Anomalies"}
          />
          <MetricCard
            title="EWMA Anomalies"
            value={ewmaResult.count}
            icon={Zap}
            color="blue"
            trend={null}
            onInfo={() => setOpenMetricInfo(openMetricInfo === "EWMA Anomalies" ? null : "EWMA Anomalies")}
            infoOpen={openMetricInfo === "EWMA Anomalies"}
          />
          <MetricCard
            title="HAMPEL Anomalies"
            value={hampelResult.count}
            icon={TrendingUp}
            color="purple"
            trend={null}
            onInfo={() => setOpenMetricInfo(openMetricInfo === "HAMPEL Anomalies" ? null : "HAMPEL Anomalies")}
            infoOpen={openMetricInfo === "HAMPEL Anomalies"}
          />
          <MetricCard
            title="RATE-OF-CHANGE"
            value={rateResult.count}
            icon={Database}
            color="emerald"
            trend={null}
            onInfo={() => setOpenMetricInfo(openMetricInfo === "RATE-OF-CHANGE" ? null : "RATE-OF-CHANGE")}
            infoOpen={openMetricInfo === "RATE-OF-CHANGE"}
          />
          <MetricCard
            title="Maximum Value"
            value={maxValue}
            icon={Star}
            trend={null}
            color="yellow"
            onInfo={() => setOpenMetricInfo(openMetricInfo === "Maximum Value" ? null : "Maximum Value")}
            infoOpen={openMetricInfo === "Maximum Value"}
          />
        </div>

        {/* Sensor Reading Time Series Graph */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-6">
          <div className="flex justify-between items-center mb-2">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">Sensor Reading Time Series</h2>
            </div>
            {selectedAnomaly && (
              <button
                className="text-blue-600 text-sm underline ml-2 hover:text-blue-800 transition-colors duration-200"
                onClick={() => setSelectedAnomaly(null)}
              >
                Show Full Graph
              </button>
            )}
          </div>
          {renderGraph()}
        </div>

        {/* Anomaly Table */}
        <AnomalyTable
          anomalies={displayedAnomalies}
          onRowClick={anomaly => setSelectedAnomaly(anomaly)}
        />
      </main>
    </div>
  );
}

export default IoTAnomalyDetectionDashboard;