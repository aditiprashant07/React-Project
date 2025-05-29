import React from 'react';

const AnomalyTable = ({ anomalies, onRowClick }) => {
  const getAnomalyTypes = (anomaly) => {
    const types = [];
    if (anomaly.isZScoreAnomaly) types.push("Z-Score");
    if (anomaly.isMADAnomaly) types.push("MAD");
    if (anomaly.isEWMAAnomaly) types.push("EWMA");
    if (anomaly.isHampelAnomaly) types.push("Hampel");
    if (anomaly.isRateAnomaly) types.push("Rate-of-Change");
    if (anomaly.isAnomaly) types.push("Mock");
    return types.join(", ");
  };

  if (!anomalies.length) {
    return <div className="bg-gray-50 rounded-lg p-6 text-center text-gray-500">No anomalies detected in the current time range.</div>;
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Deviation</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Anomaly Type</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {anomalies.map((anomaly, index) => {
            const date = new Date(anomaly.timestamp);
            const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
            const deviation = ((anomaly.value - 70) / 70 * 100).toFixed(1);
            return (
              <tr
                key={index}
                className="hover:bg-blue-50 cursor-pointer"
                onClick={() => onRowClick(anomaly)}
              >
                <td className="px-6 py-4 text-sm">{formattedDate}</td>
                <td className="px-6 py-4 text-sm">{anomaly.value}</td>
                <td className="px-6 py-4 text-sm">{deviation}%</td>
                <td className="px-6 py-4 text-sm">{getAnomalyTypes(anomaly)}</td>
                <td className="px-6 py-4">
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

export default AnomalyTable;
