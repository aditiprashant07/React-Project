// src/Settings.js
import React, { useState, useEffect, createContext, useContext } from 'react';
import { Settings as SettingsIcon, Thermometer, AlertTriangle, Cloud, Zap, TrendingUp, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

// Define the default threshold configurations
const THRESHOLDS = {
  restricted: {
    zScore: 3.5,
    mad: 3.5,
    ewma: 2.5,
    hampel: 3.5,
    rate: 25,
  },
  normal: {
    zScore: 2.7,
    mad: 2.7,
    ewma: 2.0,
    hampel: 2.7,
    rate: 15,
  },
  relaxed: {
    zScore: 2.0,
    mad: 2.0,
    ewma: 1.5,
    hampel: 2.0,
    rate: 10,
  },
  default: { // Used as initial custom values, aligned with 'normal'
    zScore: 2.7,
    mad: 2.7,
    ewma: 2.0,
    hampel: 2.7,
    rate: 15,
  },
};

// Create a React Context for thresholds
const ThresholdContext = createContext();

// Custom hook to use the threshold context
export const useThresholds = () => useContext(ThresholdContext);

// Thresholds Provider Component
export const ThresholdProvider = ({ children }) => {
  // Try to load state from localStorage, otherwise use 'normal' as the initial mode
  const [mode, setMode] = useState(() => localStorage.getItem('thresholdMode') || 'normal');

  const [customThresholds, setCustomThresholds] = useState(() => {
    try {
      const storedCustom = localStorage.getItem('customThresholds');
      return storedCustom ? JSON.parse(storedCustom) : { ...THRESHOLDS.default };
    } catch (e) {
      console.error("Failed to parse custom thresholds from localStorage", e);
      return { ...THRESHOLDS.default }; // Fallback to THRESHOLDS.default
    }
  });

  useEffect(() => {
    localStorage.setItem('thresholdMode', mode);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem('customThresholds', JSON.stringify(customThresholds));
  }, [customThresholds]);

  // Determine the active thresholds based on the selected mode
  const activeThresholds = mode === 'custom' ? customThresholds : THRESHOLDS[mode];

  const value = {
    mode,
    setMode,
    customThresholds,
    setCustomThresholds,
    activeThresholds,
    THRESHOLDS
  };

  return (
    <ThresholdContext.Provider value={value}>
      {children}
    </ThresholdContext.Provider>
  );
};

// Settings Page Component
function Settings() {
  const { mode, setMode, customThresholds, setCustomThresholds, THRESHOLDS } = useThresholds();

  const handleCustomChange = (e) => {
    const { name, value } = e.target;
    const numValue = parseFloat(value);
    setCustomThresholds(prev => ({ ...prev, [name]: isNaN(numValue) ? e.target.value : numValue }));
  };

  const getCustomValue = (key) => {
    return customThresholds[key] !== undefined && customThresholds[key] !== null
           ? customThresholds[key]
           : THRESHOLDS.default[key];
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <SettingsIcon size={30} className="text-gray-800" />
          <h1 className="text-3xl font-bold text-gray-800">Anomaly Detection Settings</h1>
        </div>
        {/* Button to go back to App.js */}
        <Link
          to="/"
          className="flex items-center space-x-2 text-gray-600 hover:text-blue-600 px-4 py-2 bg-white rounded-lg shadow hover:shadow-md transition-shadow duration-200"
        >
          <ArrowLeft size={20} />
          <span>Back to Dashboard</span>
        </Link>
      </header>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">Threshold Modes</h2>
        <div className="flex space-x-4 mb-6">
          {['relaxed', 'normal', 'restricted', 'custom'].map((m) => (
            <button
              key={m}
              className={`px-6 py-3 rounded-lg font-medium transition-all duration-200
                ${mode === m ? 'bg-blue-600 text-white shadow-md' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
              onClick={() => setMode(m)}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)} Mode
            </button>
          ))}
        </div>

        <h3 className="text-xl font-semibold text-gray-700 mb-4">Current Threshold Values:</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {Object.entries(THRESHOLDS.default).map(([key, defaultValue]) => (
            <div key={key} className="bg-gray-50 p-4 rounded-md border border-gray-200 flex items-center justify-between">
              <label htmlFor={key} className="block text-md font-medium text-gray-700 capitalize">
                {key.replace(/([A-Z])/g, ' $1').trim()} Threshold:
              </label>
              {mode === 'custom' ? (
                <input
                  type="text"
                  step="0.1"
                  name={key}
                  id={key}
                  value={getCustomValue(key)}
                  onChange={handleCustomChange}
                  className="mt-1 block w-24 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm text-right"
                />
              ) : (
                <span className="font-bold text-lg text-blue-700">
                  {THRESHOLDS[mode][key]}
                </span>
              )}
            </div>
          ))}
        </div>

        {mode === 'custom' && (
          <p className="mt-6 text-sm text-gray-600">
            * Adjust the input fields above to set custom thresholds. These values will be saved.
          </p>
        )}
        {/* Corrected descriptions and order */}
        <p className="mt-4 text-sm text-gray-600">
            <strong>Restricted Mode:</strong> Higher thresholds, fewer anomalies detected. Good for noisy data or when you want to catch only major deviations.
        </p>
        <p className="mt-2 text-sm text-gray-600">
            <strong>Normal Mode:</strong> Balanced thresholds, offering a good balance between catching significant deviations and avoiding excessive false positives.
        </p>
        <p className="mt-2 text-sm text-gray-600">
            <strong>Relaxed Mode:</strong> Lower thresholds, more anomalies detected. Suitable for highly sensitive monitoring where even minor deviations are important.
        </p>
      </div> {/* <-- This is the missing closing div tag */}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">Algorithm Explanations</h2>
        <div className="space-y-4">
          <div className="flex items-start">
            <Zap size={20} className="text-blue-500 mr-3 mt-1 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-lg text-gray-800">Z-Score</h3>
              <p className="text-gray-600 text-sm">Measures how many standard deviations a data point is from the mean. Higher absolute Z-Score indicates a greater deviation. A higher threshold in relaxed mode means a point needs to be *further* from the mean to be flagged.</p>
            </div>
          </div>
          <div className="flex items-start">
            <AlertTriangle size={20} className="text-green-500 mr-3 mt-1 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-lg text-gray-800">MAD Score (Median Absolute Deviation)</h3>
              <p className="text-gray-600 text-sm">Similar to Z-Score but uses median instead of mean and MAD instead of standard deviation, making it more robust to outliers. A higher MAD threshold means a point needs to deviate *more* from the median to be flagged.</p>
            </div>
          </div>
          <div className="flex items-start">
            <Cloud size={20} className="text-purple-500 mr-3 mt-1 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-lg text-gray-800">EWMA Score (Exponentially Weighted Moving Average)</h3>
              <p className="text-gray-600 text-sm">Detects shifts in the process mean. It assigns exponentially decreasing weights to older observations. A higher EWMA threshold means a point needs to deviate *more* from the EWMA to be flagged.</p>
            </div>
          </div>
          <div className="flex items-start">
            <Thermometer size={20} className="text-orange-500 mr-3 mt-1 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-lg text-gray-800">Hampel Score</h3>
              <p className="text-gray-600 text-sm">A robust outlier detection method that uses a sliding window to calculate local median and MAD. It's good for detecting localized anomalies. A higher Hampel threshold means a point needs to deviate *more* within its local window to be flagged.</p>
            </div>
          </div>
          <div className="flex items-start">
            <TrendingUp size={20} className="text-red-500 mr-3 mt-1 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-lg text-gray-800">Rate of Change</h3>
              <p className="text-gray-600 text-sm">Detects sudden spikes or drops by comparing the current value to the previous one. A higher rate threshold means a larger absolute change is required to be flagged as an anomaly.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;