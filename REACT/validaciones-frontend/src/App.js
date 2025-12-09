// src/App.js
import React, { useState, useMemo, useRef, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

// Helper para obtener el prefijo de la aplicación basándose en la URL actual
// Detecta automáticamente si estamos en /validaciones/ o en la raíz
const getAppPrefix = () => {
  // Detectar desde la URL actual (más confiable que process.env en runtime)
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const pathname = window.location.pathname;
    
    // Si estamos en el dominio de producción, siempre usar /validaciones
    if (hostname === 'sistemas.mopc.gov.py' || hostname.includes('mopc.gov.py')) {
      return '/validaciones';
    }
    
    // Si el pathname comienza con /validaciones, usar ese prefijo
    if (pathname && pathname.startsWith('/validaciones')) {
      return '/validaciones';
    }
  }
  
  // Si process.env.PUBLIC_URL está configurado, usarlo (funciona en build time)
  if (process.env.PUBLIC_URL) {
    return process.env.PUBLIC_URL;
  }
  
  // Fallback: vacío (para desarrollo local en localhost)
  return '';
};

// Helper para construir URLs de API con el prefijo correcto
// El proxy externo mantiene el prefijo /validaciones, por lo que las APIs
// deben ir a /validaciones/api/... para que el proxy las reenvíe correctamente
const getApiUrl = (path) => {
  // Asegurarse de que el path empiece con /
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  
  // Detectar prefijo explícitamente
  let apiPrefix = '';
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const pathname = window.location.pathname;
    
    // Si estamos en el dominio de producción, SIEMPRE usar /validaciones
    if (hostname === 'sistemas.mopc.gov.py' || hostname.includes('mopc.gov.py')) {
      apiPrefix = '/validaciones';
    } else if (pathname && pathname.startsWith('/validaciones')) {
      apiPrefix = '/validaciones';
    } else if (process.env.PUBLIC_URL) {
      apiPrefix = process.env.PUBLIC_URL;
    }
  } else if (process.env.PUBLIC_URL) {
    apiPrefix = process.env.PUBLIC_URL;
  }
  
  const finalUrl = `${apiPrefix}${cleanPath}`;
  
  // Log para depuración - siempre activo para ver qué URL se está usando
  console.log('[DEBUG API] URL construida:', finalUrl, '| Prefijo detectado:', apiPrefix, '| Hostname:', typeof window !== 'undefined' ? window.location.hostname : 'N/A', '| Path original:', path);
  
  return finalUrl;
};

// Helper para construir URLs de archivos estáticos con el prefijo correcto
const getStaticUrl = (path) => {
  const prefix = getAppPrefix();
  // Asegurarse de que el path empiece con /
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${prefix}${cleanPath}`;
};

function getTurquoiseColor(intensity){
  // if(intensity <= 0.2) return '#d0f2ec';
  // if(intensity <= 0.4) return '#9ee6db';
  // if(intensity <= 0.6) return '#5fd3c2';
  // if(intensity <= 0.8) return '#2aaea2';
  if(intensity <= 0.2) return '#4dd3c9';
  if(intensity <= 0.4) return '#3dbfb5';
  if(intensity <= 0.6) return '#2da9a0';
  if(intensity <= 0.8) return '#1e8f87';
  return '#0f5f5a';
}

function getFeatureValue(feature, criterio){
  const p = feature.properties || {};
  if(criterio === 'validaciones') return Number(p.cantidad_validaciones || 0);
  if(criterio === 'porcentaje'){
    const pasajeros = Number(p.cantidad_pasajeros || 0);
    const poblacion = Number(p.POBLACION || p.poblacion || 0);
    if(!poblacion || poblacion === 0) return 0;
    return (pasajeros / poblacion) * 100;
  }
  if(criterio === 'buses') return Number(p.cantidad_buses || 0);
  if(criterio === 'empresas') return Number(p.num_empresas || 0);
  if(criterio === 'lineas') return Number(p.num_lineas || 0);
  return Number(p.cantidad_validaciones || 0);
}

// Función para calcular la intensidad según la segmentación fija de Tasa de uso
function getPorcentajeIntensity(valorPorcentaje){
  if(valorPorcentaje <= 0) return 0;
  if(valorPorcentaje <= 25) return 0.2;  // 0% - 25%
  if(valorPorcentaje <= 50) return 0.4;  // 26% - 50%
  if(valorPorcentaje <= 75) return 0.6;  // 51% - 75%
  if(valorPorcentaje <= 100) return 0.8; // 76% - 100%
  return 1.0; // > 100%
}

function getNameFromProps(props){
  if(!props) return 'Sin nombre';
  const keys = Object.keys(props);
  // Prioridad: columnas comunes que usamos en backend
  const candidates = ['barrio_completo','BARLO_DESC','DIST_DESC_','DIST_DESC','NOMBRE','nombre','Nombre','BARRIO','barrio','Barrio','name','NAME','nombre_area','area'];
  for(const c of candidates){
    if(c in props && props[c]) return String(props[c]);
  }
  // fallback: cualquier campo que parezca nombre
  for(const k of keys){
    if(k.toLowerCase().includes('barri') || k.toLowerCase().includes('dist') || k.toLowerCase().includes('nombre') || k.toLowerCase().includes('name')){
      if(props[k]) return String(props[k]);
    }
  }
  return props.name || props.NAME || 'Sin nombre';
}

// Componente para acceder a la instancia del mapa
function MapController({ centerMap, zoomToFeature, geoJsonLayerRef }) {
  const map = useMap();
  
  useEffect(() => {
    if (centerMap && zoomToFeature) {
      const feature = zoomToFeature;
      if (feature.geometry) {
        const layer = L.geoJSON(feature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
          
          // Encontrar y abrir el popup después de un pequeño delay para asegurar que el mapa se haya ajustado
          setTimeout(() => {
            if (geoJsonLayerRef && geoJsonLayerRef.current) {
              const featureName = getNameFromProps(feature.properties);
              geoJsonLayerRef.current.eachLayer((layer) => {
                if (layer.feature) {
                  const layerName = getNameFromProps(layer.feature.properties);
                  if (layerName === featureName) {
                    layer.openPopup();
                    layer.bringToFront();
                  }
                }
              });
            }
          }, 300);
        }
      }
    }
  }, [centerMap, zoomToFeature, map, geoJsonLayerRef]);
  
  return null;
}

function Legend({min, max, criterio}){
  if(max === 0 && min === 0) return null;
  let buckets = [];
  
  if(criterio === 'porcentaje'){
    // Segmentación fija para Tasa de uso
    buckets = [
      { label: '0% - 25%', color: getTurquoiseColor(0.2), intensity: 0.2 },
      { label: '26% - 50%', color: getTurquoiseColor(0.4), intensity: 0.4 },
      { label: '51% - 75%', color: getTurquoiseColor(0.6), intensity: 0.6 },
      { label: '76% - 100%', color: getTurquoiseColor(0.8), intensity: 0.8 },
      { label: '> 100%', color: getTurquoiseColor(1.0), intensity: 1.0 }
    ];
  } else {
    // Segmentación normal para otros criterios
    const steps = 5;
    const step = (max - min) / steps || 0;
    for(let i=0;i<steps;i++){
      const inicio = min + i*step;
      const fin = (i === steps-1) ? max : min + (i+1)*step;
      const intensity = (i+1)/steps;
      buckets.push({
        label: `${Math.round(inicio).toLocaleString()} - ${Math.round(fin).toLocaleString()}`,
        color: getTurquoiseColor(intensity)
      });
    }
  }
  
  const title = criterio === 'validaciones' ? 'Validaciones' : criterio === 'porcentaje' ? 'Tasa de uso' : criterio === 'buses' ? 'Buses' : criterio === 'empresas' ? 'Empresas' : 'Líneas';
  return (
    <div className="legend card">
      <strong>{title}</strong>
      {buckets.map((b,i) => (
        <div key={i} className="legend-row">
          <div className="legend-swatch" style={{background:b.color}} />
          <span className="legend-label">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function App(){
  const [geojson, setGeojson] = useState(null);
  const [criterio, setCriterio] = useState('validaciones');
  const [mes, setMes] = useState(new Date().getMonth()+1);
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [idFranja, setIdFranja] = useState(null);
  const [franjas, setFranjas] = useState([]);
  const [incluirBarrios, setIncluirBarrios] = useState(false);
  const [totals, setTotals] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showIndicadoresModal, setShowIndicadoresModal] = useState(false);
  const [opacity, setOpacity] = useState(0.9); // Estado para controlar la opacidad
  const [mapLayer, setMapLayer] = useState('street'); // Estado para la capa del mapa

  // Nombres de los meses
  const meses = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
  ];

  // Definición de capas del mapa
  const mapLayers = {
    street: {
      name: 'Calle',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    },
    satellite: {
      name: 'Satelital',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: '&copy; <a href="https://www.esri.com/">Esri</a>'
    }
  };

  // Función para obtener mensajes de error amigables
  const getErrorMessage = (err) => {
    const status = err.response?.status;
    
    // Error 504 - Gateway Timeout
    if (status === 504) {
      return 'El servidor está tardando más de lo esperado en procesar la solicitud. Por favor, intenta nuevamente en unos momentos. Si el problema persiste, puede que haya muchos datos para procesar o el servidor esté ocupado.';
    }
    
    // Error 503 - Service Unavailable
    if (status === 503) {
      return 'El servicio no está disponible temporalmente. Por favor, intenta nuevamente en unos momentos.';
    }
    
    // Error 500 - Internal Server Error
    if (status === 500) {
      return 'Ocurrió un error en el servidor. Por favor, intenta nuevamente. Si el problema persiste, contacta al administrador del sistema.';
    }
    
    // Error 404 - Not Found
    if (status === 404) {
      return 'No se encontró la información solicitada. Por favor, verifica los parámetros seleccionados e intenta nuevamente.';
    }
    
    // Error de timeout (sin código de estado)
    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout') || err.message?.includes('Timeout')) {
      return 'La solicitud está tardando demasiado tiempo. Por favor, intenta nuevamente o verifica tu conexión a internet.';
    }
    
    // Error de conexión
    if (err.code === 'ERR_NETWORK' || err.message?.includes('Network Error') || err.message?.includes('Failed to fetch')) {
      return 'No se pudo conectar con el servidor. Por favor, verifica tu conexión a internet e intenta nuevamente.';
    }
    
    // Error del servidor con mensaje personalizado
    if (err.response?.data?.error && typeof err.response.data.error === 'string') {
      // Si el mensaje ya es amigable, usarlo directamente
      const serverError = err.response.data.error;
      if (!serverError.includes('status code') && !serverError.includes('Request failed')) {
        return serverError;
      }
    }
    
    // Mensaje genérico para otros errores
    return 'Ocurrió un error al obtener los datos. Por favor, intenta nuevamente. Si el problema persiste, contacta al administrador del sistema.';
  };

  // Cargar franjas operativas al montar el componente
  useEffect(() => {
    const cargarFranjas = async () => {
      try {
        const res = await axios.get(getApiUrl('/api/franjas_operativas'));
        if (res.data.franjas && res.data.franjas.length > 0) {
          setFranjas(res.data.franjas);
          // Seleccionar Pico Mañana por defecto si existe, sino la primera
          const picoManana = res.data.franjas.find(f => 
            f.denominacion.toLowerCase().includes('pico mañana') || 
            f.denominacion.toLowerCase().includes('pico manana')
          );
          if (picoManana) {
            setIdFranja(picoManana.id_franja);
          } else {
            setIdFranja(res.data.franjas[0].id_franja);
          }
        }
      } catch (err) {
        console.error('Error al cargar franjas operativas:', err);
        const errorMessage = getErrorMessage(err);
        alert('Error al cargar las franjas operativas: ' + errorMessage);
      }
    };
    cargarFranjas();
  }, []);

  // const fetchData = async () => {
  //   setLoading(true);
  //   try {
  //     const res = await axios.post('/api/validaciones', {
  //       mes, anio, horario_pico: horario, incluir_barrios: incluirBarrios
  //     });
  //     if(res.data.error){
  //       alert(res.data.error);
  //     } else {
  //       setGeojson(res.data.geojson);
  //       // Ensure we're using the unique counts from the backend
  //       setTotals({
  //         ...res.data.totals,
  //         unique_passengers: res.data.totals?.unique_passengers ?? res.data.totals?.pasajeros,
  //         unique_buses: res.data.totals?.unique_buses ?? res.data.totals?.buses
  //       });
  //       setStats(res.data.stats || null);
  //     }
  //   } catch (err) {
  //     console.error(err);
  //     alert('Error al obtener datos: ' + (err.message || err));
  //   } finally {
  //     setLoading(false);
  //   }
  // };

  const fetchData = async () => {
    if (!idFranja) {
      alert('Por favor selecciona una franja operativa');
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post(getApiUrl('/api/validaciones'), {
        mes, anio, id_franja: idFranja, incluir_barrios: incluirBarrios
      });
      if(res.data.error){
        alert(res.data.error);
      } else {
        // Limpiar la referencia anterior antes de actualizar
        if (geoJsonLayerRef.current) {
          geoJsonLayerRef.current.clearLayers();
        }
        // Actualizar el GeoJSON y forzar re-render con nueva key
        setGeojson(res.data.geojson);
        setGeojsonKey(prev => prev + 1); // Incrementar key para forzar re-render
        setTotals({
          ...res.data.totals,
          // Ensure we're using the unique counts from the backend
          pasajeros: res.data.totals.unique_passengers ?? res.data.totals.pasajeros,
          buses: res.data.totals.unique_buses ?? res.data.totals.buses,
          dias_con_datos: res.data.totals.dias_con_datos ?? null,
          promedio_diario_pasajeros: res.data.totals.promedio_diario_pasajeros ?? null,
          promedio_diario_buses: res.data.totals.promedio_diario_buses ?? null
        });
        setStats(res.data.stats || null);
      }
    } catch (err) {
      console.error('Error completo:', err);
      console.error('Response data:', err.response?.data);
      console.error('Response status:', err.response?.status);
      const errorMessage = getErrorMessage(err);
      alert(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const computedStats = useMemo(() => {
    if(stats && stats[criterio]) {
      return { min: stats[criterio].min, max: stats[criterio].max };
    }
    if(!geojson) return {min:0,max:0};
    let min = Infinity, max = -Infinity;
    geojson.features.forEach(f => {
      const v = getFeatureValue(f, criterio);
      if(v < min) min = v;
      if(v > max) max = v;
    });
    if(min === Infinity) min = 0;
    if(max === -Infinity) max = 0;
    return {min, max};
  }, [geojson, criterio, stats]);

  const styleFeature = (feature) => {
    const val = getFeatureValue(feature, criterio);
    let color = '#f0f0f0';
    let intensity = 0;
    
    if(val >= 0){
      if(criterio === 'porcentaje'){
        // Usar segmentación fija para Tasa de uso
        intensity = getPorcentajeIntensity(val);
        color = getTurquoiseColor(intensity);
      } else {
        // Segmentación normal para otros criterios
        const maxVal = computedStats.max || 0;
        if(maxVal > 0 && val > 0){
          intensity = Math.min(1, val / maxVal);
          color = getTurquoiseColor(intensity);
        }
      }
    }
    
    return {
      fillColor: color,
      color: '#ffffff',
      weight: incluirBarrios ? 0.8 : 1.6,
      fillOpacity: opacity,
      dashArray: '0'
    };
  };

  // Ref para almacenar referencias de las capas
  const geoJsonLayerRef = useRef(null);
  // Refs para generar PDF
  const headerRef = useRef(null);
  const tableRef = useRef(null);
  // Key para forzar re-render del GeoJSON cuando cambian los datos
  const [geojsonKey, setGeojsonKey] = useState(0);
  // Estado para controlar el centrado del mapa desde la tabla
  const [centerMap, setCenterMap] = useState(0);
  const [zoomToFeature, setZoomToFeature] = useState(null);

  // Actualizar estilos cuando cambia el criterio u opacidad
  useEffect(() => {
    if (geoJsonLayerRef.current && geojson) {
      geoJsonLayerRef.current.eachLayer((layer) => {
        const feature = layer.feature;
        if (feature) {
          // Recalcular estilo basado en el criterio actual
          const val = getFeatureValue(feature, criterio);
          let color = '#f0f0f0';
          let intensity = 0;
          
          if(val >= 0){
            if(criterio === 'porcentaje'){
              // Usar segmentación fija para Tasa de uso
              intensity = getPorcentajeIntensity(val);
              color = getTurquoiseColor(intensity);
            } else {
              // Segmentación normal para otros criterios
              const maxVal = computedStats.max || 0;
              if(maxVal > 0 && val > 0){
                intensity = Math.min(1, val / maxVal);
                color = getTurquoiseColor(intensity);
              }
            }
          }
          
          const newStyle = {
            fillColor: color,
            color: '#ffffff',
            weight: incluirBarrios ? 0.8 : 1.6,
            fillOpacity: opacity,
            dashArray: '0'
          };
          layer.setStyle(newStyle);
        }
      });
    }
  }, [criterio, computedStats, incluirBarrios, opacity, geojson]);

  const onEachFeature = (feature, layer) => {
    const p = feature.properties || {};
    const nombre = getNameFromProps(p);
    const poblacion = Number(p.POBLACION || p.poblacion || 0);
    const promedioPasajerosDiario = Number(p.promedio_pasajeros_diario || 0);
    const promedioBusesDiario = Number(p.promedio_buses_diario || 0);
    const cantidadValidaciones = Number(p.cantidad_validaciones || 0);
    const cantidadPasajeros = Number(p.cantidad_pasajeros || 0);
    const cantidadBuses = Number(p.cantidad_buses || 0);
    const popupHtml = `
      <div style="min-width:180px">
        <b>${nombre}</b><br/>
        <b>📊 DEMANDA:</b><br>
        <b>Validaciones:</b> ${cantidadValidaciones.toLocaleString()}<br/>
        <b>Pasajeros:</b> ${cantidadPasajeros.toLocaleString()}${promedioPasajerosDiario > 0 ? ` / Prom. diario: ${promedioPasajerosDiario.toLocaleString('es-PY', {minimumFractionDigits: 1, maximumFractionDigits: 1})}` : ''}<br/>
        ${poblacion > 0 ? `<b>Población:</b> ${poblacion.toLocaleString()}<br/>` : ''}
        <b>🚌 OFERTA:</b><br>
        <b>Buses:</b> ${cantidadBuses.toLocaleString()}${promedioBusesDiario > 0 ? ` / Prom. diario: ${promedioBusesDiario.toLocaleString('es-PY', {minimumFractionDigits: 1, maximumFractionDigits: 1})}` : ''}<br/>
        ${false ? `
        <b>Empresas:</b> ${Number(p.num_empresas || 0).toLocaleString()}<br/>
        <b>Líneas:</b> ${Number(p.num_lineas || 0).toLocaleString()}
        ` : ''}
        <br/>
        <b>Fuentes:</b><br/>
        ${poblacion > 0 ? 'INE. Censo Nacional de Población y Viviendas, 2022.<br/>' : ''}
        SNBE. Sistema Nacional de Billetaje electrónico<br/>
      </div>
    `;
    // Bind popup (still available on click) but also show on hover
    layer.bindPopup(popupHtml, {closeButton: true, offset: [0, -10]});

    // Guardar el estilo original calculado
    const originalStyle = styleFeature(feature);
    layer._originalStyle = originalStyle;

    layer.on({
      mouseover: (e) => {
        e.target.openPopup();
        // Obtener las propiedades actuales del estilo renderizado
        const currentOptions = e.target.options || {};
        // IMPORTANTE: Preservar explícitamente fillColor y fillOpacity
        // Solo actualizar las propiedades del borde
        const newStyle = {
          fillColor: currentOptions.fillColor || originalStyle.fillColor,
          fillOpacity: currentOptions.fillOpacity !== undefined ? currentOptions.fillOpacity : originalStyle.fillOpacity,
          weight: 4,
          color: '#ff0000',
          dashArray: currentOptions.dashArray || originalStyle.dashArray || '0'
        };
        e.target.setStyle(newStyle);
        // Actualizar también las opciones para que se mantengan
        Object.assign(e.target.options, newStyle);
        // bring to front for visibility
        try { 
          if (e.target.bringToFront) {
            e.target.bringToFront(); 
        }
        } catch(err){}
      },
      mouseout: (e) => {
        e.target.closePopup();
        // Solo restaurar las propiedades del borde, NO tocar el interior
        const currentOptions = e.target.options || {};
        const original = e.target._originalStyle || originalStyle;
        // Solo cambiar las propiedades del borde, mantener fillColor y fillOpacity actuales
        e.target.setStyle({
          fillColor: currentOptions.fillColor || original.fillColor,
          fillOpacity: currentOptions.fillOpacity !== undefined ? currentOptions.fillOpacity : original.fillOpacity,
          weight: original.weight,
          color: original.color,
          dashArray: original.dashArray || '0'
        });
        // Actualizar también las opciones
        Object.assign(e.target.options, {
          fillColor: currentOptions.fillColor || original.fillColor,
          fillOpacity: currentOptions.fillOpacity !== undefined ? currentOptions.fillOpacity : original.fillOpacity,
          weight: original.weight,
          color: original.color,
          dashArray: original.dashArray || '0'
        });
      }
    });
  };

  // Estados para ordenamiento y filtros
  const [sortColumn, setSortColumn] = useState('validaciones');
  const [sortDirection, setSortDirection] = useState('desc');
  const [filterText, setFilterText] = useState('');

  // Build table rows from geojson
  const tableRows = useMemo(() => {
    if (!geojson) return [];
    return geojson.features.map(f => {
      const p = f.properties || {};
      // Use unique_passengers and unique_buses if available
      const pasajerosUnicos = p.unique_passengers ?? p.cantidad_pasajeros ?? 0;
      const busesUnicos = p.unique_buses ?? p.cantidad_buses ?? 0;
      const poblacion = Number(p.POBLACION || p.poblacion || 0);
      
      // Calcular cantidad de empresas y líneas
      const empresasStr = p.empresas || '';
      const lineasStr = p.lineas || '';
      const empresasList = empresasStr.split(',').map(e => e.trim()).filter(e => e);
      const lineasList = lineasStr.split(',').map(l => l.trim()).filter(l => l);
      const numEmpresas = p.num_empresas ?? empresasList.length;
      const numLineas = p.num_lineas ?? lineasList.length;
      
      // Intentar obtener relaciones empresa-línea desde propiedades
      let empresaLineasDict = {};
      let lineaEmpresasDict = {};
      
      try {
        if (p.empresa_lineas) {
          empresaLineasDict = typeof p.empresa_lineas === 'string' 
            ? JSON.parse(p.empresa_lineas) 
            : p.empresa_lineas;
        }
        if (p.linea_empresas) {
          lineaEmpresasDict = typeof p.linea_empresas === 'string'
            ? JSON.parse(p.linea_empresas)
            : p.linea_empresas;
        }
      } catch (e) {
        console.warn('Error parseando relaciones empresa-línea:', e);
      }
      
      // Crear tooltip para empresas: "Nombre de Empresa. Linea/s: XX, XY, YY, etc..."
      let empresasTooltip = 'Sin empresas';
      if (Object.keys(empresaLineasDict).length > 0) {
        empresasTooltip = Object.keys(empresaLineasDict)
          .sort()
          .map(empresa => {
            const lineas = empresaLineasDict[empresa] || [];
            const lineasStr = lineas.join(', ');
            return `${empresa}. Linea/s: ${lineasStr}`;
          })
          .join('\n');
      } else if (empresasList.length > 0) {
        // Fallback: usar lista simple si no hay relaciones
        empresasTooltip = empresasList.map(e => `• ${e}`).join('\n');
      }
      
      // Crear tooltip para líneas: "XX(Número de Línea). Empresa: tal"
      let lineasTooltip = 'Sin líneas';
      if (Object.keys(lineaEmpresasDict).length > 0) {
        lineasTooltip = Object.keys(lineaEmpresasDict)
          .sort((a, b) => {
            // Ordenar numéricamente si son números, sino alfabéticamente
            const numA = parseInt(a);
            const numB = parseInt(b);
            if (!isNaN(numA) && !isNaN(numB)) {
              return numA - numB;
            }
            return a.localeCompare(b);
          })
          .map(linea => {
            const empresas = lineaEmpresasDict[linea] || [];
            const empresasStr = empresas.join(', ');
            return `${linea}. Empresa: ${empresasStr}`;
          })
          .join('\n');
      } else if (lineasList.length > 0) {
        // Fallback: usar lista simple si no hay relaciones
        lineasTooltip = lineasList.map(l => `• ${l}`).join('\n');
      }
      
      return {
        name: getNameFromProps(p),
        validaciones: Number(p.cantidad_validaciones || 0),
        pasajeros: Number(pasajerosUnicos),
        promedioPasajerosDiario: Number(p.promedio_pasajeros_diario || 0),
        buses: Number(busesUnicos),
        promedioBusesDiario: Number(p.promedio_buses_diario || 0),
        empresas: empresasStr,
        lineas: lineasStr,
        numEmpresas: numEmpresas,
        numLineas: numLineas,
        empresasTooltip: empresasTooltip,
        lineasTooltip: lineasTooltip,
        poblacion: poblacion,
        penetracion: poblacion > 0 ? ((Number(pasajerosUnicos) / poblacion) * 100) : null
      };
    });
  }, [geojson]);

  // Filtrar y ordenar las filas
  const filteredAndSortedRows = useMemo(() => {
    let filtered = tableRows;

    // Aplicar filtro de texto
    if (filterText.trim()) {
      const searchLower = filterText.toLowerCase();
      filtered = filtered.filter(row => 
        row.name.toLowerCase().includes(searchLower) ||
        row.empresas.toLowerCase().includes(searchLower) ||
        row.lineas.toLowerCase().includes(searchLower)
      );
    }

    // Aplicar ordenamiento
    const sorted = [...filtered].sort((a, b) => {
      let aVal = a[sortColumn];
      let bVal = b[sortColumn];

      // Para empresas y líneas, ordenar por cantidad numérica
      if (sortColumn === 'empresas') {
        aVal = a.numEmpresas;
        bVal = b.numEmpresas;
      } else if (sortColumn === 'lineas') {
        aVal = a.numLineas;
        bVal = b.numLineas;
      }

      // Manejar valores nulos/undefined
      if (aVal == null) aVal = '';
      if (bVal == null) bVal = '';

      // Ordenar números
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      }

      // Ordenar strings
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      
      if (sortDirection === 'asc') {
        return aStr < bStr ? -1 : aStr > bStr ? 1 : 0;
      } else {
        return aStr > bStr ? -1 : aStr < bStr ? 1 : 0;
      }
    });

    return sorted;
  }, [tableRows, sortColumn, sortDirection, filterText]);

  // Manejar clic en header de columna para ordenar
  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  // Manejar clic en nombre de la tabla para centrar mapa y mostrar popup
  const handleRowNameClick = (rowName) => {
    if (!geojson) return;
    
    // Buscar el feature que corresponde al nombre
    const feature = geojson.features.find(f => {
      const featureName = getNameFromProps(f.properties);
      return featureName === rowName;
    });
    
    if (feature) {
      setZoomToFeature(feature);
      setCenterMap(prev => prev + 1); // Incrementar para forzar actualización
    }
  };

  // Función para obtener el número de días en un mes
  const getDaysInMonth = (month, year) => {
    return new Date(year, month, 0).getDate();
  };

  // Función para obtener el número de días con datos
  // Priorizar dias_con_datos del backend (ya considera tipo de día de la franja)
  // Si no está disponible, calcular basándose en mes actual vs pasado
  const getDiasConDatos = useMemo(() => {
    // Primero intentar usar el valor del backend (ya considera el tipo de día)
    if (totals && totals.dias_con_datos && typeof totals.dias_con_datos === 'number' && totals.dias_con_datos > 0) {
      return totals.dias_con_datos;
    }
    
    // Fallback: Si es el mes actual, usar solo los días transcurridos hasta hoy
    const ahora = new Date();
    const mesActual = ahora.getMonth() + 1; // getMonth() devuelve 0-11
    const anioActual = ahora.getFullYear();
    
    if (mes === mesActual && anio === anioActual) {
      return ahora.getDate(); // Día actual del mes (ej: si hoy es 5 de diciembre, retorna 5)
    }
    
    // Si es un mes pasado o futuro, usar todos los días del mes (fallback)
    return getDaysInMonth(mes, anio);
  }, [totals, mes, anio]);

  // Usar promedio diario calculado en el backend (suma de totales diarios / días)
  // Si no está disponible, calcular como fallback
  const promedioPasajerosDiarioTotal = useMemo(() => {
    // Priorizar el valor calculado en el backend
    if (totals && totals.promedio_diario_pasajeros !== null && totals.promedio_diario_pasajeros !== undefined) {
      return totals.promedio_diario_pasajeros;
    }
    // Fallback: calcular localmente si no está disponible
    if (!totals || !totals.pasajeros || typeof totals.pasajeros !== 'number') return 0;
    const dias = getDiasConDatos;
    if (dias === 0) return 0;
    return totals.pasajeros / dias;
  }, [totals, getDiasConDatos]);

  // Usar promedio diario calculado en el backend (suma de totales diarios / días)
  // Si no está disponible, calcular como fallback
  const promedioBusesDiarioTotal = useMemo(() => {
    // Priorizar el valor calculado en el backend
    if (totals && totals.promedio_diario_buses !== null && totals.promedio_diario_buses !== undefined) {
      return totals.promedio_diario_buses;
    }
    // Fallback: calcular localmente si no está disponible
    if (!totals || !totals.buses || typeof totals.buses !== 'number') return 0;
    const dias = getDiasConDatos;
    if (dias === 0) return 0;
    return totals.buses / dias;
  }, [totals, getDiasConDatos]);

  // Usar los totales únicos del backend
  const displayedTotals = {
    validaciones: totals?.validaciones ?? '-',
    pasajeros: totals?.pasajeros ?? '-',
    buses: totals?.buses ?? '-',
    desde_cache: totals?.desde_cache ? 'Sí' : 'No',
    promedioPasajerosDiario: promedioPasajerosDiarioTotal,
    promedioBusesDiario: promedioBusesDiarioTotal
  };

  // Función para generar y descargar PDF
  const downloadPDF = async () => {
    if (!geojson || !filteredAndSortedRows.length) {
      alert('No hay datos para exportar. Por favor, obtén los datos primero.');
      return;
    }

    try {
      // Obtener la franja seleccionada para mostrar en el PDF
      const franjaSeleccionada = franjas.find(f => f.id_franja === idFranja);
      const franjaNombre = franjaSeleccionada 
        ? `${franjaSeleccionada.denominacion} (${franjaSeleccionada.hora_inicio.substring(0,5)} - ${franjaSeleccionada.hora_fin.substring(0,5)}) - ${franjaSeleccionada.tipo_dia_descripcion}`
        : 'No seleccionada';
      
      const nombreMes = meses[mes - 1];
      const tipoArea = incluirBarrios ? 'Barrios' : 'Distritos';

      // Crear nuevo documento PDF
      const pdf = new jsPDF('l', 'mm', 'a4'); // landscape, milímetros, A4
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 10;
      const maxWidth = pageWidth - (margin * 2);

      let yPosition = margin;

      // Título principal
      pdf.setFontSize(18);
      pdf.setFont(undefined, 'bold');
      pdf.text('Análisis de Validaciones', margin, yPosition);
      yPosition += 10;

      // Información del reporte
      pdf.setFontSize(11);
      pdf.setFont(undefined, 'normal');
      pdf.text(`Mes: ${nombreMes} ${anio}`, margin, yPosition);
      yPosition += 6;
      pdf.text(`Franja Operativa: ${franjaNombre}`, margin, yPosition);
      yPosition += 6;
      pdf.text(`Área: ${tipoArea}`, margin, yPosition);
      yPosition += 6;
      pdf.text(`Criterio: ${criterio === 'validaciones' ? 'Validaciones' : criterio === 'porcentaje' ? 'Tasa de uso' : criterio === 'buses' ? 'Buses' : criterio === 'empresas' ? 'Empresas' : 'Líneas'}`, margin, yPosition);
      yPosition += 6;

      // Totales
      pdf.setFont(undefined, 'bold');
      pdf.text('Totales:', margin, yPosition);
      yPosition += 6;
      pdf.setFont(undefined, 'normal');
      pdf.text(`Validaciones: ${typeof displayedTotals.validaciones === 'number' ? displayedTotals.validaciones.toLocaleString() : displayedTotals.validaciones}`, margin + 5, yPosition);
      yPosition += 5;
      const pasajerosText = typeof displayedTotals.pasajeros === 'number' ? displayedTotals.pasajeros.toLocaleString() : displayedTotals.pasajeros;
      const promDiarioPasajerosText = typeof displayedTotals.promedioPasajerosDiario === 'number' && displayedTotals.promedioPasajerosDiario > 0 ? ` / Prom. diario: ${displayedTotals.promedioPasajerosDiario.toFixed(1)}` : '';
      pdf.text(`Pasajeros: ${pasajerosText}${promDiarioPasajerosText}`, margin + 5, yPosition);
      yPosition += 5;
      const busesText = typeof displayedTotals.buses === 'number' ? displayedTotals.buses.toLocaleString() : displayedTotals.buses;
      const promDiarioBusesText = typeof displayedTotals.promedioBusesDiario === 'number' && displayedTotals.promedioBusesDiario > 0 ? ` / Prom. diario: ${displayedTotals.promedioBusesDiario.toFixed(1)}` : '';
      pdf.text(`Buses: ${busesText}${promDiarioBusesText}`, margin + 5, yPosition);
      yPosition += 10;

      // Encabezado de la tabla
      pdf.setFontSize(10);
      pdf.setFont(undefined, 'bold');
      pdf.text('Detalle por área', margin, yPosition);
      yPosition += 8;

      // Calcular anchos de columnas
      const colWidths = {
        num: 8,
        nombre: 42,
        validaciones: 20,
        pasajeros: 20,
        promedioPasajerosDiario: 18,
        poblacion: 18,
        buses: 18,
        empresas: 18,
        lineas: 18,
        penetracion: 20
      };
      const startX = margin;
      let currentX = startX;

      // Dibujar encabezado de tabla
      pdf.setFillColor(102, 126, 234); // Color del encabezado
      pdf.rect(currentX, yPosition - 5, colWidths.num, 7, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(8);
      pdf.text('#', currentX + colWidths.num / 2, yPosition - 1, { align: 'center' });
      currentX += colWidths.num;

      pdf.rect(currentX, yPosition - 5, colWidths.nombre, 7, 'F');
      pdf.text('Nombre', currentX + 2, yPosition - 1);
      currentX += colWidths.nombre;

      pdf.rect(currentX, yPosition - 5, colWidths.validaciones, 7, 'F');
      pdf.text('Valid.', currentX + colWidths.validaciones / 2, yPosition - 1, { align: 'center' });
      currentX += colWidths.validaciones;

      pdf.rect(currentX, yPosition - 5, colWidths.pasajeros, 7, 'F');
      pdf.text('Pasaj. Ún.', currentX + colWidths.pasajeros / 2, yPosition - 1, { align: 'center' });
      currentX += colWidths.pasajeros;

      pdf.rect(currentX, yPosition - 5, colWidths.promedioPasajerosDiario, 7, 'F');
      pdf.text('Prom. diario', currentX + colWidths.promedioPasajerosDiario / 2, yPosition - 1, { align: 'center' });
      currentX += colWidths.promedioPasajerosDiario;

      pdf.rect(currentX, yPosition - 5, colWidths.poblacion, 7, 'F');
      pdf.text('Población', currentX + colWidths.poblacion / 2, yPosition - 1, { align: 'center' });
      currentX += colWidths.poblacion;

      pdf.rect(currentX, yPosition - 5, colWidths.buses, 7, 'F');
      pdf.text('Buses Ún.', currentX + colWidths.buses / 2, yPosition - 1, { align: 'center' });
      currentX += colWidths.buses;

      // pdf.rect(currentX, yPosition - 5, colWidths.empresas, 7, 'F');
      // pdf.text('Empresas', currentX + colWidths.empresas / 2, yPosition - 1, { align: 'center' });
      // currentX += colWidths.empresas;

      // pdf.rect(currentX, yPosition - 5, colWidths.lineas, 7, 'F');
      // pdf.text('Líneas', currentX + colWidths.lineas / 2, yPosition - 1, { align: 'center' });
      // currentX += colWidths.lineas;

      pdf.rect(currentX, yPosition - 5, colWidths.penetracion, 7, 'F');
      pdf.text('Tasa uso (%)', currentX + colWidths.penetracion / 2, yPosition - 1, { align: 'center' });

      yPosition += 5;
      pdf.setTextColor(0, 0, 0);
      pdf.setFont(undefined, 'normal');
      pdf.setFontSize(7);

      // Filas de datos
      filteredAndSortedRows.forEach((row, index) => {
        // Verificar si necesitamos una nueva página
        if (yPosition > pageHeight - 20) {
          pdf.addPage();
          yPosition = margin;
          // Redibujar encabezado en nueva página
          currentX = startX;
          pdf.setFillColor(102, 126, 234);
          pdf.setTextColor(255, 255, 255);
          pdf.setFont(undefined, 'bold');
          pdf.setFontSize(8);
          
          pdf.rect(currentX, yPosition - 5, colWidths.num, 7, 'F');
          pdf.text('#', currentX + colWidths.num / 2, yPosition - 1, { align: 'center' });
          currentX += colWidths.num;
          pdf.rect(currentX, yPosition - 5, colWidths.nombre, 7, 'F');
          pdf.text('Nombre', currentX + 2, yPosition - 1);
          currentX += colWidths.nombre;
          pdf.rect(currentX, yPosition - 5, colWidths.validaciones, 7, 'F');
          pdf.text('Valid.', currentX + colWidths.validaciones / 2, yPosition - 1, { align: 'center' });
          currentX += colWidths.validaciones;
          pdf.rect(currentX, yPosition - 5, colWidths.pasajeros, 7, 'F');
          pdf.text('Pasaj. Ún.', currentX + colWidths.pasajeros / 2, yPosition - 1, { align: 'center' });
          currentX += colWidths.pasajeros;
          pdf.rect(currentX, yPosition - 5, colWidths.promedioPasajerosDiario, 7, 'F');
          pdf.text('Prom. diario', currentX + colWidths.promedioPasajerosDiario / 2, yPosition - 1, { align: 'center' });
          currentX += colWidths.promedioPasajerosDiario;
          pdf.rect(currentX, yPosition - 5, colWidths.poblacion, 7, 'F');
          pdf.text('Población', currentX + colWidths.poblacion / 2, yPosition - 1, { align: 'center' });
          currentX += colWidths.poblacion;
          pdf.rect(currentX, yPosition - 5, colWidths.buses, 7, 'F');
          pdf.text('Buses Ún.', currentX + colWidths.buses / 2, yPosition - 1, { align: 'center' });
          currentX += colWidths.buses;
          // pdf.rect(currentX, yPosition - 5, colWidths.empresas, 7, 'F');
          // pdf.text('Empresas', currentX + colWidths.empresas / 2, yPosition - 1, { align: 'center' });
          // currentX += colWidths.empresas;
          // pdf.rect(currentX, yPosition - 5, colWidths.lineas, 7, 'F');
          // pdf.text('Líneas', currentX + colWidths.lineas / 2, yPosition - 1, { align: 'center' });
          // currentX += colWidths.lineas;
          pdf.rect(currentX, yPosition - 5, colWidths.penetracion, 7, 'F');
          pdf.text('Tasa uso (%)', currentX + colWidths.penetracion / 2, yPosition - 1, { align: 'center' });
          yPosition += 5;
          pdf.setTextColor(0, 0, 0);
          pdf.setFont(undefined, 'normal');
          pdf.setFontSize(7);
        }

        // Alternar color de fondo para filas
        if (index % 2 === 0) {
          pdf.setFillColor(248, 249, 255);
          pdf.rect(startX, yPosition - 4, pageWidth - (margin * 2), 5, 'F');
        }

        currentX = startX;
        
        // Número
        pdf.text(String(index + 1), currentX + colWidths.num / 2, yPosition, { align: 'center' });
        currentX += colWidths.num;

        // Nombre (puede necesitar truncar)
        const nombre = row.name.length > 35 ? row.name.substring(0, 32) + '...' : row.name;
        pdf.text(nombre, currentX + 1, yPosition);
        currentX += colWidths.nombre;

        // Validaciones
        pdf.text(row.validaciones.toLocaleString(), currentX + colWidths.validaciones / 2, yPosition, { align: 'right' });
        currentX += colWidths.validaciones;

        // Pasajeros únicos
        pdf.text(row.pasajeros.toLocaleString(), currentX + colWidths.pasajeros / 2, yPosition, { align: 'right' });
        currentX += colWidths.pasajeros;

        // Promedio diario pasajeros
        const promedioPasajeros = row.promedioPasajerosDiario > 0 ? row.promedioPasajerosDiario.toFixed(1) : '-';
        pdf.text(promedioPasajeros, currentX + colWidths.promedioPasajerosDiario / 2, yPosition, { align: 'right' });
        currentX += colWidths.promedioPasajerosDiario;

        // Población
        const poblacion = row.poblacion > 0 ? row.poblacion.toLocaleString() : '-';
        pdf.text(poblacion, currentX + colWidths.poblacion / 2, yPosition, { align: 'right' });
        currentX += colWidths.poblacion;

        // Buses
        pdf.text(row.buses.toLocaleString(), currentX + colWidths.buses / 2, yPosition, { align: 'right' });
        currentX += colWidths.buses;

        // // Empresas
        // pdf.text(String(row.numEmpresas > 0 ? row.numEmpresas : '-'), currentX + colWidths.empresas / 2, yPosition, { align: 'center' });
        // currentX += colWidths.empresas;

        // // Líneas
        // pdf.text(String(row.numLineas > 0 ? row.numLineas : '-'), currentX + colWidths.lineas / 2, yPosition, { align: 'center' });
        // currentX += colWidths.lineas;

        // Tasa de uso
        const penetracion = row.penetracion !== null ? row.penetracion.toFixed(1) : '-';
        pdf.text(penetracion, currentX + colWidths.penetracion / 2, yPosition, { align: 'right' });

        yPosition += 5;
      });

      // Pie de página
      const totalPages = pdf.internal.pages.length - 1;
      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i);
        pdf.setFontSize(8);
        pdf.setTextColor(128, 128, 128);
        pdf.text(
          `Página ${i} de ${totalPages} - Generado el ${new Date().toLocaleString('es-ES')}`,
          pageWidth / 2,
          pageHeight - 5,
          { align: 'center' }
        );
      }

      // Generar nombre del archivo
      const nombreArchivo = `Validaciones_${nombreMes}_${anio}_${tipoArea}.pdf`;
      pdf.save(nombreArchivo);

    } catch (error) {
      console.error('Error al generar PDF:', error);
      alert('Error al generar el PDF. Por favor, intenta nuevamente.');
    }
  };  

  return (
    <div className="app-container">
      <header className="topbar card" ref={headerRef}>
        <h2>Análisis de Validaciones</h2>
        <div className="controls">
          <select value={mes} onChange={e=>setMes(Number(e.target.value))}>
            {meses.map((nombre, i) => (
              <option key={i+1} value={i+1}>{nombre}</option>
            ))}
          </select>

          <select value={anio} onChange={e=>setAnio(Number(e.target.value))}>
            {[2025,2024,2023,2022].map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <select 
            value={idFranja || ''} 
            onChange={e=>setIdFranja(Number(e.target.value))} 
            disabled={franjas.length === 0}
          >
            {franjas.length === 0 ? (
              <option value="">Cargando franjas...</option>
            ) : (
              franjas.map((franja) => {
                const horaInicio = franja.hora_inicio.substring(0, 5);
                const horaFin = franja.hora_fin.substring(0, 5);
                return (
                  <option key={franja.id_franja} value={franja.id_franja}>
                    {franja.denominacion} ({horaInicio} - {horaFin}) - {franja.tipo_dia_descripcion}
                  </option>
                );
              })
            )}
          </select>

          <label className="control-checkbox">
            <input type="checkbox" checked={incluirBarrios} onChange={e=>setIncluirBarrios(e.target.checked)} /> Incluir Barrios
          </label>

          <button className="btn" onClick={fetchData} disabled={loading}>{loading ? 'Cargando...' : 'Obtener Datos'}</button>

          <label className="control-criterio">
            Criterio:
            <select value={criterio} onChange={e=>setCriterio(e.target.value)}>
              <option value="validaciones">Validaciones</option>
              <option value="porcentaje">Tasa de uso</option>
              <option value="buses">Buses</option>
              {/* <option value="empresas">Empresas</option>
              <option value="lineas">Líneas</option> */}
            </select>
          </label>

          <label className="control-criterio">
            Vista:
            <select value={mapLayer} onChange={e=>setMapLayer(e.target.value)}>
              <option value="street">Calle</option>
              <option value="satellite">Satelital</option>
            </select>
          </label>
        </div>
      </header>

      <main className="content">
        <section className="map-area card">
          {geojson ? (
            <MapContainer center={[-25.3, -57.6]} zoom={11} className="responsive-map" style={{borderRadius:8}}>
              <TileLayer 
                url={mapLayers[mapLayer].url}
                attribution={mapLayers[mapLayer].attribution}
              />
              <MapController centerMap={centerMap} zoomToFeature={zoomToFeature} geoJsonLayerRef={geoJsonLayerRef} />
              <GeoJSON 
                key={`geojson-${geojsonKey}-${idFranja}`}
                ref={geoJsonLayerRef}
                data={geojson} 
                style={styleFeature} 
                onEachFeature={onEachFeature}
              />
            </MapContainer>
          ) : (
            <div className="map-placeholder">Mapa sin datos. Haz clic en "Obtener Datos".</div>
          )}
        </section>

        <aside className="sidebar">
          <Legend min={computedStats.min} max={computedStats.max} criterio={criterio} />
          <div className="card totals">
            <h3>Totales del sistema en el periodo y franja seleccionada {displayedTotals.desde_cache === 'Sí' ? <small>(cache)</small> : null}</h3>
            <div><b>Validaciones:</b> {typeof displayedTotals.validaciones === 'number' ? displayedTotals.validaciones.toLocaleString('es-PY') : displayedTotals.validaciones}</div>
            <div><b>Pasajeros:</b> {typeof displayedTotals.pasajeros === 'number' ? displayedTotals.pasajeros.toLocaleString('es-PY') : displayedTotals.pasajeros}{typeof displayedTotals.promedioPasajerosDiario === 'number' && displayedTotals.promedioPasajerosDiario > 0 ? ` / Prom. diario: ${displayedTotals.promedioPasajerosDiario.toLocaleString('es-PY', {minimumFractionDigits: 1, maximumFractionDigits: 1})}` : ''}</div>
            <div><b>Buses:</b> {typeof displayedTotals.buses === 'number' ? displayedTotals.buses.toLocaleString('es-PY') : displayedTotals.buses}{typeof displayedTotals.promedioBusesDiario === 'number' && displayedTotals.promedioBusesDiario > 0 ? ` / Prom. diario: ${displayedTotals.promedioBusesDiario.toLocaleString('es-PY', {minimumFractionDigits: 1, maximumFractionDigits: 1})}` : ''}</div>
            
            <div style={{marginTop: '15px', paddingTop: '15px', borderTop: '1px solid rgba(0,0,0,0.1)'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
                <label htmlFor="opacity-slider" style={{fontSize: '13px', fontWeight: '600', color: '#555'}}>
                  <b>Transparencia:</b>
                </label>
                <span style={{fontSize: '13px', color: '#666', fontWeight: '500'}}>
                  {Math.round(opacity * 100)}%
                </span>
              </div>
              <input
                id="opacity-slider"
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={opacity}
                onChange={(e) => setOpacity(parseFloat(e.target.value))}
                    style={{
                    width: '100%',
                    height: '6px',
                    borderRadius: '3px',
                    background: '#ddd',
                    outline: 'none',
                    cursor: 'pointer',
                    WebkitAppearance: 'none',
                    appearance: 'none'
                  }}
                  className="opacity-slider"
              />
            </div>
          </div>
          <div className="card" style={{textAlign: 'center', padding: '15px'}}>
            <img 
              src={getStaticUrl('/MINISTERIO-DE-OBRAS-PUBLICAS-Curvas-01-transparente.png')}
              alt="Ministerio de Obras Públicas y Comunicaciones" 
              style={{
                maxWidth: '100%',
                width: 'auto',
                maxHeight: '120px',
                height: 'auto',
                display: 'block',
                margin: '0 auto 15px auto',
                objectFit: 'contain'
              }}
            />
            <div 
              style={{
                textAlign: 'left', 
                paddingTop: '15px',
                fontSize: '0.85em',
                cursor: 'pointer',
                color: '#0066cc'
              }}
              onClick={() => setShowIndicadoresModal(true)}
              onMouseEnter={(e) => e.target.style.textDecoration = 'underline'}
              onMouseLeave={(e) => e.target.style.textDecoration = 'none'}
            >
              <h4 style={{marginTop: 0, marginBottom: '10px', fontSize: '1em'}}>Los principales indicadores disponibles son:</h4>
              <div style={{lineHeight: '1.6', fontSize: '0.9em'}}>
                <div><b>📜 Validaciones:</b> demanda mensual en las localidades y franja horaria seleccionada.</div>
                <div><b>🚌 Buses:</b> total de buses distintos y en promedio diario que circulan en las localidades y franjas horarias elegidas.</div>
                <div><b>👥 Pasajeros:</b> tarjetas distintas y promedio diario utilizadas en las localidades y franjas horarias elegidas.</div>
                <div><b>🏡 Población:</b> datos del INE por zona.</div>
                <div><b>📊 Tasa de uso:</b> relación pasajeros / población.</div>
              </div>
            </div>
            
            {/* Modal de Indicadores */}
            {showIndicadoresModal && (
              <div 
                style={{
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  backgroundColor: 'rgba(0, 0, 0, 0.5)',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  zIndex: 10000
                }}
                onClick={() => setShowIndicadoresModal(false)}
              >
                <div 
                  style={{
                    backgroundColor: 'white',
                    padding: '30px',
                    borderRadius: '8px',
                    maxWidth: '600px',
                    width: '90%',
                    maxHeight: '80vh',
                    overflow: 'auto',
                    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                    <h3 style={{margin: 0, fontSize: '1.5em'}}>Los principales indicadores disponibles son:</h3>
                    <button
                      onClick={() => setShowIndicadoresModal(false)}
                      style={{
                        background: 'none',
                        border: 'none',
                        fontSize: '24px',
                        cursor: 'pointer',
                        color: '#666',
                        padding: '0',
                        width: '30px',
                        height: '30px'
                      }}
                    >
                      ×
                    </button>
                  </div>
                  <div style={{lineHeight: '2', fontSize: '1.1em'}}>
                    <div style={{marginBottom: '15px'}}><b>📜 Validaciones:</b> demanda mensual en las localidades y franja horaria seleccionada.</div>
                    <div style={{marginBottom: '15px'}}><b>🚌 Buses:</b> total de buses distintos y en promedio diario que circulan en las localidades y franjas horarias elegidas.</div>
                    <div style={{marginBottom: '15px'}}><b>👥 Pasajeros:</b> tarjetas distintas y promedio diario utilizadas en las localidades y franjas horarias elegidas.</div>
                    <div style={{marginBottom: '15px'}}><b>🏡 Población:</b> datos del INE por zona.</div>
                    <div style={{marginBottom: '15px'}}><b>📊 Tasa de uso:</b> relación pasajeros / población.</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </aside>
      </main>

      <section className="table-section card">
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}>
          <h3 style={{margin: 0}}>Detalle por área</h3>
          {filteredAndSortedRows.length > 0 && (
            <button
              onClick={downloadPDF}
              style={{
                padding: '8px 16px',
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'all 0.3s'
              }}
              onMouseOver={(e) => e.target.style.backgroundColor = '#c82333'}
              onMouseOut={(e) => e.target.style.backgroundColor = '#dc3545'}
            >
              📄 Descargar PDF
            </button>
          )}
        </div>
        <div style={{marginBottom: '10px'}}>
          <input
            type="text"
            placeholder="Buscar por nombre, empresa o línea..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid rgba(0,0,0,0.1)',
              borderRadius: '6px',
              fontSize: '14px'
            }}
          />
        </div>
        <div className="table-wrapper" ref={tableRef}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{cursor: 'default'}}>#</th>
                <th className="sortable" onClick={() => handleSort('name')} title="Clic para ordenar">
                  Nombre {sortColumn === 'name' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'name' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('validaciones')} title="Clic para ordenar">
                  Validaciones {sortColumn === 'validaciones' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'validaciones' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('pasajeros')} title="Clic para ordenar">
                  Pasajeros {sortColumn === 'pasajeros' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'pasajeros' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('promedioPasajerosDiario')} title="Clic para ordenar">
                  Prom. diario {sortColumn === 'promedioPasajerosDiario' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'promedioPasajerosDiario' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('poblacion')} title="Clic para ordenar">
                  Población {sortColumn === 'poblacion' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'poblacion' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('buses')} title="Clic para ordenar">
                  Buses {sortColumn === 'buses' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'buses' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('promedioBusesDiario')} title="Clic para ordenar">
                  Prom. diario (buses) {sortColumn === 'promedioBusesDiario' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'promedioBusesDiario' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                {/* <th className="sortable" onClick={() => handleSort('empresas')} title="Clic para ordenar">
                  Empresas {sortColumn === 'empresas' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'empresas' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
                <th className="sortable" onClick={() => handleSort('lineas')} title="Clic para ordenar">
                  Líneas {sortColumn === 'lineas' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'lineas' && <span style={{opacity: 0.3}}> ↕</span>}
                </th> */}
                <th className="sortable" onClick={() => handleSort('penetracion')} title="Clic para ordenar">
                  Tasa de uso {sortColumn === 'penetracion' && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                  {sortColumn !== 'penetracion' && <span style={{opacity: 0.3}}> ↕</span>}
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedRows.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{textAlign: 'center', padding: '20px', color: '#999'}}>
                    No se encontraron resultados
                  </td>
                </tr>
              ) : (
                filteredAndSortedRows.map((r,i) => (
                <tr key={i}>
                  <td>{i+1}</td>
                  <td 
                    className="nowrap clickable-name"
                    onClick={() => handleRowNameClick(r.name)}
                    title="Clic para centrar en el mapa y mostrar detalles"
                  >
                    {r.name}
                  </td>
                  <td>{r.validaciones.toLocaleString()}</td>
                  <td>{r.pasajeros.toLocaleString()}</td>
                  <td>{r.promedioPasajerosDiario > 0 ? r.promedioPasajerosDiario.toFixed(1) : '-'}</td>
                    <td>{r.poblacion > 0 ? r.poblacion.toLocaleString() : '-'}</td>
                  <td>{r.buses.toLocaleString()}</td>
                  <td>{r.promedioBusesDiario > 0 ? r.promedioBusesDiario.toFixed(1) : '-'}</td>
                    {/* <td 
                      className="nowrap" 
                      style={{cursor: r.numEmpresas > 0 ? 'help' : 'default'}}
                      title={r.empresasTooltip}
                    >
                      {r.numEmpresas > 0 ? r.numEmpresas : '-'}
                    </td>
                    <td 
                      className="nowrap" 
                      style={{cursor: r.numLineas > 0 ? 'help' : 'default'}}
                      title={r.lineasTooltip}
                    >
                      {r.numLineas > 0 ? r.numLineas : '-'}
                    </td> */}
                  <td>{r.penetracion !== null ? r.penetracion.toFixed(1) : '-'}</td>
                </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {filteredAndSortedRows.length > 0 && (
          <div style={{marginTop: '8px', fontSize: '12px', color: '#666'}}>
            Mostrando {filteredAndSortedRows.length} de {tableRows.length} áreas
          </div>
        )}
      </section>
      
      <footer className="app-footer">
        <div className="footer-left">
          <img 
            src={getStaticUrl('/MINISTERIO-DE-OBRAS-PUBLICAS-Curvas-01-transparente.png')}
            alt="Ministerio de Obras Públicas y Comunicaciones" 
            className="footer-logo-ministerio"
          />
        </div>
        <div className="footer-center">
          <div className="footer-copyright">
            © {new Date().getFullYear()} Copyright
          </div>
          <div className="footer-dev">
            Desarrollado por equipo CID-DMT-VMT
          </div>
        </div>
        <div className="footer-right">
          <div className="footer-logos-stacked">
            <img 
              src={getStaticUrl('/Logo_CIDSA2.jpg')}
              alt="CIDSA Logo" 
              className="footer-logo-cidsa"
            />
          </div>
        </div>
      </footer>
    </div>
  );
}