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

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos de validaciones
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', '5432')
}

# Configuración de la base de datos de rutas (EOTs)
DB_RUTAS_CONFIG = {
    'host': os.getenv('DB_RUTAS_HOST', os.getenv('DB_HOST')),
    'database': os.getenv('DB_RUTAS_NAME'),
    'user': os.getenv('DB_RUTAS_USER', os.getenv('DB_USER')),
    'password': os.getenv('DB_RUTAS_PASSWORD', os.getenv('DB_PASSWORD')),
    'port': os.getenv('DB_RUTAS_PORT', '5432')
}

app = Flask(__name__)

# Variables globales
gdf_distritos = None
gdf_barrios = None
columna_nombre_distrito = None
columna_nombre_barrio = None
columna_nombre_barrio_simple = None

# Directorio para cache
CACHE_DIR = 'cache_validaciones'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def cargar_distritos():
    """Carga los shapefiles de distritos de Central, Asunción y Presidente Hayes"""
    
    # Definir rutas de los shapefiles de distritos
    rutas_distritos = [
        # Central
        ('DPTO_CENTRAL', 'Distritos_Central.shp'),
        ('CIUDADES/DPTO_CENTRAL', 'Distritos_Central.shp'),
        # Asunción
        ('CIUDADES/ASUNCION', 'Distrito_Asuncion.shp'),
        # Presidente Hayes
        #('CIUDADES/PRESIDENTE_HAYES', 'Distritos_Presidente Hayes.shp'),
    ]
    
    gdfs_distritos = []
    
    for carpeta, archivo in rutas_distritos:
        ruta_completa = os.path.join(carpeta, archivo)
        if os.path.exists(ruta_completa):
            try:
                gdf = gpd.read_file(ruta_completa)
                
                # Asegurar que está en WGS84 (EPSG:4326)
                if gdf.crs != 'EPSG:4326':
                    gdf = gdf.to_crs('EPSG:4326')
                
                gdfs_distritos.append(gdf)
                print(f"✓ Cargado: {ruta_completa} ({len(gdf)} distritos)")
            except Exception as e:
                print(f"✗ Error cargando {ruta_completa}: {e}")
    
    if not gdfs_distritos:
        raise Exception("No se pudieron cargar los shapefiles de distritos")
    
    # Combinar todos los GeoDataFrames de distritos
    gdf_combinado = pd.concat(gdfs_distritos, ignore_index=True)
    
    print(f"\n✓ Total de distritos cargados: {len(gdf_combinado)}")
    print(f"Columnas disponibles: {gdf_combinado.columns.tolist()}")
    
    # Buscar columna de nombre para distritos
    col_nombre = None
    columnas_posibles = ['DIST_DESC_', 'DIST_DESC', 'NOMBRE', 'nombre', 'Nombre', 'DISTRITO', 'distrito', 'Distrito', 'NAME', 'name']
    for col in columnas_posibles:
        if col in gdf_combinado.columns:
            col_nombre = col
            break
    
    if col_nombre is None:
        col_nombre = gdf_combinado.columns[0]
    
    print(f"Usando columna '{col_nombre}' para nombres de distritos")
    
    return gdf_combinado, col_nombre

def cargar_vias():
    """Carga los shapefiles de vias de Central, Asunción y Presidente Hayes"""
    rutas_vias = [
        # Central
        ('CIUDADES/DPTO_CENTRAL', 'Vías Principales_Central.shp'),
        # Asunción
        ('CIUDADES/ASUNCION', 'Vías principales_Asuncion.shp'),
        # Presidente Hayes
        #('CIUDADES/PRESIDENTE_HAYES', 'Vias_Presidente Hayes.shp'),
    ]
    gdfs_vias = []
    
    for carpeta, archivo in rutas_vias:
        ruta_completa = os.path.join(carpeta, archivo)
        if os.path.exists(ruta_completa):
            try:
                gdf = gpd.read_file(ruta_completa)
                
                # Asegurar que está en WGS84 (EPSG:4326)
                if gdf.crs != 'EPSG:4326':
                    gdf = gdf.to_crs('EPSG:4326')
                
                gdfs_vias.append(gdf)
                print(f"✓ Cargado: {ruta_completa} ({len(gdf)} vias)")
            except Exception as e:
                print(f"✗ Error cargando {ruta_completa}: {e}")
    if not gdfs_vias:
        print("No se pudieron cargar los shapefiles de vias")
    # Combinar todos los GeoDataFrames de distritos
    gdf_combinado = pd.concat(gdfs_vias, ignore_index=True)
    
    print(f"\n✓ Total de vías cargadas: {len(gdf_combinado)}")
    print(f"Columnas disponibles: {gdf_combinado.columns.tolist()}")
    
    # Buscar columna de nombre para vías
    # col_nombre = 'NOMBRE'
    # columnas_posibles = ['DIST_DESC_', 'DIST_DESC', 'NOMBRE', 'nombre', 'Nombre', 'DISTRITO', 'distrito', 'Distrito', 'NAME', 'name']
    # for col in columnas_posibles:
    #     if col in gdf_combinado.columns:
    #         col_nombre = col
    #         break
    col_nombre = 'NOMBRE'
    
    if col_nombre is None:
        col_nombre = gdf_combinado.columns[0]
    
    print(f"Usando columna '{col_nombre}' para nombres de vías")
    
    return gdf_combinado, col_nombre


def cargar_barrios():
    """Carga los shapefiles de barrios de Central, Asunción y Presidente Hayes"""
    
    # Definir rutas de los shapefiles de barrios
    rutas_barrios = [
        # Central
        ('DPTO_CENTRAL', 'Barrios Localidades_Central.shp'),
        ('CIUDADES/DPTO_CENTRAL', 'Barrios Localidades_Central.shp'),
        # Asunción
        ('CIUDADES/ASUNCION', 'Barrios Localidades_Asuncion.shp'),
        # Presidente Hayes
        #('CIUDADES/PRESIDENTE_HAYES', 'Barrios Localidades_Presidente Hayes.shp'),
    ]
    
    gdfs_barrios = []
    
    for carpeta, archivo in rutas_barrios:
        ruta_completa = os.path.join(carpeta, archivo)
        if os.path.exists(ruta_completa):
            try:
                gdf = gpd.read_file(ruta_completa)
                
                # Asegurar que está en WGS84 (EPSG:4326)
                if gdf.crs != 'EPSG:4326':
                    gdf = gdf.to_crs('EPSG:4326')
                
                gdfs_barrios.append(gdf)
                print(f"✓ Cargado: {ruta_completa} ({len(gdf)} barrios)")
            except Exception as e:
                print(f"✗ Error cargando {ruta_completa}: {e}")
    
    if not gdfs_barrios:
        print("⚠️ Advertencia: No se encontraron shapefiles de barrios")
        return None, None, None
    
    # Combinar todos los GeoDataFrames de barrios
    gdf_combinado = pd.concat(gdfs_barrios, ignore_index=True)
    
    print(f"\n✓ Total de barrios cargados: {len(gdf_combinado)}")
    print(f"Columnas disponibles: {gdf_combinado.columns.tolist()}")
    
    # Buscar columna de nombre para barrios
    col_nombre = None
    columnas_posibles = ['BARLO_DESC', 'DIST_DESC_', 'NOMBRE', 'nombre', 'Nombre', 'BARRIO', 'barrio', 'Barrio', 'NAME', 'name']
    for col in columnas_posibles:
        if col in gdf_combinado.columns:
            col_nombre = col
            break
    
    if col_nombre is None:
        col_nombre = gdf_combinado.columns[0]
    
    # Buscar columna de distrito para barrios
    col_distrito = None
    columnas_distrito_posibles = ['DIST_DESC_', 'DIST_DESC', 'DISTRITO', 'distrito', 'Distrito']
    for col in columnas_distrito_posibles:
        if col in gdf_combinado.columns:
            col_distrito = col
            break
    
    # Crear columna combinada: "Barrio - Distrito"
    if col_distrito and col_distrito in gdf_combinado.columns:
        gdf_combinado['barrio_completo'] = gdf_combinado[col_nombre].astype(str) + ' - ' + gdf_combinado[col_distrito].astype(str)
        col_nombre_completo = 'barrio_completo'
        print(f"Usando columna '{col_nombre}' para nombres de barrios y '{col_distrito}' para distritos")
        print(f"Columna combinada creada: 'barrio_completo'")
    else:
        col_nombre_completo = col_nombre
        print(f"⚠️ No se encontró columna de distrito, usando solo '{col_nombre}'")
    
    return gdf_combinado, col_nombre_completo, col_nombre

def obtener_cache_key(mes, anio, horario_pico, incluir_barrios):
    """Genera una clave única para el cache"""
    barrios_suffix = "_barrios" if incluir_barrios else ""
    return f"validaciones_{anio}_{mes:02d}_{horario_pico}{barrios_suffix}"

def guardar_cache(mes, anio, horario_pico, incluir_barrios, gdf_resultado, col_nombre):
    """Guarda los resultados en cache como JSON"""
    cache_key = obtener_cache_key(mes, anio, horario_pico, incluir_barrios)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    # Convertir GeoDataFrame a formato serializable
    cache_data = {
        'mes': mes,
        'anio': anio,
        'horario_pico': horario_pico,
        'incluir_barrios': incluir_barrios,
        'fecha_cache': datetime.now().isoformat(),
        'areas': []
    }
    
    for idx, row in gdf_resultado.iterrows():
        cache_data['areas'].append({
            'nombre': row[col_nombre],
            'cantidad_validaciones': int(row['cantidad_validaciones']),
            'cantidad_pasajeros': int(row['cantidad_pasajeros']),
            'cantidad_buses': int(row['cantidad_buses']),
            'empresas': row.get('empresas', ''),
            'lineas': row.get('lineas', '')
        })
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Cache guardado: {cache_file}")

def cargar_cache(mes, anio, horario_pico, incluir_barrios, gdf_base, col_nombre):
    """Carga los resultados desde cache si existe"""
    cache_key = obtener_cache_key(mes, anio, horario_pico, incluir_barrios)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        print(f"✓ Cargando desde cache: {cache_file}")
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Reconstruir GeoDataFrame con los datos del cache
        gdf_resultado = gdf_base.copy()
        
        # Crear diccionarios de cantidades
        validaciones = {d['nombre']: d['cantidad_validaciones'] for d in cache_data['areas']}
        pasajeros = {d['nombre']: d['cantidad_pasajeros'] for d in cache_data['areas']}
        buses = {d['nombre']: d['cantidad_buses'] for d in cache_data['areas']}
        empresas = {d['nombre']: d.get('empresas', '') for d in cache_data['areas']}
        lineas = {d['nombre']: d.get('lineas', '') for d in cache_data['areas']}
        
        # Asignar cantidades al GeoDataFrame
        gdf_resultado['cantidad_validaciones'] = gdf_resultado[col_nombre].map(validaciones).fillna(0).astype(int)
        gdf_resultado['cantidad_pasajeros'] = gdf_resultado[col_nombre].map(pasajeros).fillna(0).astype(int)
        gdf_resultado['cantidad_buses'] = gdf_resultado[col_nombre].map(buses).fillna(0).astype(int)
        gdf_resultado['empresas'] = gdf_resultado[col_nombre].map(empresas).fillna('')
        gdf_resultado['lineas'] = gdf_resultado[col_nombre].map(lineas).fillna('')
        
        return gdf_resultado, True
    
    return None, False

def obtener_validaciones(mes, anio, horario_pico):
    """Obtiene las validaciones en horario pico desde PostgreSQL"""
    
    # Calcular fechas de inicio y fin del mes
    if mes == 12:
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio + 1}-01-01"
    else:
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio}-{mes + 1:02d}-01"
    
    # Definir rango de horas según el horario pico
    if horario_pico == 'manana':
        hora_inicio = 5
        hora_fin = 7
        nombre_pico = "Mañana (5:00 - 7:59)"
    else:  # tarde
        hora_inicio = 16
        hora_fin = 18
        nombre_pico = "Tarde (16:00 - 18:59)"
    
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
            consecutivoevento,
            tipoevento
        FROM c_transacciones 
        WHERE fechahoraevento >= %s 
            AND fechahoraevento < %s
            AND DATE_PART('hour', fechahoraevento) BETWEEN %s AND %s
            AND tipoevento IN (4,8)
            AND latitude IS NOT NULL
            AND longitude IS NOT NULL
            -- INICIO DE LA OPTIMIZACIÓN GEOGRÁFICA
            AND (latitude BETWEEN -26.00 AND -25.00 AND longitude BETWEEN -58.00 AND -57.00)
            -- FIN DE LA OPTIMIZACIÓN GEOGRÁFICA
        ORDER BY idsam, consecutivoevento, serialmediopago, fechahoraevento, fechahoraevento DESC;
        """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        df = pd.read_sql_query(query, conn, params=(fecha_inicio, fecha_fin, hora_inicio, hora_fin))
        conn.close()
        print(f"Validaciones obtenidas ({nombre_pico}): {len(df)}")
        return df
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def obtener_empresas_lineas_por_area(gdf_areas):
    """Obtiene las empresas y líneas que pasan por cada área desde la base de datos de rutas"""
    
    try:
        conn = psycopg2.connect(**DB_RUTAS_CONFIG)
        
        # Consulta para obtener rutas con sus empresas
        query = """
        SELECT 
            cr.linea,
            cr.geom,
            e.eot_nombre AS nombre_eot
        FROM catalogo_rutas cr
        INNER JOIN eots e ON cr.id_eot_catalogo = e.cod_catalogo
        WHERE cr.geom IS NOT NULL
        AND cr.estado IS TRUE
        """
        
        # Cargar rutas como GeoDataFrame
        gdf_rutas = gpd.read_postgis(query, conn, geom_col='geom')
        conn.close()
        
        # Asegurar que ambos GeoDataFrames están en el mismo CRS
        if gdf_rutas.crs != gdf_areas.crs:
            gdf_rutas = gdf_rutas.to_crs(gdf_areas.crs)
        
        print(f"✓ Rutas cargadas: {len(gdf_rutas)}")
        
        # Para cada área, encontrar qué rutas la intersectan
        resultados = {}
        
        for idx, area in gdf_areas.iterrows():
            area_geom = area.geometry
            
            # Encontrar rutas que intersectan con el área
            rutas_intersectan = gdf_rutas[gdf_rutas.intersects(area_geom)]
            
            if len(rutas_intersectan) > 0:
                # Obtener empresas únicas
                empresas = sorted(rutas_intersectan['nombre_eot'].unique().tolist())
                # Obtener líneas únicas
                lineas = sorted(rutas_intersectan['linea'].unique().tolist())
                
                resultados[idx] = {
                    'empresas': ', '.join(empresas),
                    'lineas': ', '.join(lineas),
                    'num_empresas': len(empresas),
                    'num_lineas': len(lineas)
                }
            else:
                resultados[idx] = {
                    'empresas': '',
                    'lineas': '',
                    'num_empresas': 0,
                    'num_lineas': 0
                }
        
        return resultados
        
    except Exception as e:
        print(f"⚠️ Error al obtener empresas y líneas: {e}")
        import traceback
        print(traceback.format_exc())
        return {}

def asignar_validaciones_a_areas(df_validaciones, gdf_areas, col_nombre):
    """Asigna cada validación a su área correspondiente y cuenta validaciones, pasajeros y buses únicos"""
    # Crear GeoDataFrame con las validaciones
    geometry = [Point(xy) for xy in zip(df_validaciones['longitude'], df_validaciones['latitude'])]
    gdf_validaciones = gpd.GeoDataFrame(df_validaciones, geometry=geometry, crs='EPSG:4326')
    
    # Realizar spatial join
    validaciones_con_area = gpd.sjoin(
        gdf_validaciones, 
        gdf_areas, 
        how='left', 
        predicate='within'
    )
    
    # Contar validaciones por área
    conteo_validaciones = validaciones_con_area.groupby(col_nombre).size().reset_index(name='cantidad_validaciones')
    
    # Contar pasajeros únicos (serialmediopago distintos) por área
    conteo_pasajeros = validaciones_con_area.groupby(col_nombre)['serialmediopago'].nunique().reset_index(name='cantidad_pasajeros')
    
    # Contar buses únicos (idsam distintos) por área
    conteo_buses = validaciones_con_area.groupby(col_nombre)['idsam'].nunique().reset_index(name='cantidad_buses')
    
    # Unir todos los conteos
    conteo_completo = conteo_validaciones.merge(conteo_pasajeros, on=col_nombre, how='outer')
    conteo_completo = conteo_completo.merge(conteo_buses, on=col_nombre, how='outer')
    
    # Unir con geometrías
    gdf_resultado = gdf_areas.merge(conteo_completo, on=col_nombre, how='left')
    gdf_resultado['cantidad_validaciones'] = gdf_resultado['cantidad_validaciones'].fillna(0).astype(int)
    gdf_resultado['cantidad_pasajeros'] = gdf_resultado['cantidad_pasajeros'].fillna(0).astype(int)
    gdf_resultado['cantidad_buses'] = gdf_resultado['cantidad_buses'].fillna(0).astype(int)
    
    # Obtener empresas y líneas que pasan por cada área
    print("Consultando empresas y líneas por área...")
    empresas_lineas = obtener_empresas_lineas_por_area(gdf_resultado)
    
    # Agregar información de empresas y líneas
    for idx in gdf_resultado.index:
        if idx in empresas_lineas:
            gdf_resultado.at[idx, 'empresas'] = empresas_lineas[idx]['empresas']
            gdf_resultado.at[idx, 'lineas'] = empresas_lineas[idx]['lineas']
            gdf_resultado.at[idx, 'num_empresas'] = empresas_lineas[idx]['num_empresas']
            gdf_resultado.at[idx, 'num_lineas'] = empresas_lineas[idx]['num_lineas']
        else:
            gdf_resultado.at[idx, 'empresas'] = ''
            gdf_resultado.at[idx, 'lineas'] = ''
            gdf_resultado.at[idx, 'num_empresas'] = 0
            gdf_resultado.at[idx, 'num_lineas'] = 0
    
    return gdf_resultado

def crear_mapa_inicial(gdf_distritos, col_nombre):
    """Crea el mapa inicial solo con los shapes de distritos"""
    # Calcular centro del mapa
    bounds = gdf_distritos.total_bounds
    centro = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Crear mapa base
    mapa = folium.Map(location=centro, zoom_start=10, tiles='OpenStreetMap')
    
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
            # color distrito seleccionado
            highlight_function=lambda x: {
                #'fillColor': '#ffff00',
                'color': '#ff0000',
                'weight': 4,
                'fillOpacity': 0.4
            },
            tooltip=folium.Tooltip(f'<b>{nombre}</b><br>Sin datos')
        ).add_to(mapa)
    # Agregar vías principales de central y asunción
    # gdf_vias_central = gpd.read_file('CIUDADES/DPTO_CENTRAL/Vías Principales_Central.shp')
    # gdf_vias_asuncion = gpd.read_file('CIUDADES/ASUNCION/Vías Principales_Asuncion.shp')
    # usar la función concatenar para agrupas ambos en gdf_vias
    #gdf_vias = pd.concat([gdf_vias_central, gdf_vias_asuncion], ignore_index=True)
    for idx, row in gdf_vias.iterrows():
        nombre = row['NOMBRE'] if pd.notna(row['NOMBRE']) else "Sin nombre"
        folium.GeoJson(
            row['geometry'].__geo_interface__,
            style_function=lambda x: {
                # color de la via
                #Color verde oscuro
                'color': '#008000',
                'weight': 3,
                'fillOpacity': 0
            },
            tooltip=folium.Tooltip(f'<b>{nombre}</b><br>Sin datos')
        ).add_to(mapa)
    return mapa._repr_html_()
    
def crear_leyenda_mapa_calor(min_val, max_val, tipo='validaciones'):
    """Crea una leyenda de mapa de calor personalizada"""
    
    titulo = 'Validaciones' if tipo == 'validaciones' else 'Pasajeros Únicos'
    
    # Calcular rangos
    rango = max_val - min_val
    if rango == 0:
        rangos = [(min_val, min_val, '#cccccc')]
    else:
        step = rango / 5
        rangos = [
            (min_val, min_val + step, '#4dd3c9'),           # Turquesa claro
            (min_val + step, min_val + 2*step, '#3dbfb5'),  # Turquesa medio-claro
            (min_val + 2*step, min_val + 3*step, '#2da9a0'), # Turquesa medio
            (min_val + 3*step, min_val + 4*step, '#1e8f87'), # Turquesa oscuro
            (min_val + 4*step, max_val, '#0f5f5a')          # Turquesa muy oscuro
        ]
    
    leyenda_html = f"""
    <div style="position: fixed; 
                bottom: 50px; right: 50px; 
                width: 220px; 
                background-color: white; 
                border: 2px solid grey; 
                border-radius: 10px;
                z-index: 9999; 
                font-size: 14px;
                padding: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <p style="margin: 0 0 10px 0; font-weight: bold; text-align: center;">
            {titulo}
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

def crear_mapa_con_datos(gdf_resultado, col_nombre, col_nombre_simple, incluir_barrios):
    """Crea el mapa interactivo con datos de validaciones"""
    # Calcular centro del mapa
    bounds = gdf_resultado.total_bounds
    centro = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Crear mapa base
    zoom_inicial = 10 if not incluir_barrios else 11
    mapa = folium.Map(location=centro, zoom_start=zoom_inicial, tiles='OpenStreetMap')
    
    # Obtener máximo y mínimo de validaciones para escala de colores
    max_validaciones = gdf_resultado['cantidad_validaciones'].max()
    min_validaciones = gdf_resultado[gdf_resultado['cantidad_validaciones'] > 0]['cantidad_validaciones'].min() if (gdf_resultado['cantidad_validaciones'] > 0).any() else 0
    
    # Agregar cada área al mapa
    for idx, row in gdf_resultado.iterrows():
        nombre_completo = row[col_nombre] if pd.notna(row[col_nombre]) else "Sin nombre"
        nombre_simple = row[col_nombre_simple] if col_nombre_simple and pd.notna(row[col_nombre_simple]) else nombre_completo
        cantidad_validaciones = row['cantidad_validaciones']
        cantidad_pasajeros = row['cantidad_pasajeros']
        cantidad_buses = row['cantidad_buses']
        num_empresas = row.get('num_empresas', 0)
        num_lineas = row.get('num_lineas', 0)
        
        # Color basado en cantidad de validaciones (escala turquesa)
        if max_validaciones > 0 and cantidad_validaciones > 0:
            intensidad = cantidad_validaciones / max_validaciones
            
            # Escala de 5 colores turquesa (de claro a oscuro)
            if intensidad <= 0.2:
                color = '#4dd3c9'  # Turquesa muy claro
            elif intensidad <= 0.4:
                color = '#3dbfb5'  # Turquesa claro
            elif intensidad <= 0.6:
                color = '#2da9a0'  # Turquesa medio
            elif intensidad <= 0.8:
                color = '#1e8f87'  # Turquesa oscuro
            else:
                color = '#0f5f5a'  # Turquesa muy oscuro
        else:
            color = '#cccccc'  # Gris para áreas sin datos
        
        # Tooltip con información completa
        tipo_area = "Barrio" if incluir_barrios else "Distrito"
        tooltip_text = f"""
        <div style="font-family: Arial; font-size: 13px; min-width: 250px;">
            <b style="font-size: 14px;">{nombre_completo}</b><br>
            <span style="font-size: 11px; color: #666;">({tipo_area})</span>
            <hr style="margin: 5px 0;">
            <b>📊 DEMANDA:</b><br>
            &nbsp;&nbsp;• Validaciones: {cantidad_validaciones:,}<br>
            &nbsp;&nbsp;• Pasajeros únicos: {cantidad_pasajeros:,}<br>
            <b>🚌 OFERTA:</b><br>
            &nbsp;&nbsp;• Buses únicos: {cantidad_buses:,}<br>
            &nbsp;&nbsp;• Empresas: {num_empresas}<br>
            &nbsp;&nbsp;• Líneas: {num_lineas}
        </div>
        """
        
        # Grosor de línea según nivel
        peso_linea = 1 if incluir_barrios else 2
        
        # Agregar polígono al mapa con highlight
        folium.GeoJson(
            row['geometry'].__geo_interface__,
            style_function=lambda x, color=color, peso=peso_linea: {
                'fillColor': color,
                'color': 'white',  # Borde blanco como en la imagen
                'weight': peso,
                'fillOpacity': 0.8
            },
            highlight_function=lambda x: {
                #'fillColor': '#ffff00',
                'color': '#0000ff',
                'weight': 5,
                'fillOpacity': 1#0.8
            },
            tooltip=folium.Tooltip(tooltip_text, sticky=True)
        ).add_to(mapa)
    
    # Agregar leyenda de mapa de calor
    if max_validaciones > 0:
        leyenda_html = crear_leyenda_mapa_calor(min_validaciones, max_validaciones, 'validaciones')
        mapa.get_root().html.add_child(folium.Element(leyenda_html))
    
    return mapa._repr_html_()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis de Validaciones - Paraguay</title>
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
            max-width: 1600px;
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
            align-items: flex-end;
            flex-wrap: wrap;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 0;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
        
        .checkbox-group label {
            margin: 0;
            cursor: pointer;
            user-select: none;
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
            height: 44px;
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
            margin-top: 250px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 13px;
        }
        
        thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        th {
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
        }
        
        td {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        
        tbody tr:hover {
            background: #f8f9ff;
        }
        
        .total-row {
            background: #f0f0f0;
            font-weight: bold;
        }
        
        .empresas-cell, .lineas-cell {
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 11px;
            color: #555;
        }
        
        .empresas-cell:hover, .lineas-cell:hover {
            white-space: normal;
            overflow: visible;
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
            <h1>📊 Análisis de Validaciones - Central, Asunción y Presidente Hayes</h1>
            <p class="subtitle">
                <span id="horario-badge" class="info-badge">Selecciona un horario pico</span>
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
                
                <div class="form-group">
                    <label for="horario_pico">Horario Pico:</label>
                    <select id="horario_pico">
                        <option value="manana">🌅 Mañana (5:00 - 7:59)</option>
                        <option value="tarde">🌆 Tarde (16:00 - 18:59)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>&nbsp;</label>
                    <div class="checkbox-group">
                        <input type="checkbox" id="incluir_barrios" name="incluir_barrios">
                        <label for="incluir_barrios">🏘️ Incluir Barrios</label>
                    </div>
                </div>
                
                <button onclick="obtenerDatos()" id="btnObtener">
                    🔍 Obtener Datos
                </button>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <!--
            Esto en color blanco, en negrita y en mayúsculas
            -->
            <p style="color: white; font-weight: bold;">Procesando datos, por favor espere...</p>
            <p style="color: white; font-weight: bold;">Este proceso puede demorar aproximadamente 2 minutos</p>

        </div>
        
        <div class="error" id="error"></div>
        
        <div class="content">
            <div id="map-container">{{ mapa_inicial|safe }}</div>
            <div id="tabla-container">
                <div class="no-data-message">
                    Selecciona un mes, año y horario pico, luego haz clic en "Obtener Datos" para ver las estadísticas.
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Establecer mes y año actual por defecto
        const fechaActual = new Date();
        document.getElementById('mes').value = fechaActual.getMonth() + 1;
        document.getElementById('anio').value = fechaActual.getFullYear();
        
        // Actualizar badge de horario al cambiar selector
        document.getElementById('horario_pico').addEventListener('change', function() {
            const horarioBadge = document.getElementById('horario-badge');
            if (this.value === 'manana') {
                horarioBadge.textContent = '🌅 Pico Mañana: 5:00 - 7:59';
            } else {
                horarioBadge.textContent = '🌆 Pico Tarde: 16:00 - 18:59';
            }
        });
        
        // Establecer badge inicial
        document.getElementById('horario-badge').textContent = '🌅 Pico Mañana: 5:00 - 7:59';
        
        async function obtenerDatos() {
            const mes = document.getElementById('mes').value;
            const anio = document.getElementById('anio').value;
            const horario_pico = document.getElementById('horario_pico').value;
            const incluir_barrios = document.getElementById('incluir_barrios').checked;
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
                    body: JSON.stringify({ 
                        mes: mes, 
                        anio: anio,
                        horario_pico: horario_pico,
                        incluir_barrios: incluir_barrios
                    })
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
    mapa_inicial = crear_mapa_inicial(gdf_distritos, columna_nombre_distrito)
    return render_template_string(HTML_TEMPLATE, mapa_inicial=mapa_inicial)

@app.route('/obtener_datos', methods=['POST'])
def obtener_datos():
    try:
        data = request.json
        mes = int(data['mes'])
        anio = int(data['anio'])
        horario_pico = data['horario_pico']
        incluir_barrios = data.get('incluir_barrios', False)
        
        # Seleccionar GeoDataFrame y columna según si se incluyen barrios
        if incluir_barrios:
            if gdf_barrios is None:
                return jsonify({'error': 'No se encontró el shapefile de barrios'})
            gdf_base = gdf_barrios
            col_nombre = columna_nombre_barrio
            col_nombre_simple = columna_nombre_barrio_simple
            tipo_area = "barrios"
        else:
            gdf_base = gdf_distritos
            col_nombre = columna_nombre_distrito
            col_nombre_simple = None
            tipo_area = "distritos"
        
        # Intentar cargar desde cache
        gdf_resultado, desde_cache = cargar_cache(mes, anio, horario_pico, incluir_barrios, gdf_base, col_nombre)
        
        if not desde_cache:
            # No hay cache, obtener de la base de datos
            print(f"No hay cache para {mes}/{anio} ({horario_pico}, {tipo_area}), consultando base de datos...")
            df_validaciones = obtener_validaciones(mes, anio, horario_pico)
            
            if df_validaciones is None or len(df_validaciones) == 0:
                return jsonify({'error': 'No se encontraron validaciones para el período seleccionado'})
            
            # Asignar validaciones a áreas
            gdf_resultado = asignar_validaciones_a_areas(df_validaciones, gdf_base, col_nombre)
            
            # Guardar en cache
            guardar_cache(mes, anio, horario_pico, incluir_barrios, gdf_resultado, col_nombre)
        
        # Crear mapa con datos
        mapa_html = crear_mapa_con_datos(gdf_resultado, col_nombre, col_nombre_simple, incluir_barrios)
        # Cargar de nuevo encima las vías

        
        # Crear tabla
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        horario_texto = "Mañana (5:00 - 7:59)" if horario_pico == 'manana' else "Tarde (16:00 - 18:59)"
        tipo_area_texto = "Barrio" if incluir_barrios else "Distrito"
        
        total_validaciones = gdf_resultado['cantidad_validaciones'].sum()
        
        # Para pasajeros y buses únicos, necesitamos contar los valores distintos en todo el lapso de tiempo
        # No podemos sumar los conteos por área porque eso contaría duplicados
        df_validaciones = obtener_validaciones(mes, anio, horario_pico)
        if df_validaciones is not None and len(df_validaciones) > 0:
            total_pasajeros = df_validaciones['serialmediopago'].nunique()
            total_buses = df_validaciones['idsam'].nunique()
        else:
            total_pasajeros = 0
            total_buses = 0
        
        tabla_html = f"""
        <h2>Análisis de Demanda y Oferta por {tipo_area_texto} - {meses[mes]} {anio}</h2>
        <p style="color: #666; margin-bottom: 10px;">
            <b>Horario Pico:</b> {horario_texto} | 
            <b>Total Validaciones:</b> {total_validaciones:,} | 
            <b>Total Pasajeros Únicos:</b> {total_pasajeros:,} | 
            <b>Total Buses Únicos:</b> {total_buses:,}
            {' | <span style="color: #28a745;">⚡ Datos desde caché</span>' if desde_cache else ''}
        </p>
        <table>
            <thead>
                <tr>
                    <th rowspan="2">{tipo_area_texto}</th>
                    <th colspan="4" style="text-align: center; border-bottom: 1px solid rgba(255,255,255,0.3);">📊 DEMANDA</th>
                    <th colspan="4" style="text-align: center; border-bottom: 1px solid rgba(255,255,255,0.3);">🚌 OFERTA</th>
                </tr>
                <tr>
                    <th style="text-align: right;">Validaciones</th>
                    <th style="text-align: right;">%</th>
                    <th style="text-align: right;">Pasajeros</th>
                    <th style="text-align: right;">%</th>
                    <th style="text-align: right;">Buses</th>
                    <th style="text-align: center;">Empresas</th>
                    <th style="text-align: center;">Líneas</th>
                </tr>
            </thead>
            <tbody>
        """
        
        # Ordenar por cantidad de validaciones
        gdf_ordenado = gdf_resultado.sort_values('cantidad_validaciones', ascending=False)
        
        # Limitar a top 50 si son barrios para no saturar la tabla
        limite = 50 if incluir_barrios else len(gdf_ordenado)
        
        for idx, row in gdf_ordenado.head(limite).iterrows():
            nombre = row[col_nombre] if pd.notna(row[col_nombre]) else "Sin nombre"
            cantidad_validaciones = row['cantidad_validaciones']
            cantidad_pasajeros = row['cantidad_pasajeros']
            cantidad_buses = row['cantidad_buses']
            empresas = row.get('empresas', '')
            lineas = row.get('lineas', '')
            
            porcentaje_validaciones = (cantidad_validaciones / total_validaciones * 100) if total_validaciones > 0 else 0
            porcentaje_pasajeros = (cantidad_pasajeros / total_pasajeros * 100) if total_pasajeros > 0 else 0
            
            # Truncar empresas y líneas para la tabla
            empresas_display = empresas if len(empresas) <= 30 else empresas[:27] + '...'
            lineas_display = lineas if len(lineas) <= 30 else lineas[:27] + '...'
            
            tabla_html += f"""
                <tr>
                    <td>{nombre}</td>
                    <td style="text-align: right;">{cantidad_validaciones:,}</td>
                    <td style="text-align: right;">{porcentaje_validaciones:.2f}%</td>
                    <td style="text-align: right;">{cantidad_pasajeros:,}</td>
                    <td style="text-align: right;">{porcentaje_pasajeros:.2f}%</td>
                    <td style="text-align: right;">{cantidad_buses:,}</td>
                    <td class="empresas-cell" title="{empresas}">{empresas_display if empresas else '-'}</td>
                    <td class="lineas-cell" title="{lineas}">{lineas_display if lineas else '-'}</td>
                </tr>
            """
        
        if incluir_barrios and len(gdf_ordenado) > limite:
            tabla_html += f"""
                <tr>
                    <td colspan="8" style="text-align: center; color: #999; font-style: italic;">
                        Mostrando top {limite} de {len(gdf_ordenado)} barrios
                    </td>
                </tr>
            """
        
        tabla_html += f"""
                <tr class="total-row">
                    <td>TOTAL</td>
                    <td style="text-align: right;">{total_validaciones:,}</td>
                    <td style="text-align: right;">100.00%</td>
                    <td style="text-align: right;">{total_pasajeros:,}</td>
                    <td style="text-align: right;">100.00%</td>
                    <td style="text-align: right;">{total_buses:,}</td>
                    <td style="text-align: center;">-</td>
                    <td style="text-align: center;">-</td>
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

if __name__ == "__main__":
    print("=" * 60)
    print("INICIANDO SERVIDOR WEB")
    print("=" * 60)
    
    # Cargar distritos (Central, Asunción, Presidente Hayes)
    print("\nCargando distritos...")
    gdf_distritos, columna_nombre_distrito = cargar_distritos()
    gdf_vias, columna_nombre_via = cargar_vias()
    
    # Cargar barrios (Central, Asunción, Presidente Hayes)
    print("\nCargando barrios...")
    gdf_barrios, columna_nombre_barrio, columna_nombre_barrio_simple = cargar_barrios()
    
    print("\n✓ Servidor listo!")
    print(f"✓ Directorio de cache: {CACHE_DIR}")
    print(f"✓ Distritos cargados: {len(gdf_distritos)}")
    print(f"✓ Barrios disponibles: {'Sí (' + str(len(gdf_barrios)) + ')' if gdf_barrios is not None else 'No'}")
    print("\nAbre tu navegador en: http://localhost:5000")
    print("\nPresiona Ctrl+C para detener el servidor")
    print("=" * 60)
    
    app.run(debug=True, port=5000)