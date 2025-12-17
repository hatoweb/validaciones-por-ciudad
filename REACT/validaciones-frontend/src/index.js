import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { initGA, trackPageView } from './utils/analytics';

// Inicializar Google Analytics cuando la app se carga
// Esperar a que el DOM esté completamente listo
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initGA();
    // Trackear la vista inicial de la página después de un pequeño delay
    setTimeout(() => {
      trackPageView();
    }, 200);
  });
} else {
  // DOM ya está listo
  setTimeout(() => {
    initGA();
    trackPageView();
  }, 100);
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);