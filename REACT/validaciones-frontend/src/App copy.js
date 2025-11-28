// src/App.js
import React, { useState, useMemo, useRef, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';

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

function Legend({min, max, criterio}){
  if(max === 0 && min === 0) return null;
  const steps = 5;
  const step = (max - min) / steps || 0;
  const buckets = [];
  for(let i=0;i<steps;i++){
    const inicio = min + i*step;
    const fin = (i === steps-1) ? max : min + (i+1)*step;
    const intensity = (i+1)/steps;
    buckets.push({
      label: criterio === 'porcentaje' ? `${inicio.toFixed(1)}% - ${fin.toFixed(1)}%` : `${Math.round(inicio).toLocaleString()} - ${Math.round(fin).toLocaleString()}`,
      color: getTurquoiseColor(intensity)
    });
  }
  const title = criterio === 'validaciones' ? 'Validaciones' : criterio === 'porcentaje' ? 'Penetración (%)' : criterio === 'buses' ? 'Buses' : criterio === 'empresas' ? 'Empresas' : 'Líneas';
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
  const [horario, setHorario] = useState('manana');
  const [incluirBarrios, setIncluirBarrios] = useState(false);
  const [totals, setTotals] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
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
    setLoading(true);
    try {
      const res = await axios.post('/api/validaciones', {
        mes, anio, horario_pico: horario, incluir_barrios: incluirBarrios
      });
      if(res.data.error){
        alert(res.data.error);
      } else {
        setGeojson(res.data.geojson);
        setTotals({
          ...res.data.totals,
          // Ensure we're using the unique counts from the backend
          pasajeros: res.data.totals.unique_passengers ?? res.data.totals.pasajeros,
          buses: res.data.totals.unique_buses ?? res.data.totals.buses
        });
        setStats(res.data.stats || null);
      }
    } catch (err) {
      console.error(err);
      alert('Error al obtener datos: ' + (err.message || err));
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
    const maxVal = computedStats.max || 0;
    if(maxVal > 0 && val > 0){
      const intensity = Math.min(1, val / maxVal);
      color = getTurquoiseColor(intensity);
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

  // Actualizar estilos cuando cambia el criterio u opacidad
  useEffect(() => {
    if (geoJsonLayerRef.current && geojson) {
      geoJsonLayerRef.current.eachLayer((layer) => {
        const feature = layer.feature;
        if (feature) {
          // Recalcular estilo basado en el criterio actual
          const val = getFeatureValue(feature, criterio);
          let color = '#f0f0f0';
          const maxVal = computedStats.max || 0;
          if(maxVal > 0 && val > 0){
            const intensity = Math.min(1, val / maxVal);
            color = getTurquoiseColor(intensity);
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
    const popupHtml = `
      <div style="min-width:180px">
        <b>${nombre}</b><br/>
        <b>📊 DEMANDA:</b><br>
        <b>Validaciones:</b> ${p.cantidad_validaciones || 0}<br/>
        <b>Pasajeros únicos:</b> ${p.cantidad_pasajeros || 0}<br/>
        ${poblacion > 0 ? `<b>Población:</b> ${poblacion.toLocaleString()}<br/>` : ''}
        <b>🚌 OFERTA:</b><br>
        <b>Buses únicos:</b> ${p.cantidad_buses || 0}<br/>
        <b>Empresas:</b> ${p.num_empresas || 0}<br/>
        <b>Líneas:</b> ${p.num_lineas || 0}
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
      
      // Crear tooltips con viñetas
      const empresasTooltip = empresasList.length > 0 
        ? empresasList.map(e => `• ${e}`).join('\n')
        : 'Sin empresas';
      const lineasTooltip = lineasList.length > 0
        ? lineasList.map(l => `• ${l}`).join('\n')
        : 'Sin líneas';
      
      return {
        name: getNameFromProps(p),
        validaciones: Number(p.cantidad_validaciones || 0),
        pasajeros: Number(pasajerosUnicos),
        buses: Number(busesUnicos),
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

  // Usar los totales únicos del backend
  const displayedTotals = {
    validaciones: totals?.validaciones ?? '-',
    pasajeros: totals?.pasajeros ?? '-',
    buses: totals?.buses ?? '-',
    desde_cache: totals?.desde_cache ? 'Sí' : 'No'
  };  

  return (
    <div className="app-container">
      <header className="topbar card">
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

          <select value={horario} onChange={e=>setHorario(e.target.value)}>
            <option value="manana">Mañana 5:00-7:59</option>
            <option value="tarde">Tarde 16:00-18:59</option>
          </select>

          <label className="control-checkbox">
            <input type="checkbox" checked={incluirBarrios} onChange={e=>setIncluirBarrios(e.target.checked)} /> Incluir Barrios
          </label>

          <button className="btn" onClick={fetchData} disabled={loading}>{loading ? 'Cargando...' : 'Obtener Datos'}</button>

          <label className="control-criterio">
            Criterio:
            <select value={criterio} onChange={e=>setCriterio(e.target.value)}>
              <option value="validaciones">Validaciones</option>
              <option value="porcentaje">Penetración (%)</option>
              <option value="buses">Buses</option>
              <option value="empresas">Empresas</option>
              <option value="lineas">Líneas</option>
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
            <MapContainer center={[-25.3, -57.6]} zoom={11} style={{height:'620px', borderRadius:8}}>
              <TileLayer 
                url={mapLayers[mapLayer].url}
                attribution={mapLayers[mapLayer].attribution}
              />
              <GeoJSON 
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
            <h3>Totales {displayedTotals.desde_cache === 'Sí' ? <small>(cache)</small> : null}</h3>
            <div><b>Validaciones:</b> {typeof displayedTotals.validaciones === 'number' ? displayedTotals.validaciones.toLocaleString() : displayedTotals.validaciones}</div>
            <div><b>Pasajeros únicos:</b> {typeof displayedTotals.pasajeros === 'number' ? displayedTotals.pasajeros.toLocaleString() : displayedTotals.pasajeros}</div>
            <div><b>Buses únicos:</b> {typeof displayedTotals.buses === 'number' ? displayedTotals.buses.toLocaleString() : displayedTotals.buses}</div>
            
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
              src="/Logo_CIDSA2.jpg" 
              alt="CIDSA Logo" 
              style={{
                maxWidth: '100%',
                height: 'auto',
                display: 'block',
                margin: '0 auto'
              }}
            />
          </div>
        </aside>
      </main>

      <section className="table-section card">
        <h3>Detalle por área</h3>
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
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th className="sortable" onClick={() => handleSort('name')}>
                  Nombre {sortColumn === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('validaciones')}>
                  Validaciones {sortColumn === 'validaciones' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('pasajeros')}>
                  Pasajeros únicos {sortColumn === 'pasajeros' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('poblacion')}>
                  Población {sortColumn === 'poblacion' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('buses')}>
                  Buses únicos {sortColumn === 'buses' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('empresas')}>
                  Empresas {sortColumn === 'empresas' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('lineas')}>
                  Líneas {sortColumn === 'lineas' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="sortable" onClick={() => handleSort('penetracion')}>
                  Penetración (%) {sortColumn === 'penetracion' && (sortDirection === 'asc' ? '↑' : '↓')}
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
                  <td className="nowrap">{r.name}</td>
                  <td>{r.validaciones.toLocaleString()}</td>
                  <td>{r.pasajeros.toLocaleString()}</td>
                    <td>{r.poblacion > 0 ? r.poblacion.toLocaleString() : '-'}</td>
                  <td>{r.buses.toLocaleString()}</td>
                    <td 
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
                    </td>
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
    </div>
  );
}