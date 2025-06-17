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
import SettingsPage from './Settings';

// ✅ FIXED: Use your working API endpoint
const API_ENDPOINT = 'https://tzhkgzlfs3.execute-api.ap-northeast-1.amazonaws.com/prod';

const metricExplanations = {
  'Critical Anomalies': 'Critical severity anomalies requiring immediate attention.',
  'High Anomalies': 'High severity anomalies needing review.',
  'Medium Anomalies': 'Medium severity anomalies for monitoring.',
  'CPU Anomalies': 'CPU usage anomalies detected.',
  'Total Devices': 'Number of devices reporting anomalies.',
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

  // ✅ FIXED: Updated fetchData to work with your API Gateway response
  const fetchData = async () => {
    setLoading(true);
    try {
      console.log('🚀 Fetching data from:', API_ENDPOINT);

      // ✅ QUICK FIX: Remove problematic headers that trigger CORS preflight
      const res = await fetch(API_ENDPOINT, {
        method: 'GET',
        // headers removed to bypass CORS
        mode: 'cors'
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const apiResponse = await res.json();
      console.log('📥 API Response:', apiResponse);

      const anomaliesData = apiResponse.anomalies || [];
      const count = apiResponse.count || 0;

      console.log(`📊 Retrieved ${count} anomalies:`, anomaliesData);

      const transformedData = anomaliesData.map((anomaly, index) => ({
        ...anomaly,
        id: index,
        value: anomaly.metrics?.cpu_anomaly || 0,
        timestamp: anomaly.timestamp,
        displayTime: new Date(anomaly.timestamp).toLocaleTimeString(),
        isAnomaly: true,
        isZScoreAnomaly: anomaly.metrics?.anomaly_z_score > 1.5,
        isMADAnomaly: anomaly.metrics?.anomaly_hampel_score > 0,
        isEWMAAnomaly: anomaly.metrics?.anomaly_ewma_score > 2.0,
        isHampelAnomaly: anomaly.metrics?.anomaly_hampel_score > 0,
        isRateAnomaly: anomaly.metrics?.anomaly_rate_of_change > 50,
        isCritical: anomaly.severity === 'CRITICAL',
        isHigh: anomaly.severity === 'HIGH',
        isMedium: anomaly.severity === 'MEDIUM',
        deviceId: anomaly.device_id
      }));

      setData(transformedData);

      const stats = {
        totalAnomalies: count,
        anomalyCounts: {
          critical: transformedData.filter(d => d.severity === 'CRITICAL').length,
          high: transformedData.filter(d => d.severity === 'HIGH').length,
          medium: transformedData.filter(d => d.severity === 'MEDIUM').length,
          zScore: transformedData.filter(d => d.isZScoreAnomaly).length,
          mad: transformedData.filter(d => d.isMADAnomaly).length,
          ewma: transformedData.filter(d => d.isEWMAAnomaly).length,
          hampel: transformedData.filter(d => d.isHampelAnomaly).length,
          rate: transformedData.filter(d => d.isRateAnomaly).length,
          devices: new Set(transformedData.map(d => d.device_id)).size
        }
      };

      setStatistics(stats);
      console.log('📈 Statistics calculated:', stats);

    } catch (err) {
      console.error('❌ Fetch error:', err);
      setData([]);
      setStatistics({});

      if (err.message.includes('CORS') || err.message.includes('Failed to fetch')) {
        alert(`CORS Error: API Gateway needs CORS config.

Temporary fix: Use CORS proxy or update CloudFormation.

Error: ${err.message}`);
      } else {
        alert(`Failed to fetch data: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  // ✅ FIXED: Add additional API methods for different endpoints
  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API_ENDPOINT.replace('/anomalies', '/summary')}`);
      const data = await res.json();
      console.log('📊 Summary data:', data);
      return data;
    } catch (err) {
      console.error('Summary fetch error:', err);
      return null;
    }
  };

  const fetchDevices = async () => {
    try {
      const res = await fetch(`${API_ENDPOINT.replace('/anomalies', '/devices')}`);
      const data = await res.json();
      console.log('📱 Devices data:', data);
      return data;
    } catch (err) {
      console.error('Devices fetch error:', err);
      return null;
    }
  };

  useEffect(() => { 
    fetchData(); 
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // ✅ FIXED: Update filtering to work with new data structure
  const filteredAnomalies = (data || []).filter((anomaly) => {
    if (!search) return true;
    
    const searchLower = search.toLowerCase();
    const date = anomaly.timestamp ? new Date(anomaly.timestamp) : null;
    const formattedDate = date ? `${date.toLocaleDateString()} ${date.toLocaleTimeString()}` : '';
    
    return (
      formattedDate.includes(searchLower) ||
      (anomaly.device_id && anomaly.device_id.toLowerCase().includes(searchLower)) ||
      (anomaly.severity && anomaly.severity.toLowerCase().includes(searchLower)) ||
      (anomaly.value && anomaly.value.toString().includes(search))
    );
  });

  // ✅ FIXED: Use calculated statistics
  const anomalyCounts = statistics.anomalyCounts || {
    critical: 0,
    high: 0,
    medium: 0,
    zScore: 0,
    mad: 0,
    ewma: 0,
    hampel: 0,
    rate: 0,
    devices: 0
  };

  const handleRowClick = (anomaly) => {
    setSelectedAnomaly(anomaly);
    const idx = data.findIndex((d) => d.timestamp === anomaly.timestamp);
    const slice = data.slice(Math.max(0, idx - 5), idx + 6);
    setAnomalyWindowData(slice);
  };

  // ✅ FIXED: Auto-select first anomaly
  useEffect(() => {
    if (data && data.length > 0) {
      const first = data[0];
      setSelectedAnomaly(first);
      setAnomalyWindowData(data.slice(0, 6));
    } else {
      setSelectedAnomaly(null);
      setAnomalyWindowData([]);
    }
  }, [data]);

  // ✅ FIXED: Add debug button for testing
  const handleDebugAPI = async () => {
    console.log('🔧 Running API Debug Tests...');
    
    // Test different endpoints
    const tests = [
      { name: 'Anomalies', endpoint: '/anomalies' },
      { name: 'Summary', endpoint: '/summary' },
      { name: 'Devices', endpoint: '/devices' }
    ];
    
    for (const test of tests) {
      try {
        const url = `https://hjwx6b5m0b.execute-api.ap-northeast-1.amazonaws.com/prod${test.endpoint}`;
        console.log(`🧪 Testing ${test.name}: ${url}`);
        
        const res = await fetch(url);
        const data = await res.json();
        
        console.log(`✅ ${test.name} response:`, data);
      } catch (err) {
        console.error(`❌ ${test.name} failed:`, err);
      }
    }
  };

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
          
          {/* ✅ ADDED: Debug button for testing */}
          <button 
            className="flex items-center space-x-2 text-gray-600 hover:text-green-600" 
            onClick={handleDebugAPI}
          >
            <AlertCircle size={20} />
            <span>Debug API</span>
          </button>
          
          <button className="flex items-center space-x-2 text-gray-600 hover:text-blue-600" onClick={fetchData}>
            <RefreshCw size={20} />
            <span>Refresh Data</span>
          </button>
        </div>
      </header>

      {/* ✅ FIXED: Updated metric cards to show relevant data */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-6">
        {[
          { title: 'Critical Anomalies', value: anomalyCounts.critical, icon: AlertCircle, color: 'red' },
          { title: 'High Anomalies', value: anomalyCounts.high, icon: AlertCircle, color: 'orange' },
          { title: 'Medium Anomalies', value: anomalyCounts.medium, icon: AlertCircle, color: 'yellow' },
          { title: 'Total Devices', value: anomalyCounts.devices, icon: TrendingUp, color: 'blue' },
          { title: 'RATE-OF-CHANGE', value: anomalyCounts.rate, icon: TrendingUp, color: 'purple' },
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

      {/* Status indicator */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className={`h-3 w-3 rounded-full ${loading ? 'bg-yellow-400' : 'bg-green-400'}`}></div>
            <span className="text-sm text-gray-600">
              {loading ? 'Loading...' : `Connected - ${data.length} anomalies loaded`}
            </span>
          </div>
          <div className="text-sm text-gray-500">
            API: {API_ENDPOINT}
          </div>
        </div>
      </div>

      {/* Thresholds */}
      <ThresholdPanel loading={loading} />

      {/* Graph */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
          <BarChart2 size={20} className="mr-2" /> Anomaly Context
          {selectedAnomaly && (
            <span className="ml-2 text-base text-gray-500">
              (for {selectedAnomaly.device_id} at {selectedAnomaly.displayTime})
            </span>
          )}
        </h2>
        <AnomalyGraph data={anomalyWindowData} selectedAnomaly={selectedAnomaly} />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
          <AlertCircle size={20} className="mr-2" /> Anomaly Details ({filteredAnomalies.length})
        </h2>
        <div className="mb-4 flex items-center space-x-4">
          <div className="relative flex-grow">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by device, severity, or time..."
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
            <span className="ml-3 text-sm font-medium text-gray-900">Auto-refresh (30s)</span>
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