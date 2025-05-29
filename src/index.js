import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { ThresholdProvider } from './Settings';
import { BrowserRouter } from 'react-router-dom';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ThresholdProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThresholdProvider>
  </React.StrictMode>
);
