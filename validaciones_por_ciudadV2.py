import os
import psycopg2
import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
from branca.element import Template, MacroElement
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify
from shapely.geometry import Point
from datetime import datetime, timedelta
import json
import hashlib
import webbrowser
import threading

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', '5432')
}

app = Flask(__name__)

# Variables globales
gdf_distritos = None
gdf_todas_ciudades = None
columna_nombre = None

# Directorio para cache
CACHE_DIR = 'cache_validaciones'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def cargar_todos_los_shapes():
    """Carga los shapefiles específicos de Asunción, Central y Presidente Hayes"""
    gdfs = []
    
    # 1) Cargar Distrito_Asuncion.shp de CIUDADES/ASUNCION
    ruta_asuncion = os.path.join('CIUDADES', 'ASUNCION', 'Distrito_Asuncion.shp')
    if os.path.exists(ruta_asuncion):
        gdf_asuncion = gpd.read_file(ruta_asuncion)
        if gdf_asuncion.crs != 'EPSG:4326':
            gdf_asuncion = gdf_asuncion.to_crs('EPSG:4326')
        gdfs.append(gdf_asuncion)
        print(f"✓ Cargado: {ruta_asuncion} ({len(gdf_asuncion)} distritos)")
    else:
        print(f"✗ No se encontró: {ruta_asuncion}")
    
    # 2) Cargar Distritos_Presidente Hayes.shp de CIUDADES/PRESIDENTE_HAYES
    ruta_hayes = os.path.join('CIUDADES', 'PRESIDENTE_HAYES', 'Distritos_Presidente Hayes.shp')
    if os.path.exists(ruta_hayes):
        gdf_hayes = gpd.read_file(ruta_hayes)
        if gdf_hayes.crs != 'EPSG:4326':
            gdf_hayes = gdf_hayes.to_crs('EPSG:4326')
        gdfs.append(gdf_hayes)
        print(f"✓ Cargado: {ruta_hayes} ({len(gdf_hayes)} distritos)")
    else:
        print(f"✗ No se encontró: {ruta_hayes}")
    
    # 3) Cargar Distritos_Central.shp de CIUDADES/DPTO_CENTRAL
    ruta_central = os.path.join('CIUDADES', 'DPTO_CENTRAL', 'Distritos_Central.shp')
    if os.path.exists(ruta_central):
        gdf_central = gpd.read_file(ruta_central)
        if gdf_central.crs != 'EPSG:4326':
            gdf_central = gdf_central.to_crs('EPSG:4326')
        gdfs.append(gdf_central)
        print(f"✓ Cargado: {ruta_central} ({len(gdf_central)} distritos)")
    else:
        print(f"✗ No se encontró: {ruta_central}")
    
    # Combinar todos los GeoDataFrames
    if gdfs:
        gdf_combinado = pd.concat(gdfs, ignore_index=True)
        print(f"\n✓ Total de distritos cargados: {len(gdf_combinado)}")
        print(f"Columnas disponibles: {gdf_combinado.columns.tolist()}")
        return gdf_combinado
    else:
        raise Exception("No se pudieron cargar los shapefiles")

def cargar_distritos():
    """Carga y combina los shapefiles de distritos de Central, Asunción y Presidente Hayes"""
    gdfs = []
    
    # Cargar distritos de Central
    ruta_central = os.path.join('CIUDADES', 'DPTO_CENTRAL', 'Distritos_Central.shp')
    if os.path.exists(ruta_central):
        gdf_central = gpd.read_file(ruta_central)
        if gdf_central.crs != 'EPSG:4326':
            gdf_central = gdf_central.to_crs('EPSG:4326')
        gdfs.append(gdf_central)
        print(f"✓ Distritos Central cargados: {len(gdf_central)}")
    
    # Cargar distrito de Asunción
    ruta_asuncion = os.path.join('CIUDADES', 'ASUNCION', 'Distrito_Asuncion.shp')
    if os.path.exists(ruta_asuncion):
        gdf_asuncion = gpd.read_file(ruta_asuncion)
        if gdf_asuncion.crs != 'EPSG:4326':
            gdf_asuncion = gdf_asuncion.to_crs('EPSG:4326')
        gdfs.append(gdf_asuncion)
        print(f"✓ Distrito de Asunción cargado: {len(gdf_asuncion)}")
    
    # Cargar distritos de Presidente Hayes
    ruta_hayes = os.path.join('CIUDADES', 'PRESIDENTE_HAYES', 'Distritos_Presidente Hayes.shp')
    if os.path.exists(ruta_hayes):
        gdf_hayes = gpd.read_file(ruta_hayes)
        if gdf_hayes.crs != 'EPSG:4326':
            gdf_hayes = gdf_hayes.to_crs('EPSG:4326')
        gdfs.append(gdf_hayes)
        print(f"✓ Distritos de Presidente Hayes cargados: {len(gdf_hayes)}")
    
    if not gdfs:
        raise Exception("No se pudieron cargar los shapefiles de distritos")
    
    # Combinar todos los distritos
    gdf_combinado = pd.concat(gdfs, ignore_index=True)
    print(f"\n✓ Total de distritos cargados: {len(gdf_combinado)}")
    
    # Usar DIST_DESC_ como columna de nombre
    col_nombre = 'DIST_DESC_'
    
    if col_nombre not in gdf_combinado.columns:
        print(f"Advertencia: Columna {col_nombre} no encontrada")
        print(f"Columnas disponibles: {gdf_combinado.columns.tolist()}")
        # Buscar alternativas
        columnas_posibles = ['NOMBRE', 'nombre', 'Nombre', 'DISTRITO', 'distrito', 'Distrito', 'NAME', 'name']
        for col in columnas_posibles:
            if col in gdf_combinado.columns:
                col_nombre = col
                break
        if col_nombre not in gdf_combinado.columns:
            col_nombre = gdf_combinado.columns[0]
    
    print(f"Usando columna '{col_nombre}' para nombres de distritos")
    
    # Asegurar que los nombres de distritos sean strings
    gdf_combinado[col_nombre] = gdf_combinado[col_nombre].astype(str)
    
    return gdf_combinado, col_nombre

def obtener_cache_key(mes, anio):
    """Genera una clave única para el cache"""
    return f"validaciones_{anio}_{mes:02d}"

#def guardar_cache(mes, anio, gdf_resultado, destinos_probables):
def guardar_cache(mes, anio, gdf_resultado):
    """Guarda los resultados en cache como JSON"""
    cache_key = obtener_cache_key(mes, anio)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    # Convertir GeoDataFrame a formato serializable
    cache_data = {
        'mes': mes,
        'anio': anio,
        'fecha_cache': datetime.now().isoformat(),
        'distritos': []#,
        #'destinos_probables': destinos_probables
    }
    
    for idx, row in gdf_resultado.iterrows():
        cache_data['distritos'].append({
            'nombre': row[columna_nombre],
            'cantidad': int(row['cantidad'])
        })
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Cache guardado: {cache_file}")

def cargar_cache(mes, anio):
    """Carga los resultados desde cache si existe
    
    Returns:
        tuple: (gdf_resultado, desde_cache) donde:
            - gdf_resultado: GeoDataFrame con los datos de validaciones
            - desde_cache: Booleano que indica si se cargó desde caché
    """
    cache_key = obtener_cache_key(mes, anio)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        print(f"✓ Cargando desde cache: {cache_file}")
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Reconstruir GeoDataFrame con los datos del cache
        gdf_resultado = gdf_distritos.copy()
        
        # Crear diccionario de cantidades
        cantidades = {d['nombre']: d['cantidad'] for d in cache_data['distritos']}
        
        # Asignar cantidades al GeoDataFrame
        gdf_resultado['cantidad'] = gdf_resultado[columna_nombre].map(cantidades).fillna(0).astype(int)
        
        return gdf_resultado, True
    
    return None, False

def obtener_validaciones(mes, anio):
    """Obtiene las validaciones en horario pico (5:00 - 7:59) desde PostgreSQL"""
    
    # Calcular fechas de inicio y fin del mes
    if mes == 12:
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio + 1}-01-01"
    else:
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio}-{mes + 1:02d}-01"
    
    # Consulta optimizada
    query = """
    SELECT DISTINCT ON (idsam, consecutivoevento, serialmediopago)
        idsam,
        serialmediopago,
        fechahoraevento,
        entidad,
        latitude,
        longitude,
        idrutaestacion,
        tipotransporte,
        consecutivoevento
    FROM c_transacciones 
    WHERE fechahoraevento >= %s 
        AND fechahoraevento < %s
        AND DATE_PART('hour', fechahoraevento) BETWEEN 5 AND 7
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
    ORDER BY idsam, consecutivoevento, serialmediopago, fechahoraevento
    """
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        df = pd.read_sql_query(query, conn, params=(fecha_inicio, fecha_fin))
        conn.close()
        print(f"Validaciones obtenidas: {len(df)}")
        return df
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# def obtener_destinos_buses(df_validaciones, mes, anio):
#     """Obtiene los destinos probables de los buses una hora después"""
    
#     if df_validaciones is None or len(df_validaciones) == 0:
#         return []
    
#     # Calcular fechas de inicio y fin del mes
#     if mes == 12:
#         fecha_inicio = f"{anio}-{mes:02d}-01"
#         fecha_fin = f"{anio + 1}-01-01"
#     else:
#         fecha_inicio = f"{anio}-{mes:02d}-01"
#         fecha_fin = f"{anio}-{mes + 1:02d}-01"
    
#     # Obtener lista única de buses (idsam) y sus horarios
#     buses_unicos = df_validaciones[['idsam', 'fechahoraevento']].copy()
    
#     # Consulta para obtener validaciones de los mismos buses 1 hora después
#     query = """
#     SELECT 
#         idsam,
#         fechahoraevento,
#         latitude,
#         longitude
#     FROM c_transacciones 
#     WHERE fechahoraevento >= %s 
#         AND fechahoraevento < %s
#         AND idsam = ANY(%s)
#         AND latitude IS NOT NULL
#         AND longitude IS NOT NULL
#     ORDER BY idsam, fechahoraevento
#     """
    
#     try:
#         conn = psycopg2.connect(**DB_CONFIG)
#         lista_buses = df_validaciones['idsam'].unique().tolist()
#         df_destinos = pd.read_sql_query(query, conn, params=(fecha_inicio, fecha_fin, lista_buses))
#         conn.close()
        
#         print(f"Registros de destinos obtenidos: {len(df_destinos)}")
        
#         # Procesar destinos
#         destinos_por_pasajero = []
        
#         for idx, row in df_validaciones.iterrows():
#             idsam = row['idsam']
#             hora_origen = row['fechahoraevento']
            
#             # Buscar validaciones del mismo bus 1 hora después
#             hora_limite_inf = hora_origen + timedelta(hours=1)
#             hora_limite_sup = hora_origen + timedelta(hours=2)
            
#             destinos_bus = df_destinos[
#                 (df_destinos['idsam'] == idsam) &
#                 (df_destinos['fechahoraevento'] >= hora_limite_inf) &
#                 (df_destinos['fechahoraevento'] <= hora_limite_sup)
#             ]
            
#             if len(destinos_bus) > 0:
#                 # Tomar la primera validación después de 1 hora
#                 destino = destinos_bus.iloc[0]
#                 destinos_por_pasajero.append({
#                     'idsam': idsam,
#                     'latitude': destino['latitude'],
#                     'longitude': destino['longitude']
#                 })
        
#         print(f"Destinos encontrados: {len(destinos_por_pasajero)}")
        
#         # Asignar destinos a ciudades
#         if len(destinos_por_pasajero) > 0:
#             df_destinos_pasajeros = pd.DataFrame(destinos_por_pasajero)
#             geometry = [Point(xy) for xy in zip(df_destinos_pasajeros['longitude'], df_destinos_pasajeros['latitude'])]
#             gdf_destinos = gpd.GeoDataFrame(df_destinos_pasajeros, geometry=geometry, crs='EPSG:4326')
            
#             # Realizar spatial join con todas las ciudades
#             destinos_con_ciudad = gpd.sjoin(
#                 gdf_destinos, 
#                 gdf_todas_ciudades, 
#                 how='left', 
#                 predicate='within'
#             )
            
#             # Contar destinos por ciudad
#             if 'DIST_DESC_' in destinos_con_ciudad.columns:
#                 conteo_destinos = destinos_con_ciudad['DIST_DESC_'].value_counts()
#             else:
#                 # Buscar columna alternativa
#                 col_nombre_destino = None
#                 for col in ['NOMBRE', 'nombre', 'NAME', 'name', 'DISTRITO', 'distrito']:
#                     if col in destinos_con_ciudad.columns:
#                         col_nombre_destino = col
#                         break
#                 if col_nombre_destino:
#                     conteo_destinos = destinos_con_ciudad[col_nombre_destino].value_counts()
#                 else:
#                     conteo_destinos = pd.Series()
            
#             # Calcular porcentajes
#             total_destinos = conteo_destinos.sum()
#             destinos_probables = []
            
#             for ciudad, cantidad in conteo_destinos.head(10).items():
#                 if pd.notna(ciudad):
#                     porcentaje = (cantidad / total_destinos * 100) if total_destinos > 0 else 0
#                     destinos_probables.append({
#                         'ciudad': str(ciudad),
#                         'cantidad': int(cantidad),
#                         'porcentaje': round(porcentaje, 2)
#                     })
            
#             return destinos_probables
        
#         return []
        
#     except Exception as e:
#         print(f"Error al obtener destinos: {e}")
#         import traceback
#         print(traceback.format_exc())
#         return []

def asignar_validaciones_a_distritos(df_validaciones, gdf_distritos, col_nombre):
    """Asigna cada validación a su distrito correspondiente"""
    # Crear GeoDataFrame con las validaciones
    geometry = [Point(xy) for xy in zip(df_validaciones['longitude'], df_validaciones['latitude'])]
    gdf_validaciones = gpd.GeoDataFrame(df_validaciones, geometry=geometry, crs='EPSG:4326')
    
    # Realizar spatial join
    validaciones_con_distrito = gpd.sjoin(
        gdf_validaciones, 
        gdf_distritos, 
        how='left', 
        predicate='within'
    )
    
    # Contar validaciones por distrito
    conteo = validaciones_con_distrito.groupby(col_nombre).size().reset_index(name='cantidad')
    
    # Unir con geometrías
    gdf_resultado = gdf_distritos.merge(conteo, on=col_nombre, how='left')
    gdf_resultado['cantidad'] = gdf_resultado['cantidad'].fillna(0).astype(int)
    
    return gdf_resultado

def crear_leyenda_mapa_calor(min_val, max_val):
    """Crea una leyenda de mapa de calor personalizada"""
    
    # Calcular rangos
    rango = max_val - min_val
    if rango == 0:
        rangos = [(min_val, min_val, '#cccccc')]
    else:
        step = rango / 4
        rangos = [
            (min_val, min_val + step, '#00ff00'),
            (min_val + step, min_val + 2*step, '#7fff00'),
            (min_val + 2*step, min_val + 3*step, '#ffff00'),
            (min_val + 3*step, max_val, '#ff0000')
        ]
    
    leyenda_html = """
    <div style="position: fixed; 
                bottom: 50px; right: 50px; 
                width: 200px; 
                background-color: white; 
                border: 2px solid grey; 
                border-radius: 10px;
                z-index: 9999; 
                font-size: 14px;
                padding: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <p style="margin: 0 0 10px 0; font-weight: bold; text-align: center;">
            Validaciones
        </p>
    """
    
    for i, (inicio, fin, color) in enumerate(rangos):
        leyenda_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="width: 30px; height: 20px; background-color: {color}; 
                        border: 1px solid black; margin-right: 10px;"></div>
            <span>{int(inicio):,} - {int(fin):,}</span>
        </div>
        """
    
    leyenda_html += "</div>"
    
    return leyenda_html

# def crear_cuadro_destinos(destinos_probables):
#     """Crea el cuadro de destinos probables"""
    
#     if not destinos_probables or len(destinos_probables) == 0:
#         return """
#         <div style="position: fixed; 
#                     top: 20px; right: 20px; 
#                     width: 300px; 
#                     background-color: white; 
#                     border: 2px solid #667eea; 
#                     border-radius: 10px;
#                     z-index: 9999; 
#                     font-size: 13px;
#                     padding: 15px;
#                     box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
#             <p style="margin: 0; font-weight: bold; text-align: center; color: #667eea;">
#                 🎯 Destinos Probables
#             </p>
#             <p style="margin: 10px 0 0 0; text-align: center; color: #999; font-size: 12px;">
#                 Sin datos disponibles
#             </p>
#         </div>
#         """
    
#     destinos_html = """
#     <div style="position: fixed; 
#                 top: 20px; right: 20px; 
#                 width: 300px; 
#                 max-height: 400px;
#                 overflow-y: auto;
#                 background-color: white; 
#                 border: 2px solid #667eea; 
#                 border-radius: 10px;
#                 z-index: 9999; 
#                 font-size: 13px;
#                 padding: 15px;
#                 box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
#         <p style="margin: 0 0 10px 0; font-weight: bold; text-align: center; color: #667eea; font-size: 15px;">
#             🎯 Destinos Probables
#         </p>
#         <p style="margin: 0 0 10px 0; text-align: center; color: #666; font-size: 11px;">
#             (Basado en validaciones 1 hora después)
#         </p>
#     """
    
#     for destino in destinos_probables:
#         ciudad = destino['ciudad']
#         cantidad = destino['cantidad']
#         porcentaje = destino['porcentaje']
        
#         # Barra de progreso
#         destinos_html += f"""
#         <div style="margin-bottom: 12px;">
#             <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
#                 <span style="font-weight: 600; color: #333;">{ciudad}</span>
#                 <span style="color: #667eea; font-weight: bold;">{porcentaje}%</span>
#             </div>
#             <div style="background-color: #e0e0e0; border-radius: 10px; height: 8px; overflow: hidden;">
#                 <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
#                             width: {porcentaje}%; height: 100%;"></div>
#             </div>
#             <div style="font-size: 11px; color: #999; margin-top: 2px;">
#                 {cantidad:,} pasajeros
#             </div>
#         </div>
#         """
    
#     destinos_html += "</div>"
    
#     return destinos_html

def crear_mapa_inicial(gdf_distritos, col_nombre):
    """Crea el mapa inicial solo con los shapes de distritos"""
    # Calcular centro del mapa
    bounds = gdf_distritos.total_bounds
    centro = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Crear mapa base
    mapa = folium.Map(location=centro, zoom_start=11, tiles='OpenStreetMap')
    
    # Agregar cada distrito al mapa sin datos
    for idx, row in gdf_distritos.iterrows():
        nombre = row[col_nombre] if pd.notna(row[col_nombre]) else "Sin nombre"
        
        # Color gris para el estado inicial
        color = '#cccccc'
        
        # Agregar polígono al mapa con highlight
        folium.GeoJson(
            row['geometry'].__geo_interface__,
            style_function=lambda x, color=color: {
                'fillColor': color,
                'color': 'black',
                'weight': 2,
                'fillOpacity': 0.4
            },
            highlight_function=lambda x: {
                'fillColor': '#ffff00',
                'color': '#ff0000',
                'weight': 4,
                'fillOpacity': 0.7
            },
            tooltip=folium.Tooltip(f'<b>{nombre}</b><br>Sin datos')
        ).add_to(mapa)
    
    return mapa._repr_html_()

#def crear_mapa_con_datos(gdf_resultado, col_nombre, destinos_probables):
def crear_mapa_con_datos(gdf_resultado, col_nombre):
    """Crea el mapa interactivo con datos de validaciones"""
    # Calcular centro del mapa
    bounds = gdf_resultado.total_bounds
    centro = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Crear mapa base
    mapa = folium.Map(location=centro, zoom_start=11, tiles='OpenStreetMap')
    
    # Obtener máximo y mínimo de validaciones para escala de colores
    max_validaciones = gdf_resultado['cantidad'].max()
    min_validaciones = gdf_resultado[gdf_resultado['cantidad'] > 0]['cantidad'].min() if (gdf_resultado['cantidad'] > 0).any() else 0
    
    # Agregar cada distrito al mapa
    for idx, row in gdf_resultado.iterrows():
        nombre = row[col_nombre] if pd.notna(row[col_nombre]) else "Sin nombre"
        cantidad = row['cantidad']
        
        # Color basado en cantidad de validaciones (verde a rojo)
        if max_validaciones > 0 and cantidad > 0:
            intensidad = cantidad / max_validaciones
            # Gradiente: verde -> amarillo -> rojo
            if intensidad < 0.5:
                # Verde a amarillo
                r = int(255 * (intensidad * 2))
                g = 255
                b = 0
            else:
                # Amarillo a rojo
                r = 255
                g = int(255 * (2 - intensidad * 2))
                b = 0
            color = f'#{r:02x}{g:02x}{b:02x}'
        else:
            color = '#cccccc'
        
        # Agregar polígono al mapa con highlight
        folium.GeoJson(
            row['geometry'].__geo_interface__,
            style_function=lambda x, color=color: {
                'fillColor': color,
                'color': 'black',
                'weight': 2,
                'fillOpacity': 0.6
            },
            highlight_function=lambda x: {
                'fillColor': '#ffff00',
                'color': '#0000ff',
                'weight': 5,
                'fillOpacity': 0.8
            },
            tooltip=folium.Tooltip(f'<b>{nombre}</b><br>{cantidad:,} validaciones', sticky=True)
        ).add_to(mapa)
    
    # Agregar leyenda de mapa de calor
    if max_validaciones > 0:
        leyenda_html = crear_leyenda_mapa_calor(min_validaciones, max_validaciones)
        mapa.get_root().html.add_child(folium.Element(leyenda_html))
    
    # Agregar cuadro de destinos probables
    # destinos_html = crear_cuadro_destinos(destinos_probables)
    # mapa.get_root().html.add_child(folium.Element(destinos_html))
    
    return mapa._repr_html_()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis de Validaciones - Central, Paraguay</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-size: 14px;
            color: #555;
            margin-bottom: 5px;
            font-weight: 600;
        }
        
        select {
            padding: 10px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            background: white;
            cursor: pointer;
            transition: all 0.3s;
            min-width: 150px;
        }
        
        select:hover {
            border-color: #667eea;
        }
        
        select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        button {
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 20px;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .content {
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        #map-container {
            height: 600px;
            width: 100%;
            position: relative;
        }
        
        #tabla-container {
            padding: 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }
        
        tbody tr:hover {
            background: #f8f9ff;
        }
        
        .total-row {
            background: #f0f0f0;
            font-weight: bold;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
            color: #667eea;
            font-size: 18px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .error {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            display: none;
        }
        
        .info-badge {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .cache-badge {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }
        
        .no-data-message {
            text-align: center;
            padding: 30px;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Análisis de Validaciones - Departamento Central</h1>
            <p class="subtitle">
                <span class="info-badge">Horario Pico: 5:00 - 7:59</span>
                <span id="cache-indicator"></span>
            </p>
            
            <div class="controls">
                <div class="form-group">
                    <label for="mes">Mes:</label>
                    <select id="mes">
                        <option value="1">Enero</option>
                        <option value="2">Febrero</option>
                        <option value="3">Marzo</option>
                        <option value="4">Abril</option>
                        <option value="5">Mayo</option>
                        <option value="6">Junio</option>
                        <option value="7">Julio</option>
                        <option value="8">Agosto</option>
                        <option value="9">Septiembre</option>
                        <option value="10">Octubre</option>
                        <option value="11">Noviembre</option>
                        <option value="12">Diciembre</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="anio">Año:</label>
                    <select id="anio">
                        <option value="2025">2025</option>
                        <option value="2024">2024</option>
                        <option value="2023">2023</option>
                        <option value="2022">2022</option>
                    </select>
                </div>
                
                <button onclick="obtenerDatos()" id="btnObtener">
                    🔍 Obtener Datos
                </button>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Procesando datos, por favor espere...</p>
        </div>
        
        <div class="error" id="error"></div>
        
        <div class="content">
            <div id="map-container">{{ mapa_inicial|safe }}</div>
            <div id="tabla-container">
                <div class="no-data-message">
                    Selecciona un mes y año, luego haz clic en "Obtener Datos" para ver las estadísticas.
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Establecer mes y año actual por defecto
        const fechaActual = new Date();
        document.getElementById('mes').value = fechaActual.getMonth() + 1;
        document.getElementById('anio').value = fechaActual.getFullYear();
        
        async function obtenerDatos() {
            const mes = document.getElementById('mes').value;
            const anio = document.getElementById('anio').value;
            const btnObtener = document.getElementById('btnObtener');
            const loading = document.getElementById('loading');
            const errorDiv = document.getElementById('error');
            const cacheIndicator = document.getElementById('cache-indicator');
            
            // Mostrar loading
            btnObtener.disabled = true;
            loading.style.display = 'block';
            errorDiv.style.display = 'none';
            cacheIndicator.innerHTML = '';
            
            try {
                const response = await fetch('/obtener_datos', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ mes: mes, anio: anio })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    errorDiv.textContent = '❌ Error: ' + data.error;
                    errorDiv.style.display = 'block';
                } else {
                    // Mostrar indicador de cache
                    if (data.desde_cache) {
                        cacheIndicator.innerHTML = '<span class="cache-badge">⚡ Cargado desde caché</span>';
                    }
                    
                    // Actualizar mapa
                    document.getElementById('map-container').innerHTML = data.mapa;
                    
                    // Actualizar tabla
                    document.getElementById('tabla-container').innerHTML = data.tabla;
                }
            } catch (error) {
                errorDiv.textContent = '❌ Error al obtener datos: ' + error.message;
                errorDiv.style.display = 'block';
            } finally {
                loading.style.display = 'none';
                btnObtener.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # Crear mapa inicial con los shapes
    mapa_inicial = crear_mapa_inicial(gdf_distritos, columna_nombre)
    return render_template_string(HTML_TEMPLATE, mapa_inicial=mapa_inicial)

@app.route('/obtener_datos', methods=['POST'])
def obtener_datos():
    try:
        data = request.json
        mes = int(data['mes'])
        anio = int(data['anio'])
        
        # Intentar cargar desde cache
        gdf_resultado, desde_cache = cargar_cache(mes, anio)
        
        if not desde_cache:
            # No hay cache, obtener de la base de datos
            print(f"No hay cache para {mes}/{anio}, consultando base de datos...")
            df_validaciones = obtener_validaciones(mes, anio)
            
            if df_validaciones is None or len(df_validaciones) == 0:
                return jsonify({'error': 'No se encontraron validaciones para el período seleccionado'})
            
            # Asignar validaciones a distritos
            gdf_resultado = asignar_validaciones_a_distritos(df_validaciones, gdf_distritos, columna_nombre)
            
            # Guardar en cache
            guardar_cache(mes, anio, gdf_resultado)
        
        # Crear mapa con datos
        mapa_html = crear_mapa_con_datos(gdf_resultado, columna_nombre)
        
        # Crear tabla
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        total_validaciones = gdf_resultado['cantidad'].sum()
        
        tabla_html = f"""
        <h2>Validaciones por Distrito - {meses[mes]} {anio}</h2>
        <p style="color: #666; margin-bottom: 10px;">
            Total de validaciones: {total_validaciones:,}
            {' | <span style="color: #28a745;">⚡ Datos desde caché</span>' if desde_cache else ''}
        </p>
        <table>
            <thead>
                <tr>
                    <th>Distrito</th>
                    <th style="text-align: right;">Cantidad de Validaciones</th>
                    <th style="text-align: right;">Porcentaje</th>
                </tr>
            </thead>
            <tbody>
        """
        
        # Ordenar por cantidad
        gdf_ordenado = gdf_resultado.sort_values('cantidad', ascending=False)
        
        for idx, row in gdf_ordenado.iterrows():
            nombre = row[columna_nombre] if pd.notna(row[columna_nombre]) else "Sin nombre"
            cantidad = row['cantidad']
            porcentaje = (cantidad / total_validaciones * 100) if total_validaciones > 0 else 0
            
            tabla_html += f"""
                <tr>
                    <td>{nombre}</td>
                    <td style="text-align: right;">{cantidad:,}</td>
                    <td style="text-align: right;">{porcentaje:.2f}%</td>
                </tr>
            """
        
        tabla_html += f"""
                <tr class="total-row">
                    <td>TOTAL</td>
                    <td style="text-align: right;">{total_validaciones:,}</td>
                    <td style="text-align: right;">100.00%</td>
                </tr>
            </tbody>
        </table>
        """
        
        return jsonify({
            'mapa': mapa_html,
            'tabla': tabla_html,
            'desde_cache': desde_cache
        })
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)})

def abrir_navegador():
    """Abre el navegador después de 2 segundos"""
    import time
    time.sleep(2)
    webbrowser.open('http://localhost:5000')

if __name__ == "__main__":
    print("=" * 60)
    print("INICIANDO SERVIDOR WEB")
    print("=" * 60)
    
    # Cargar todos los shapes (Central, Asunción, Chaco)
    print("\nCargando todos los shapefiles...")
    gdf_todas_ciudades = cargar_todos_los_shapes()
    
    # Cargar distritos de Central para el mapa principal
    print("\nCargando distritos de Central...")
    gdf_distritos, columna_nombre = cargar_distritos()
    
    print("\n✓ Servidor listo!")
    print(f"✓ Directorio de cache: {CACHE_DIR}")
    print("\nAbriendo navegador en: http://localhost:5000")
    print("\nPresiona Ctrl+C para detener el servidor")
    print("=" * 60)
    
    # Abrir navegador en un hilo separado
    threading.Thread(target=abrir_navegador, daemon=True).start()
    
    app.run(debug=False, port=5000)
    
# if __name__ == "__main__":
#     print("=" * 60)
#     print("INICIANDO SERVIDOR WEB")
#     print("=" * 60)
    
#     # Cargar todos los shapes (Central, Asunción, Chaco)
#     print("\nCargando todos los shapefiles...")
#     gdf_todas_ciudades = cargar_todos_los_shapes()
    
#     # Cargar distritos de Central para el mapa principal
#     print("\nCargando distritos de Central...")
#     gdf_distritos, columna_nombre = cargar_distritos()
    
#     print("\n✓ Servidor listo!")
#     print(f"✓ Directorio de cache: {CACHE_DIR}")
#     print("\nAbre tu navegador en: http://localhost:5000")
#     print("\nPresiona Ctrl+C para detener el servidor")
#     print("=" * 60)
    
#     app.run(debug=True, port=5000)