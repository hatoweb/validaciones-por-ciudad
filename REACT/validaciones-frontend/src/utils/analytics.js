// Configuración de Google Analytics
// Reemplaza 'G-XXXXXXXXXX' con tu ID de medición de Google Analytics
// O configura la variable de entorno REACT_APP_GA_MEASUREMENT_ID
export const GA_MEASUREMENT_ID = process.env.REACT_APP_GA_MEASUREMENT_ID || 'G-XXXXXXXXXX';

// Variable para rastrear si GA ya fue inicializado
let isInitialized = false;

// Verificar si Google Analytics está habilitado
export const isGAEnabled = () => {
  return GA_MEASUREMENT_ID && 
         GA_MEASUREMENT_ID !== 'G-XXXXXXXXXX' && 
         typeof window !== 'undefined';
};

// Inicializar Google Analytics
export const initGA = () => {
  // Verificar si ya fue inicializado
  if (isInitialized) {
    return;
  }

  // Verificar si tenemos un ID válido
  if (!isGAEnabled()) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('Google Analytics no está configurado. Configura REACT_APP_GA_MEASUREMENT_ID en tu archivo .env');
    }
    return;
  }

  // Verificar si gtag está disponible (se define en index.html)
  if (typeof window.gtag === 'undefined') {
    console.error('Google Analytics gtag no está disponible. Verifica que el script esté cargado correctamente en index.html.');
    return;
  }

  // Cargar el script de Google Analytics dinámicamente si no existe
  const existingScript = document.querySelector('script[src*="googletagmanager.com/gtag/js"]');
  if (!existingScript) {
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
    script.onload = () => {
      // Esperar un momento para asegurar que gtag esté completamente cargado
      setTimeout(() => {
        // Configurar Google Analytics después de cargar el script
        if (typeof window.gtag !== 'undefined') {
          window.gtag('config', GA_MEASUREMENT_ID, {
            page_path: window.location.pathname + window.location.search,
            send_page_view: true
          });
          isInitialized = true;
          
          if (process.env.NODE_ENV === 'development') {
            console.log('Google Analytics inicializado correctamente con ID:', GA_MEASUREMENT_ID);
          }
        }
      }, 100);
    };
    script.onerror = () => {
      console.error('Error al cargar el script de Google Analytics');
    };
    document.head.appendChild(script);
  } else {
    // Si el script ya existe, esperar un momento y luego configurar
    setTimeout(() => {
      if (typeof window.gtag !== 'undefined') {
        window.gtag('config', GA_MEASUREMENT_ID, {
          page_path: window.location.pathname + window.location.search,
          send_page_view: true
        });
        isInitialized = true;
        
        if (process.env.NODE_ENV === 'development') {
          console.log('Google Analytics configurado correctamente con ID:', GA_MEASUREMENT_ID);
        }
      }
    }, 100);
  }
};

// Trackear una página vista
export const trackPageView = (path) => {
  if (!isGAEnabled()) return;
  
  window.gtag('config', GA_MEASUREMENT_ID, {
    page_path: path || window.location.pathname + window.location.search,
  });
};

// Trackear un evento personalizado
export const trackEvent = (eventName, eventParams = {}) => {
  if (!isGAEnabled()) return;
  
  window.gtag('event', eventName, eventParams);
};

// Eventos específicos de la aplicación
export const analyticsEvents = {
  // Eventos de filtros
  filterMonth: (month) => trackEvent('filter_month', { month }),
  filterYear: (year) => trackEvent('filter_year', { year }),
  filterFranja: (franjaId, franjaName) => trackEvent('filter_franja', { 
    franja_id: franjaId, 
    franja_name: franjaName 
  }),
  filterBarrios: (incluirBarrios) => trackEvent('filter_barrios', { 
    incluir_barrios: incluirBarrios 
  }),
  filterCriterio: (criterio) => trackEvent('filter_criterio', { criterio }),
  filterMapLayer: (layer) => trackEvent('filter_map_layer', { layer }),
  
  // Eventos de datos
  fetchData: (params) => trackEvent('fetch_data', {
    mes: params.mes,
    anio: params.anio,
    id_franja: params.id_franja,
    incluir_barrios: params.incluir_barrios,
  }),
  fetchDataSuccess: (params) => trackEvent('fetch_data_success', {
    mes: params.mes,
    anio: params.anio,
    total_validaciones: params.total_validaciones,
    total_pasajeros: params.total_pasajeros,
    total_buses: params.total_buses,
  }),
  fetchDataError: (error) => trackEvent('fetch_data_error', {
    error_message: error.message,
    error_code: error.code,
  }),
  
  // Eventos de interacción con el mapa
  mapFeatureClick: (featureName) => trackEvent('map_feature_click', { 
    feature_name: featureName 
  }),
  mapFeatureHover: (featureName) => trackEvent('map_feature_hover', { 
    feature_name: featureName 
  }),
  
  // Eventos de tabla
  tableSort: (column, direction) => trackEvent('table_sort', { 
    column, 
    direction 
  }),
  tableSearch: (searchTerm) => trackEvent('table_search', { 
    search_term: searchTerm 
  }),
  tableRowClick: (rowName) => trackEvent('table_row_click', { 
    row_name: rowName 
  }),
  
  // Eventos de exportación
  exportPDF: (params) => trackEvent('export_pdf', {
    mes: params.mes,
    anio: params.anio,
    tipo_area: params.tipo_area,
    total_rows: params.total_rows,
  }),
  
  // Eventos de opacidad
  changeOpacity: (opacity) => trackEvent('change_opacity', { 
    opacity: Math.round(opacity * 100) 
  }),
};

