import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  BarChart2,
  RefreshCw,
  Settings,
  TrendingUp,
  Search,
} from 'lucide-react';
import { Routes, Route, useNavigate } from 'react-router-dom';
import infinity from './Infinity.png';
import MetricCard from './components/MetricCard';
import AnomalyTable from './components/AnomalyTable';
import AnomalyGraph from './components/AnomalyGraph';
import ThresholdPanel from './components/ThresholdPanel';
import SettingsPage from './Settings'; // Make sure this path is correct

const API_ENDPOINT = 'https://prjzcbe770.execute-api.ap-northeast-1.amazonaws.com/prod/anomalies';

const metricExplanations = {
  'Z-SCORE Anomalies': 'Z-Score flags points far from the mean.',
  'MAD Anomalies': 'MAD highlights deviations from the median.',
  'EWMA Anomalies': 'EWMA flags shifts in weighted averages.',
  'HAMPEL Anomalies': 'Hampel detects outliers via rolling median and MAD.',
  'RATE-OF-CHANGE': 'Rate-of-Change detects sudden jumps between values.',
};

function Dashboard() {
  const [data, setData] = useState([]);
  const [statistics, setStatistics] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);
  const [anomalyWindowData, setAnomalyWindowData] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [openMetricInfo, setOpenMetricInfo] = useState(null);

  const navigate = useNavigate();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(API_ENDPOINT);

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const apiGatewayResponse = await res.json();

      let dataFromLambda = [];
      let statsFromLambda = {};

      try {
        const parsedBody = JSON.parse(apiGatewayResponse.body);
        dataFromLambda = parsedBody.data || [];
        statsFromLambda = parsedBody.statistics || {};
      } catch (parseError) {
        console.error("Error parsing Lambda's body:", parseError, apiGatewayResponse.body);
        if (Array.isArray(apiGatewayResponse.body)) {
          dataFromLambda = apiGatewayResponse.body;
        } else {
          dataFromLambda = [];
        }
        if (typeof apiGatewayResponse.body === 'object' && apiGatewayResponse.body !== null && 'statistics' in apiGatewayResponse.body) {
          statsFromLambda = apiGatewayResponse.body.statistics;
        } else {
          statsFromLambda = {};
        }
      }

      setData(dataFromLambda);
      setStatistics(statsFromLambda);

    } catch (err) {
      console.error('Fetch error:', err);
      setData([]);
      setStatistics({});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const filteredAnomalies = (data || []).filter((d) =>
    d.isZScoreAnomaly ||
    d.isMADAnomaly ||
    d.isEWMAAnomaly ||
    d.isHampelAnomaly ||
    d.isRateAnomaly
  ).filter((anomaly) => {
    const date = anomaly.timestamp ? new Date(anomaly.timestamp) : null;
    const formattedDate = date ? `${date.toLocaleDateString()} ${date.toLocaleTimeString()}` : '';
    const deviation = (anomaly.value !== undefined && anomaly.value !== null) ? ((anomaly.value - 70) / 70 * 100).toFixed(1) : '';
    return (
      formattedDate.toLowerCase().includes(search.toLowerCase()) ||
      (anomaly.value !== undefined && anomaly.value !== null && anomaly.value.toString().includes(search)) ||
      deviation.includes(search)
    );
  });

  const anomalyCounts = statistics.anomalyCounts || {
    zScore: data.filter((d) => d.isZScoreAnomaly).length,
    mad: data.filter((d) => d.isMADAnomaly).length,
    ewma: data.filter((d) => d.isEWMAAnomaly).length,
    hampel: data.filter((d) => d.isHampelAnomaly).length,
    rate: data.filter((d) => d.isRateAnomaly).length,
  };

  const handleRowClick = (anomaly) => {
    setSelectedAnomaly(anomaly);
    const idx = data.findIndex((d) => d.timestamp === anomaly.timestamp);
    const slice = data.slice(Math.max(0, idx - 5), idx + 6);
    setAnomalyWindowData(slice);
  };

  useEffect(() => {
    const anomalies = (data || []).filter((d) =>
      d.isZScoreAnomaly ||
      d.isMADAnomaly ||
      d.isEWMAAnomaly ||
      d.isHampelAnomaly ||
      d.isRateAnomaly ||
      d.isAnomaly
    );
    if (anomalies.length > 0) {
      const first = anomalies[0];
      setSelectedAnomaly(first);
      const idx = data.findIndex((d) => d.timestamp === first.timestamp);
      const slice = data.slice(Math.max(0, idx - 5), idx + 6);
      setAnomalyWindowData(slice);
    } else {
      setSelectedAnomaly(null);
      setAnomalyWindowData([]);
    }
  }, [data]);

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <img src={infinity} alt="Infinity Logo" className="h-10 w-10" />
          <h1 className="text-3xl font-bold text-gray-800">IoT Anomaly Detection Dashboard</h1>
        </div>
        <div className="flex items-center space-x-4">
          <button
            className="flex items-center space-x-2 text-gray-600 hover:text-blue-600"
            onClick={() => navigate('/settings')}
          >
            <Settings size={20} />
            <span>Settings</span>
          </button>
          <button className="flex items-center space-x-2 text-gray-600 hover:text-blue-600" onClick={fetchData}>
            <RefreshCw size={20} />
            <span>Refresh Data</span>
          </button>
        </div>
      </header>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-6">
        {[
          { title: 'Z-SCORE Anomalies', value: anomalyCounts.zScore, icon: AlertCircle, color: 'red' },
          { title: 'MAD Anomalies', value: anomalyCounts.mad, icon: AlertCircle, color: 'red' },
          { title: 'EWMA Anomalies', value: anomalyCounts.ewma, icon: AlertCircle, color: 'red' },
          { title: 'HAMPEL Anomalies', value: anomalyCounts.hampel, icon: AlertCircle, color: 'red' },
          { title: 'RATE-OF-CHANGE', value: anomalyCounts.rate, icon: TrendingUp, color: 'red' },
        ].map((item) => (
          <MetricCard
            key={item.title}
            {...item}
            explanation={metricExplanations[item.title]}
            infoOpen={openMetricInfo === item.title}
            onInfo={() => setOpenMetricInfo(openMetricInfo === item.title ? null : item.title)}
          />
        ))}
      </div>

      {/* Thresholds */}
      <ThresholdPanel loading={loading} />

      {/* Graph */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
          <BarChart2 size={20} className="mr-2" /> Anomaly Context
          {selectedAnomaly && (
            <span className="ml-2 text-base text-gray-500">
              (for anomaly at {selectedAnomaly.displayTime || new Date(selectedAnomaly.timestamp).toLocaleTimeString()})
            </span>
          )}
        </h2>
        <AnomalyGraph data={anomalyWindowData} selectedAnomaly={selectedAnomaly} />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
          <AlertCircle size={20} className="mr-2" /> Anomaly Details
        </h2>
        <div className="mb-4 flex items-center space-x-4">
          <div className="relative flex-grow">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search anomalies..."
              className="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <label className="inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={autoRefresh}
              onChange={() => setAutoRefresh(!autoRefresh)}
            />
            <div className="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:bg-blue-600 relative">
              <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full peer-checked:left-6 transition-all"></div>
            </div>
            <span className="ml-3 text-sm font-medium text-gray-900">Auto-refresh</span>
          </label>
        </div>
        <AnomalyTable
          anomalies={filteredAnomalies}
          onRowClick={handleRowClick}
        />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  );
}