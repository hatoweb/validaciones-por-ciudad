import os
import psycopg2
from psycopg2 import errors as psycopg2_errors
import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
from branca.element import Template
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify
from shapely.geometry import Point
from datetime import datetime, timedelta
import json
import hashlib
from pathlib import Path
# Añadir imports
from flask_cors import CORS

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
CORS(app)  # permite peticiones desde React en dev (localhost:3000)

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
        print("⚠ No se pudieron cargar los shapefiles de vias")
        # Retornar un GeoDataFrame vacío con estructura básica
        gdf_combinado = gpd.GeoDataFrame(columns=['NOMBRE', 'geometry'], crs='EPSG:4326')
        col_nombre = 'NOMBRE'
    else:
        # Combinar todos los GeoDataFrames de vías
        gdf_combinado = pd.concat(gdfs_vias, ignore_index=True)
        print(f"\n✓ Total de vías cargadas: {len(gdf_combinado)}")
        print(f"Columnas disponibles: {gdf_combinado.columns.tolist()}")
        
        col_nombre = 'NOMBRE'
        if col_nombre not in gdf_combinado.columns:
            col_nombre = gdf_combinado.columns[0] if len(gdf_combinado.columns) > 0 else None
        
        if col_nombre:
            print(f"Usando columna '{col_nombre}' para nombres de vías")
    
    return gdf_combinado, col_nombre


def cargar_poblacion_asuncion():
    """Carga los datos de población de los barrios de Asunción desde el archivo GeoJSON"""
    poblacion_path = os.path.join('CIUDADES', 'ASUNCION_POBLACION', 'AsuPoblacion.geojson')
    poblacion_data = {}
    
    try:
        with open(poblacion_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for feature in data['features']:
            nombre_barrio = feature['properties']['BARLO_DESC'].upper()
            poblacion = feature['properties']['PobTot']
            poblacion_data[nombre_barrio] = poblacion
        
        print(f"  ✓ Datos de población cargados para {len(poblacion_data)} barrios de Asunción")
        return poblacion_data
    except Exception as e:
        print(f"  ✗ Error al cargar datos de población de Asunción: {str(e)}")
        return {}

def cargar_poblacion_central():
    """Carga los datos de población de los barrios/localidades del departamento Central desde el archivo GeoJSON"""
    poblacion_path = os.path.join('CIUDADES', 'CENTRAL_POBLACION', 'CentralPoblacion.geojson')
    poblacion_data = {}
    
    try:
        with open(poblacion_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for feature in data['features']:
            nombre_barrio = feature['properties']['BARLO_DESC'].upper()
            poblacion = feature['properties']['PobTot']
            poblacion_data[nombre_barrio] = poblacion
        
        print(f"  ✓ Datos de población cargados para {len(poblacion_data)} barrios/localidades de Central")
        return poblacion_data
    except Exception as e:
        print(f"  ✗ Error al cargar datos de población de Central: {str(e)}")
        return {}

def cargar_barrios():
    """Carga los shapefiles de barrios de Central, Asunción y Presidente Hayes"""
    
    # Cargar datos de población de Asunción y Central
    poblacion_asuncion = cargar_poblacion_asuncion()
    poblacion_central = cargar_poblacion_central()
    
    # Combinar ambos diccionarios de población
    poblacion_data = {**poblacion_asuncion, **poblacion_central}
    
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
                
                # Agregar datos de población si es Asunción o Central
                if ('ASUNCION' in ruta_completa.upper() or 'CENTRAL' in ruta_completa.upper()) and 'BARLO_DESC' in gdf.columns and poblacion_data:
                    print(f"\nMapeando datos de población para {ruta_completa}")
                    print(f"Barrios en el shapefile: {gdf['BARLO_DESC'].tolist()}")
                    print(f"Barrios en datos de población: {list(poblacion_data.keys())}")
                    gdf['POBLACION'] = gdf['BARLO_DESC'].str.upper().map(poblacion_data)
                    print(f"Barrios con población asignada: {gdf[gdf['POBLACION'].notna()]['BARLO_DESC'].tolist()}")
                
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

def obtener_cache_key(mes, anio, id_franja, incluir_barrios):
    """Genera una clave única para el cache"""
    barrios_suffix = "_barrios" if incluir_barrios else ""
    return f"validaciones_{anio}_{mes:02d}_franja{id_franja}{barrios_suffix}"

def guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre, totals_global=None):
    # No guardar cache si la consulta es del mes actual (puede tener datos incompletos)
    ahora = datetime.now()
    mes_actual = ahora.month
    anio_actual = ahora.year
    
    if mes == mes_actual and anio == anio_actual:
        print(f"⚠️ No se guardará cache para {mes}/{anio} porque corresponde al mes actual (datos pueden estar incompletos)")
        return
    
    cache_key = obtener_cache_key(mes, anio, id_franja, incluir_barrios)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    cache_data = {
        'mes': mes,
        'anio': anio,
        'id_franja': id_franja,
        'incluir_barrios': incluir_barrios,
        'fecha_cache': datetime.now().isoformat(),
        'totals': totals_global or {},
        'areas': []
    }
    for idx, row in gdf_resultado.iterrows():
        area_data = {
            'nombre': row[col_nombre],
            'cantidad_validaciones': int(row.get('cantidad_validaciones', 0)),
            'cantidad_pasajeros': int(row.get('cantidad_pasajeros', 0)),
            'cantidad_buses': int(row.get('cantidad_buses', 0)),
            'promedio_pasajeros_diario': float(row.get('promedio_pasajeros_diario', 0.0)),
            'promedio_buses_diario': float(row.get('promedio_buses_diario', 0.0)),
            'empresas': row.get('empresas', '') or '',
            'lineas': row.get('lineas', '') or ''
        }
        # Guardar relaciones empresa-línea si existen
        if 'empresa_lineas' in row and row.get('empresa_lineas'):
            try:
                empresa_lineas_val = row['empresa_lineas']
                if isinstance(empresa_lineas_val, str):
                    area_data['empresa_lineas'] = json.loads(empresa_lineas_val)
                else:
                    area_data['empresa_lineas'] = empresa_lineas_val
            except:
                pass
        if 'linea_empresas' in row and row.get('linea_empresas'):
            try:
                linea_empresas_val = row['linea_empresas']
                if isinstance(linea_empresas_val, str):
                    area_data['linea_empresas'] = json.loads(linea_empresas_val)
                else:
                    area_data['linea_empresas'] = linea_empresas_val
            except:
                pass
        if 'POBLACION' in row and pd.notna(row['POBLACION']):
            area_data['poblacion'] = int(row['POBLACION'])
        cache_data['areas'].append(area_data)

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    print(f"✓ Cache guardado: {cache_file}")

def cargar_cache(mes, anio, id_franja, incluir_barrios, gdf_base, col_nombre):
    # No cargar cache si la consulta es del mes actual (siempre consultar BD para datos actualizados)
    ahora = datetime.now()
    mes_actual = ahora.month
    anio_actual = ahora.year
    
    if mes == mes_actual and anio == anio_actual:
        print(f"⚠️ No se cargará cache para {mes}/{anio} porque corresponde al mes actual (consulta directa a BD)")
        return None, False, None
    
    cache_key = obtener_cache_key(mes, anio, id_franja, incluir_barrios)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        print(f"✓ Cargando desde cache: {cache_file}")
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        gdf_resultado = gdf_base.copy()
        validaciones = {d['nombre']: d['cantidad_validaciones'] for d in cache_data['areas']}
        pasajeros = {d['nombre']: d['cantidad_pasajeros'] for d in cache_data['areas']}
        buses = {d['nombre']: d['cantidad_buses'] for d in cache_data['areas']}
        promedio_pasajeros = {d['nombre']: d.get('promedio_pasajeros_diario', 0.0) for d in cache_data['areas']}
        promedio_buses = {d['nombre']: d.get('promedio_buses_diario', 0.0) for d in cache_data['areas']}
        empresas = {d['nombre']: d.get('empresas', '') for d in cache_data['areas']}
        lineas = {d['nombre']: d.get('lineas', '') for d in cache_data['areas']}
        poblaciones = {d['nombre']: d.get('poblacion') for d in cache_data['areas'] if 'poblacion' in d}

        gdf_resultado['cantidad_validaciones'] = gdf_resultado[col_nombre].map(validaciones).fillna(0).astype(int)
        gdf_resultado['cantidad_pasajeros'] = gdf_resultado[col_nombre].map(pasajeros).fillna(0).astype(int)
        gdf_resultado['cantidad_buses'] = gdf_resultado[col_nombre].map(buses).fillna(0).astype(int)
        gdf_resultado['promedio_pasajeros_diario'] = gdf_resultado[col_nombre].map(promedio_pasajeros).fillna(0.0).astype(float)
        gdf_resultado['promedio_buses_diario'] = gdf_resultado[col_nombre].map(promedio_buses).fillna(0.0).astype(float)
        gdf_resultado['empresas'] = gdf_resultado[col_nombre].map(empresas).fillna('')
        gdf_resultado['lineas'] = gdf_resultado[col_nombre].map(lineas).fillna('')
        if poblaciones:
            gdf_resultado['POBLACION'] = gdf_resultado[col_nombre].map(poblaciones)

        gdf_resultado['num_empresas'] = gdf_resultado['empresas'].apply(lambda x: len([e.strip() for e in x.split(',') if e.strip()]) if x else 0)
        gdf_resultado['num_lineas'] = gdf_resultado['lineas'].apply(lambda x: len([l.strip() for l in x.split(',') if l.strip()]) if x else 0)
        
        # Cargar relaciones empresa-línea desde cache si existen
        empresa_lineas_cache = {}
        linea_empresas_cache = {}
        for d in cache_data['areas']:
            if 'empresa_lineas' in d and d['empresa_lineas']:
                empresa_lineas_cache[d['nombre']] = d['empresa_lineas']
            if 'linea_empresas' in d and d['linea_empresas']:
                linea_empresas_cache[d['nombre']] = d['linea_empresas']
        
        if empresa_lineas_cache:
            gdf_resultado['empresa_lineas'] = gdf_resultado[col_nombre].map(
                lambda x: json.dumps(empresa_lineas_cache.get(x, {}))
            ).fillna(json.dumps({}))
        else:
            gdf_resultado['empresa_lineas'] = json.dumps({})
            
        if linea_empresas_cache:
            gdf_resultado['linea_empresas'] = gdf_resultado[col_nombre].map(
                lambda x: json.dumps(linea_empresas_cache.get(x, {}))
            ).fillna(json.dumps({}))
        else:
            gdf_resultado['linea_empresas'] = json.dumps({})

        totals = cache_data.get('totals', None)
        return gdf_resultado, True, totals

    return None, False, None

def obtener_franja_operativa(id_franja):
    """Obtiene los datos de una franja operativa desde la base de datos"""
    try:
        conn = psycopg2.connect(**DB_RUTAS_CONFIG)
        query = """
        SELECT 
            id_franja,
            denominacion,
            hora_inicio,
            hora_fin,
            id_tipo_dia,
            inicio_vigencia,
            fin_vigencia,
            activo
        FROM control_metricas.franjas_operativas
        WHERE id_franja = %s AND activo = true
        """
        df = pd.read_sql_query(query, conn, params=(id_franja,))
        conn.close()
        
        if len(df) == 0:
            return None
        
        franja = df.iloc[0].to_dict()
        # Mantener hora_inicio y hora_fin en su formato original (pueden ser timedelta, time, o string)
        # La función obtener_validaciones se encargará de convertirlos al formato correcto con minutos y segundos
        # NO los convertimos aquí para preservar toda la información de tiempo
        return franja
    except Exception as e:
        print(f"Error al obtener franja operativa: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def obtener_feriados(mes, anio):
    """Obtiene la lista de feriados del mes y año seleccionado desde la base de datos DB_RUTAS"""
    try:
        # Calcular fechas de inicio y fin del mes
        if mes == 12:
            fecha_inicio = f"{anio}-{mes:02d}-01"
            fecha_fin = f"{anio + 1}-01-01"
        else:
            fecha_inicio = f"{anio}-{mes:02d}-01"
            fecha_fin = f"{anio}-{mes + 1:02d}-01"
        
            conn_rutas = psycopg2.connect(**DB_RUTAS_CONFIG)
            query_feriados = """
            SELECT fecha 
            FROM public.feriados
            WHERE fecha >= %s AND fecha < %s
            ORDER BY fecha ASC
            """
            df_feriados = pd.read_sql_query(query_feriados, conn_rutas, params=(fecha_inicio, fecha_fin))
            conn_rutas.close()
            
            # Convertir fechas a formato YYYY-MM-DD
            feriados_list = []
            for _, row in df_feriados.iterrows():
                fecha = row['fecha']
                if pd.notna(fecha):
                    # Si es datetime, convertir a date
                    if hasattr(fecha, 'date'):
                        fecha = fecha.date()
                    elif isinstance(fecha, str):
                        fecha = fecha.split()[0]  # Tomar solo la parte de la fecha
                    feriados_list.append(str(fecha))
            
            print(f"✓ Feriados obtenidos para {mes}/{anio}: {len(feriados_list)} fechas")
            return feriados_list
    except Exception as e:
        print(f"⚠️ Error al obtener feriados: {e}")
        import traceback
        print(traceback.format_exc())
        return []

def obtener_validaciones(mes, anio, id_franja):
    """Obtiene las validaciones según la franja operativa seleccionada"""
    
    # Obtener datos de la franja operativa
    franja = obtener_franja_operativa(id_franja)
    if not franja:
        print(f"Error: No se encontró la franja operativa {id_franja}")
        return None
    
    denominacion = franja['denominacion']
    hora_inicio = franja['hora_inicio']
    hora_fin = franja['hora_fin']
    id_tipo_dia = franja['id_tipo_dia']
    
    # Convertir hora_inicio y hora_fin a formato TIME si vienen como objetos time o timedelta
    # Asegurar que sean strings en formato 'HH:MM:SS'
    from datetime import timedelta
    
    if isinstance(hora_inicio, timedelta):
        # Es un timedelta, convertir a string HH:MM:SS
        total_seconds = int(hora_inicio.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        hora_inicio_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif hasattr(hora_inicio, 'total_seconds'):
        # Es otro tipo de timedelta-like object
        total_seconds = int(hora_inicio.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        hora_inicio_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif isinstance(hora_inicio, str):
        # Ya es un string, verificar formato
        hora_inicio_str = hora_inicio.strip()
        # Si es solo un número, asumir que son horas
        if hora_inicio_str.isdigit():
            hora_inicio_str = f"{int(hora_inicio_str):02d}:00:00"
        # Si tiene formato HH:MM, agregar segundos
        elif hora_inicio_str.count(':') == 1:
            hora_inicio_str = hora_inicio_str + ':00'
        # Asegurar que tenga formato completo
        partes = hora_inicio_str.split(':')
        if len(partes) == 2:
            hora_inicio_str = hora_inicio_str + ':00'
    else:
        # Intentar convertir objeto time o datetime.time a string
        if hasattr(hora_inicio, 'hour'):
            # Es un objeto datetime.time
            hora_inicio_str = f"{hora_inicio.hour:02d}:{hora_inicio.minute:02d}:{hora_inicio.second:02d}"
        else:
            # Último recurso: convertir a string y parsear
            hora_str = str(hora_inicio).strip()
            if hora_str.isdigit():
                hora_inicio_str = f"{int(hora_str):02d}:00:00"
            else:
                hora_inicio_str = hora_str
    
    if isinstance(hora_fin, timedelta):
        # Es un timedelta, convertir a string HH:MM:SS
        total_seconds = int(hora_fin.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        hora_fin_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif hasattr(hora_fin, 'total_seconds'):
        # Es otro tipo de timedelta-like object
        total_seconds = int(hora_fin.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        hora_fin_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif isinstance(hora_fin, str):
        # Ya es un string, verificar formato
        hora_fin_str = hora_fin.strip()
        # Si es solo un número, asumir que son horas
        if hora_fin_str.isdigit():
            hora_fin_str = f"{int(hora_fin_str):02d}:00:00"
        # Si tiene formato HH:MM, agregar segundos
        elif hora_fin_str.count(':') == 1:
            hora_fin_str = hora_fin_str + ':00'
        # Asegurar que tenga formato completo
        partes = hora_fin_str.split(':')
        if len(partes) == 2:
            hora_fin_str = hora_fin_str + ':00'
    else:
        # Intentar convertir objeto time o datetime.time a string
        if hasattr(hora_fin, 'hour'):
            # Es un objeto datetime.time
            hora_fin_str = f"{hora_fin.hour:02d}:{hora_fin.minute:02d}:{hora_fin.second:02d}"
        else:
            # Último recurso: convertir a string y parsear
            hora_str = str(hora_fin).strip()
            if hora_str.isdigit():
                hora_fin_str = f"{int(hora_str):02d}:00:00"
            else:
                hora_fin_str = hora_str
    
    # Validar formato final (debe ser HH:MM:SS)
    try:
        # Validar que el formato sea correcto
        import re
        if not re.match(r'^\d{2}:\d{2}:\d{2}$', hora_inicio_str):
            raise ValueError(f"Formato de hora_inicio inválido: {hora_inicio_str}")
        if not re.match(r'^\d{2}:\d{2}:\d{2}$', hora_fin_str):
            raise ValueError(f"Formato de hora_fin inválido: {hora_fin_str}")
    except Exception as e:
        print(f"⚠️ Error al validar formato de hora: {e}")
        print(f"hora_inicio original: {hora_inicio}, convertido: {hora_inicio_str}")
        print(f"hora_fin original: {hora_fin}, convertido: {hora_fin_str}")
    
    print(f"✓ Horas convertidas: {hora_inicio_str} - {hora_fin_str}")
    
    # Obtener feriados desde DB_RUTAS para el mes y año seleccionado
    feriados_list = obtener_feriados(mes, anio)
    
    # Calcular fechas de inicio y fin del mes
    if mes == 12:
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio + 1}-01-01"
    else:
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio}-{mes + 1:02d}-01"
    
    # Inicializar parámetros de la query: fechas primero, luego horas, luego feriados
    query_params = [fecha_inicio, fecha_fin]
    
    # Construir condición de hora usando la parte TIME completa (horas, minutos y segundos)
    # Extraer la parte de tiempo del timestamp y compararla con hora_inicio y hora_fin
    # Si hora_fin es menor que hora_inicio, significa que cruza medianoche
    # En PostgreSQL se usa ::time para extraer la parte de tiempo
    
    # Validar que las horas estén en formato correcto antes de usarlas
    print(f"Validando horas: inicio='{hora_inicio_str}', fin='{hora_fin_str}'")
    
    if hora_fin_str >= hora_inicio_str:
        # Rango normal: ejemplo 05:00:00 a 07:59:59
        condicion_hora = "(fechahoraevento::time >= %s::time AND fechahoraevento::time <= %s::time)"
        query_params.extend([hora_inicio_str, hora_fin_str])
    else:
        # Rango que cruza medianoche: ejemplo 22:00:00 a 02:00:00
        condicion_hora = "(fechahoraevento::time >= %s::time OR fechahoraevento::time <= %s::time)"
        query_params.extend([hora_inicio_str, hora_fin_str])
    
    # Construir filtro según tipo de día
    # DOW en PostgreSQL: 0=Domingo, 1=Lunes, ..., 6=Sábado
    # Los feriados van DESPUÉS de las horas en la query
    filtro_tipo_dia = ""
    
    if id_tipo_dia == 5:  # LABORAL (Lunes a Viernes)
        # Días laborales: lunes(1) a viernes(5), excluyendo feriados
        if feriados_list:
            # Crear lista de fechas para excluir
            feriados_placeholders = ','.join(['%s'] * len(feriados_list))
            filtro_tipo_dia = f"""
            AND EXTRACT(DOW FROM fechahoraevento) IN (1,2,3,4,5)
            AND DATE(fechahoraevento) NOT IN ({feriados_placeholders})
            """
            query_params.extend(feriados_list)
        else:
            filtro_tipo_dia = """
            AND EXTRACT(DOW FROM fechahoraevento) IN (1,2,3,4,5)
            """
    elif id_tipo_dia == 6:  # SÁBADO
        # Sábados, excluyendo feriados que caen en sábado
        if feriados_list:
            feriados_placeholders = ','.join(['%s'] * len(feriados_list))
            filtro_tipo_dia = f"""
            AND EXTRACT(DOW FROM fechahoraevento) = 6
            AND DATE(fechahoraevento) NOT IN ({feriados_placeholders})
            """
            query_params.extend(feriados_list)
        else:
            filtro_tipo_dia = """
            AND EXTRACT(DOW FROM fechahoraevento) = 6
            """
    elif id_tipo_dia == 7:  # NO LABORAL (Domingos y Feriados)
        # Domingos (DOW = 0) O fechas en tabla de feriados
        if feriados_list:
            feriados_placeholders = ','.join(['%s'] * len(feriados_list))
            filtro_tipo_dia = f"""
            AND (
                EXTRACT(DOW FROM fechahoraevento) = 0
                OR DATE(fechahoraevento) IN ({feriados_placeholders})
            )
            """
            query_params.extend(feriados_list)
        else:
            filtro_tipo_dia = """
            AND EXTRACT(DOW FROM fechahoraevento) = 0
            """
    else:
        # Por defecto, no filtrar por tipo de día
        filtro_tipo_dia = ""
    
    query = f"""
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
    AND {condicion_hora}
    {filtro_tipo_dia}
    AND tipoevento IN (4,8)
    AND latitude IS NOT NULL
    AND longitude IS NOT NULL
    -- INICIO DE LA OPTIMIZACIÓN GEOGRÁFICA
    AND (latitude BETWEEN -26.00 AND -25.00 AND longitude BETWEEN -58.00 AND -57.00)
    -- FIN DE LA OPTIMIZACIÓN GEOGRÁFICA
    ORDER BY idsam, consecutivoevento, serialmediopago, fechahoraevento DESC;
    """
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        # Ejecutar query con todos los parámetros
        df = pd.read_sql_query(query, conn, params=tuple(query_params))
        conn.close()
        print(f"Validaciones obtenidas ({denominacion}): {len(df)}")
        return df
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        import traceback
        print(traceback.format_exc())
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
        AND permisionario IS TRUE
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
                # Obtener líneas únicas (convertir a string para consistencia)
                lineas = sorted([str(l) for l in rutas_intersectan['linea'].unique().tolist()])
                
                # Crear diccionario empresa -> líneas para tooltips
                empresa_lineas_dict = {}
                for _, ruta in rutas_intersectan.iterrows():
                    empresa = ruta['nombre_eot']
                    linea = str(ruta['linea'])
                    if empresa not in empresa_lineas_dict:
                        empresa_lineas_dict[empresa] = []
                    if linea not in empresa_lineas_dict[empresa]:
                        empresa_lineas_dict[empresa].append(linea)
                
                # Ordenar líneas dentro de cada empresa
                for empresa in empresa_lineas_dict:
                    empresa_lineas_dict[empresa] = sorted(empresa_lineas_dict[empresa])
                
                # Crear diccionario línea -> empresas para tooltips
                linea_empresas_dict = {}
                for _, ruta in rutas_intersectan.iterrows():
                    linea = str(ruta['linea'])
                    empresa = ruta['nombre_eot']
                    if linea not in linea_empresas_dict:
                        linea_empresas_dict[linea] = []
                    if empresa not in linea_empresas_dict[linea]:
                        linea_empresas_dict[linea].append(empresa)
                
                # Ordenar empresas dentro de cada línea
                for linea in linea_empresas_dict:
                    linea_empresas_dict[linea] = sorted(linea_empresas_dict[linea])
                
                resultados[idx] = {
                    'empresas': ', '.join(empresas),
                    'lineas': ', '.join(lineas),
                    'num_empresas': len(empresas),
                    'num_lineas': len(lineas),
                    'empresa_lineas': empresa_lineas_dict,  # Diccionario empresa -> [líneas]
                    'linea_empresas': linea_empresas_dict   # Diccionario línea -> [empresas]
                }
            else:
                resultados[idx] = {
                    'empresas': '',
                    'lineas': '',
                    'num_empresas': 0,
                    'num_lineas': 0,
                    'empresa_lineas': {},  # Diccionario vacío
                    'linea_empresas': {}   # Diccionario vacío
                }
        
        return resultados
        
    except Exception as e:
        print(f"⚠️ Error al obtener empresas y líneas: {e}")
        import traceback
        print(traceback.format_exc())
        return {}

def asignar_validaciones_a_areas(df_validaciones, gdf_areas, col_nombre):
    """Asigna cada validación a su área correspondiente y cuenta validaciones, pasajeros y buses únicos"""
    # Validar que col_nombre existe en gdf_areas
    if col_nombre not in gdf_areas.columns:
        raise ValueError(f"La columna '{col_nombre}' no existe en gdf_areas. Columnas disponibles: {list(gdf_areas.columns)}")
    
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
    
    # Verificar que col_nombre esté presente después del spatial join
    if col_nombre not in validaciones_con_area.columns:
        raise ValueError(f"La columna '{col_nombre}' no está presente después del spatial join. Columnas disponibles: {list(validaciones_con_area.columns)}")
    
    # Contar validaciones por área
    conteo_validaciones = validaciones_con_area.groupby(col_nombre).size().reset_index(name='cantidad_validaciones')
    
    # Contar pasajeros únicos (serialmediopago distintos) por área
    conteo_pasajeros = validaciones_con_area.groupby(col_nombre)['serialmediopago'].nunique().reset_index(name='cantidad_pasajeros')
    
    # Contar buses únicos (idsam distintos) por área
    conteo_buses = validaciones_con_area.groupby(col_nombre)['idsam'].nunique().reset_index(name='cantidad_buses')
    
    # Calcular promedios diarios: extraer la fecha de fechahoraevento
    validaciones_con_area['fecha'] = pd.to_datetime(validaciones_con_area['fechahoraevento']).dt.date
    
    # Contar buses únicos por área y por día
    buses_por_dia = validaciones_con_area.groupby([col_nombre, 'fecha'])['idsam'].nunique().reset_index(name='buses_dia')
    promedio_buses = buses_por_dia.groupby(col_nombre)['buses_dia'].mean().reset_index(name='promedio_buses_diario')
    promedio_buses['promedio_buses_diario'] = promedio_buses['promedio_buses_diario'].round(1)
    
    # Contar pasajeros únicos por área y por día
    pasajeros_por_dia = validaciones_con_area.groupby([col_nombre, 'fecha'])['serialmediopago'].nunique().reset_index(name='pasajeros_dia')
    promedio_pasajeros = pasajeros_por_dia.groupby(col_nombre)['pasajeros_dia'].mean().reset_index(name='promedio_pasajeros_diario')
    promedio_pasajeros['promedio_pasajeros_diario'] = promedio_pasajeros['promedio_pasajeros_diario'].round(1)
    
    # Unir todos los conteos
    conteo_completo = conteo_validaciones.merge(conteo_pasajeros, on=col_nombre, how='outer')
    conteo_completo = conteo_completo.merge(conteo_buses, on=col_nombre, how='outer')
    conteo_completo = conteo_completo.merge(promedio_buses, on=col_nombre, how='outer')
    conteo_completo = conteo_completo.merge(promedio_pasajeros, on=col_nombre, how='outer')
    
    # Unir con geometrías
    gdf_resultado = gdf_areas.merge(conteo_completo, on=col_nombre, how='left')
    gdf_resultado['cantidad_validaciones'] = gdf_resultado['cantidad_validaciones'].fillna(0).astype(int)
    gdf_resultado['cantidad_pasajeros'] = gdf_resultado['cantidad_pasajeros'].fillna(0).astype(int)
    gdf_resultado['cantidad_buses'] = gdf_resultado['cantidad_buses'].fillna(0).astype(int)
    gdf_resultado['promedio_buses_diario'] = gdf_resultado['promedio_buses_diario'].fillna(0.0).astype(float)
    gdf_resultado['promedio_pasajeros_diario'] = gdf_resultado['promedio_pasajeros_diario'].fillna(0.0).astype(float)
    
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
            # Guardar relaciones como JSON para el frontend
            gdf_resultado.at[idx, 'empresa_lineas'] = json.dumps(empresas_lineas[idx].get('empresa_lineas', {}))
            gdf_resultado.at[idx, 'linea_empresas'] = json.dumps(empresas_lineas[idx].get('linea_empresas', {}))
        else:
            gdf_resultado.at[idx, 'empresas'] = ''
            gdf_resultado.at[idx, 'lineas'] = ''
            gdf_resultado.at[idx, 'num_empresas'] = 0
            gdf_resultado.at[idx, 'num_lineas'] = 0
            gdf_resultado.at[idx, 'empresa_lineas'] = json.dumps({})
            gdf_resultado.at[idx, 'linea_empresas'] = json.dumps({})
    
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
        color = '#cccc'
        
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
    # Agregar vías principales de central y asunción usando la función que maneja errores
    try:
        gdf_vias, col_nombre_vias = cargar_vias()
        if not gdf_vias.empty:
            for idx, row in gdf_vias.iterrows():
                nombre = row['NOMBRE'] if pd.notna(row.get('NOMBRE', None)) else "Sin nombre"
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
    except Exception as e:
        print(f"⚠ No se pudieron cargar las vías para el mapa inicial: {e}")
    
    return mapa._repr_html_()
    
def crear_leyenda_mapa_calor(min_val, max_val, tipo='validaciones'):
    """Crea una leyenda de mapa de calor personalizada"""
    
    titulos = {
        'validaciones': 'Validaciones',
        'porcentaje': 'Penetración (%)',
        'buses': 'Buses Únicos',
        'lineas': 'Líneas de Transporte'
    }
    titulo = titulos.get(tipo, 'Validaciones')
    
    # Calcular rangos
    rango = max_val - min_val
    if rango == 0:
        rangos = [(min_val, min_val, '#cccc')]
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
        if tipo == 'porcentaje':
            leyenda_html += f"""
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 30px; height: 20px; background-color: {color}; 
                            border: 1px solid black; margin-right: 10px;"></div>
                <span>{inicio:.1f}% - {fin:.1f}%</span>
            </div>
            """
        else:
            leyenda_html += f"""
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 30px; height: 20px; background-color: {color}; 
                            border: 1px solid black; margin-right: 10px;"></div>
                <span>{int(inicio):,} - {int(fin):,}</span>
            </div>
            """
    
    leyenda_html += "</div>"
    
    return leyenda_html

def crear_mapa_con_datos(gdf_resultado, col_nombre, col_nombre_simple, incluir_barrios, criterio='validaciones'):
    """Crea el mapa interactivo con datos de validaciones"""
    # Calcular centro del mapa
    bounds = gdf_resultado.total_bounds
    centro = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Crear mapa base
    zoom_inicial = 10 if not incluir_barrios else 11
    mapa = folium.Map(location=centro, zoom_start=zoom_inicial, tiles='OpenStreetMap')
    
    # Determinar qué métrica usar para el color
    if criterio == 'validaciones':
        valores = gdf_resultado['cantidad_validaciones']
    elif criterio == 'porcentaje':
        # Calcular penetración: (pasajeros / población) * 100
        gdf_resultado['penetracion'] = (gdf_resultado['cantidad_pasajeros'] / gdf_resultado['POBLACION'] * 100).fillna(0)
        valores = gdf_resultado['penetracion']
    elif criterio == 'buses':
        valores = gdf_resultado['cantidad_buses']
    elif criterio == 'lineas':
        valores = gdf_resultado['num_lineas']
    else:
        valores = gdf_resultado['cantidad_validaciones']
    
    max_valor = valores.max()
    min_valor = valores[valores > 0].min() if (valores > 0).any() else 0
    
    # Agregar cada área al mapa
    for idx, row in gdf_resultado.iterrows():
        nombre_completo = row[col_nombre] if pd.notna(row[col_nombre]) else "Sin nombre"
        nombre_simple = row[col_nombre_simple] if col_nombre_simple and pd.notna(row[col_nombre_simple]) else nombre_completo
        
        cantidad_validaciones = row['cantidad_validaciones']
        cantidad_pasajeros = row['cantidad_pasajeros']
        cantidad_buses = row['cantidad_buses']
        num_empresas = row.get('num_empresas', 0)
        num_lineas = row.get('num_lineas', 0)
        
        if criterio == 'validaciones':
            valor_actual = cantidad_validaciones
        elif criterio == 'porcentaje':
            valor_actual = row.get('penetracion', 0)
        elif criterio == 'buses':
            valor_actual = cantidad_buses
        elif criterio == 'lineas':
            valor_actual = num_lineas
        else:
            valor_actual = cantidad_validaciones
        
        # Color basado en el valor actual (escala turquesa)
        if max_valor > 0 and valor_actual > 0:
            intensidad = valor_actual / max_valor
            
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
            color = '#cccc'  # Gris para áreas sin datos
        
        # Tooltip con información completa
        tipo_area = "Barrio" if incluir_barrios else "Distrito"
        
        poblacion_text = ""
        if 'POBLACION' in row and pd.notna(row['POBLACION']):
            poblacion_text = f"&nbsp;&nbsp;• Población: {int(row['POBLACION']):,}<br>"
        
        tooltip_text = f"""
        <div style="font-family: Arial; font-size: 13px; min-width: 250px;">
            <b style="font-size: 14px;">{nombre_completo}</b><br>
            <span style="font-size: 11px; color: #666;">({tipo_area})</span>
            <hr style="margin: 5px 0;">
            <b>📊 DEMANDA:</b><br>
            &nbsp;&nbsp;• Validaciones: {cantidad_validaciones:,}<br>
            &nbsp;&nbsp;• Pasajeros únicos: {cantidad_pasajeros:,}<br>
            {poblacion_text}
            <b>🚌 OFERTA:</b><br>
            &nbsp;&nbsp;• Buses únicos: {cantidad_buses:,}<br>
            &nbsp;&nbsp;• Empresas: {num_empresas}<br>
            &nbsp;&nbsp;• Líneas: {num_lineas}
        </div>
        """
        
        peso_linea = 1 if incluir_barrios else 2
        
        folium.GeoJson(
            row['geometry'].__geo_interface__,
            style_function=lambda x, color=color, peso=peso_linea: {
                'fillColor': color,
                'color': 'white',
                'weight': peso,
                'fillOpacity': 0.8
            },
            highlight_function=lambda x: {
                'color': '#0000ff',
                'weight': 5,
                'fillOpacity': 1
            },
            tooltip=folium.Tooltip(tooltip_text, sticky=True)
        ).add_to(mapa)
    
    if max_valor > 0:
        leyenda_html = crear_leyenda_mapa_calor(min_valor, max_valor, criterio)
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
    <!-- comentar esto<h1>📊 Análisis de Validaciones - Central, Asunción y Presidente Hayes</h1> -->
    <h1>📊 Análisis de Validaciones - Asunción y Departamento Central</h1>
    <p class="subtitle">
    <span id="horario-badge" class="info-badge">Selecciona una franja operativa</span>
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
    <label for="id_franja">Franja Operativa:</label>
    <select id="id_franja">
    <option value="">Cargando franjas...</option>
    </select>
    </div>
    
    <div class="form-group">
    <label>&nbsp;</label>
    <div class="checkbox-group">
    <input type="checkbox" id="incluir_barrios" name="incluir_barrios">
    <label for="incluir_barrios">🏘️ Incluir Barrios</label>
    </div>
    </div>

    <div class="form-group">
    <label for="criterio_mapa">Criterio Mapa:</label>
    <select id="criterio_mapa">
        <option value="validaciones">📊 Validaciones</option>
        <option value="porcentaje">📈 Penetración (%)</option>
        <option value="buses">🚌 Buses</option>
        <option value="lineas">🛣️ Líneas</option>
    </select>
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
    // Variables globales para franjas
    let franjasData = [];
    let franjaSeleccionada = null;
    
    // Establecer mes y año actual por defecto
    const fechaActual = new Date();
    document.getElementById('mes').value = fechaActual.getMonth() + 1;
    document.getElementById('anio').value = fechaActual.getFullYear();
    
    // Cargar franjas operativas al iniciar
    async function cargarFranjas() {
        try {
            const response = await fetch('/api/franjas_operativas');
            const data = await response.json();
            
            if (data.franjas && data.franjas.length > 0) {
                franjasData = data.franjas;
                const selectFranja = document.getElementById('id_franja');
                selectFranja.innerHTML = '';
                
                // Agregar opciones al selector
                franjasData.forEach(franja => {
                    const horaInicio = franja.hora_inicio.substring(0, 5);
                    const horaFin = franja.hora_fin.substring(0, 5);
                    const option = document.createElement('option');
                    option.value = franja.id_franja;
                    option.textContent = `${franja.denominacion} (${horaInicio} - ${horaFin}) - ${franja.tipo_dia_descripcion}`;
                    selectFranja.appendChild(option);
                });
                
                // Seleccionar Pico Mañana por defecto si existe
                const picoManana = franjasData.find(f => 
                    f.denominacion.toLowerCase().includes('pico mañana') || 
                    f.denominacion.toLowerCase().includes('pico manana')
                );
                if (picoManana) {
                    selectFranja.value = picoManana.id_franja;
                    actualizarBadge(picoManana);
                } else if (franjasData.length > 0) {
                    selectFranja.value = franjasData[0].id_franja;
                    actualizarBadge(franjasData[0]);
                }
            } else {
                document.getElementById('id_franja').innerHTML = '<option value="">No hay franjas disponibles</option>';
            }
        } catch (error) {
            console.error('Error al cargar franjas:', error);
            document.getElementById('id_franja').innerHTML = '<option value="">Error al cargar franjas</option>';
        }
    }
    
    // Actualizar badge de horario al cambiar selector
    function actualizarBadge(franja) {
    const horarioBadge = document.getElementById('horario-badge');
        const horaInicio = franja.hora_inicio.substring(0, 5);
        const horaFin = franja.hora_fin.substring(0, 5);
        horarioBadge.textContent = `${franja.denominacion}: ${horaInicio} - ${horaFin}`;
        franjaSeleccionada = franja;
    }
    
    document.getElementById('id_franja').addEventListener('change', function() {
        const franjaId = parseInt(this.value);
        const franja = franjasData.find(f => f.id_franja === franjaId);
        if (franja) {
            actualizarBadge(franja);
        }
    });
    
    // Cargar franjas al iniciar
    cargarFranjas();
    
    async function obtenerDatos() {
    const mes = document.getElementById('mes').value;
    const anio = document.getElementById('anio').value;
        const id_franja = document.getElementById('id_franja').value;
    const incluir_barrios = document.getElementById('incluir_barrios').checked;
    const criterio_mapa = document.getElementById('criterio_mapa').value;
    const btnObtener = document.getElementById('btnObtener');
    const loading = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const cacheIndicator = document.getElementById('cache-indicator');
        
        if (!id_franja) {
            errorDiv.textContent = '❌ Por favor selecciona una franja operativa';
            errorDiv.style.display = 'block';
            return;
        }
    
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
                    id_franja: parseInt(id_franja),
    incluir_barrios: incluir_barrios,
    criterio_mapa: criterio_mapa
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
        id_franja = int(data['id_franja'])
        incluir_barrios = data.get('incluir_barrios', False)
        criterio_mapa = data.get('criterio_mapa', 'validaciones')
        
        # Obtener información de la franja operativa
        franja = obtener_franja_operativa(id_franja)
        if not franja:
            return jsonify({'error': f'No se encontró la franja operativa {id_franja}'})
        
        denominacion_franja = franja['denominacion']
        
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
        gdf_resultado, desde_cache, _ = cargar_cache(mes, anio, id_franja, incluir_barrios, gdf_base, col_nombre)
        
        # Variables para totals
        total_validaciones = 0
        total_pasajeros = 0
        total_buses = 0
        
        if not desde_cache:
            # No hay cache, obtener de la base de datos
            print(f"No hay cache para {mes}/{anio} (franja {id_franja}: {denominacion_franja}, {tipo_area}), consultando base de datos...")
            df_validaciones = obtener_validaciones(mes, anio, id_franja)
            
            if df_validaciones is None or len(df_validaciones) == 0:
                return jsonify({'error': 'No se encontraron validaciones para el período seleccionado'})
            
            # Calcular totals antes de asignar a áreas
            total_validaciones = int(len(df_validaciones))
            total_pasajeros = int(df_validaciones['serialmediopago'].nunique())
            total_buses = int(df_validaciones['idsam'].nunique())
            
            # Asignar validaciones a áreas
            gdf_resultado = asignar_validaciones_a_areas(df_validaciones, gdf_base, col_nombre)
            
            # Preparar totals para guardar en cache
            totals_global = {
                'validaciones': total_validaciones,
                'unique_passengers': total_pasajeros,
                'unique_buses': total_buses
            }
            
            # Guardar en cache con totals
            try:
                guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre, totals_global)
            except TypeError:
                guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre)
        else:
            # Viene desde cache, intentar obtener totals del cache
            _, _, totals_cache = cargar_cache(mes, anio, id_franja, incluir_barrios, gdf_base, col_nombre)
            if totals_cache and totals_cache.get('unique_passengers') is not None:
                total_validaciones = totals_cache.get('validaciones', int(gdf_resultado['cantidad_validaciones'].sum()))
                total_pasajeros = totals_cache.get('unique_passengers', 0)
                total_buses = totals_cache.get('unique_buses', 0)
            else:
                # Recalcular totals desde BD si no están en cache
                df_validaciones = obtener_validaciones(mes, anio, id_franja)
                if df_validaciones is not None and len(df_validaciones) > 0:
                    total_validaciones = int(len(df_validaciones))
                    total_pasajeros = int(df_validaciones['serialmediopago'].nunique())
                    total_buses = int(df_validaciones['idsam'].nunique())
                else:
                    total_validaciones = int(gdf_resultado['cantidad_validaciones'].sum())
                    total_pasajeros = 0
                    total_buses = 0
        
        # Crear mapa con datos y criterio seleccionado
        mapa_html = crear_mapa_con_datos(gdf_resultado, col_nombre, col_nombre_simple, incluir_barrios, criterio_mapa)
        
        # Crear tabla
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        # Formatear horario desde la franja
        hora_inicio_display = str(franja['hora_inicio']).split(':')[0] if ':' in str(franja['hora_inicio']) else str(franja['hora_inicio'])
        hora_fin_display = str(franja['hora_fin']).split(':')[0] if ':' in str(franja['hora_fin']) else str(franja['hora_fin'])
        horario_texto = f"{denominacion_franja} ({hora_inicio_display}:00 - {hora_fin_display}:59)"
        tipo_area_texto = "Barrio" if incluir_barrios else "Distrito"
        
        gdf_ordenado = gdf_resultado.sort_values('cantidad_validaciones', ascending=False)
        
        limite = 50 if incluir_barrios else len(gdf_ordenado)
        
        barrios_unicos = sorted(gdf_ordenado[col_nombre].dropna().unique())
        empresas_unicas = set()
        lineas_unicas = set()
        
        for idx, row in gdf_ordenado.iterrows():
            empresas_str = row.get('empresas', '')
            lineas_str = row.get('lineas', '')
            
            if empresas_str:
                empresas_unicas.update([e.strip() for e in empresas_str.split(',') if e.strip()])
            if lineas_str:
                lineas_unicas.update([l.strip() for l in lineas_str.split(',') if l.strip()])
        
        empresas_unicas = sorted(empresas_unicas)
        lineas_unicas = sorted(lineas_unicas)
        
        opciones_barrios = ''.join([f'<option value="{barrio}">{barrio}</option>' for barrio in barrios_unicos])
        opciones_empresas = ''.join([f'<option value="{empresa}">{empresa}</option>' for empresa in empresas_unicas])
        opciones_lineas = ''.join([f'<option value="{linea}">{linea}</option>' for linea in lineas_unicas])
        
        tabla_html = f"""
        <h2>Análisis de Demanda y Oferta por {tipo_area_texto} - {meses[mes]} {anio}</h2>
        <p style="color: #666; margin-bottom: 10px;">
        <b>Horario Pico:</b> {horario_texto} | 
        <b>Total Validaciones:</b> {total_validaciones:,} | 
        <b>Total Pasajeros Únicos:</b> {total_pasajeros:,} | 
        <b>Total Buses Únicos:</b> {total_buses:,}
        {' | <span style="color: #28a745;">⚡ Datos desde caché</span>' if desde_cache else ''}
        </p>
        
        <!-- Filtros -->
        <div class="filtros-container" style="margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 8px;">
        <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
        <span style="color: white; font-weight: bold;">Filtros:</span>
        <select id="filtro-barrio" style="padding: 5px 10px; border-radius: 5px; border: none; background: rgba(255,255,255,0.9);">
        <option value="">Todos los {tipo_area_texto}s</option>
        {opciones_barrios}
        </select>
        <select id="filtro-empresa" style="padding: 5px 10px; border-radius: 5px; border: none; background: rgba(255,255,255,0.9);">
        <option value="">Todas las empresas</option>
        {opciones_empresas}
        </select>
        <select id="filtro-linea" style="padding: 5px 10px; border-radius: 5px; border: none; background: rgba(255,255,255,0.9);">
        <option value="">Todas las líneas</option>
        {opciones_lineas}
        </select>
        <button onclick="limpiarFiltros()" style="padding: 5px 15px; border-radius: 5px; border: none; background: #dc3545; color: white; cursor: pointer;">Limpiar filtros</button>
        </div>
        </div>
        
        <table id="tabla-datos">
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
        
        filas_tabla = ""
        for idx, row in gdf_ordenado.head(limite).iterrows():
            nombre = row[col_nombre] if pd.notna(row[col_nombre]) else "Sin nombre"
            cantidad_validaciones = row['cantidad_validaciones']
            cantidad_pasajeros = row['cantidad_pasajeros']
            cantidad_buses = row['cantidad_buses']
            empresas = row.get('empresas', '')
            lineas = row.get('lineas', '')
            
            porcentaje_validaciones = (cantidad_validaciones / total_validaciones * 100) if total_validaciones > 0 else 0
            porcentaje_pasajeros = (cantidad_pasajeros / total_pasajeros * 100) if total_pasajeros > 0 else 0
            
            empresas_display = empresas if len(empresas) <= 30 else empresas[:27] + '...'
            lineas_display = lineas if len(lineas) <= 30 else lineas[:27] + '...'
            
            filas_tabla += f"""
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
            filas_tabla += f"""
            <tr>
            <td colspan="8" style="text-align: center; color: #999; font-style: italic;">
            Mostrando top {limite} de {len(gdf_ordenado)} barrios
            </td>
            </tr>
            """
        
        tabla_html += f"""
        {filas_tabla}
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
        
        <script>
        function limpiarFiltros() {{
            document.getElementById('filtro-barrio').value = '';
            document.getElementById('filtro-empresa').value = '';
            document.getElementById('filtro-linea').value = '';
            filtrarTabla();
        }}
        
        function filtrarTabla() {{
            const filtroBarrio = document.getElementById('filtro-barrio').value.toLowerCase();
            const filtroEmpresa = document.getElementById('filtro-empresa').value.toLowerCase();
            const filtroLinea = document.getElementById('filtro-linea').value.toLowerCase();
            
            const tabla = document.getElementById('tabla-datos');
            if (!tabla) return;
            
            const filas = tabla.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
            
            for (let i = 0; i < filas.length; i++) {{
                const fila = filas[i];
                if (fila.classList.contains('total-row')) continue;
                
                const celdaBarrio = fila.cells[0].textContent.toLowerCase();
                const celdaEmpresas = fila.cells[6].textContent.toLowerCase();
                const celdaLineas = fila.cells[7].textContent.toLowerCase();
                
                const cumpleBarrio = !filtroBarrio || celdaBarrio.includes(filtroBarrio);
                const cumpleEmpresa = !filtroEmpresa || celdaEmpresas.includes(filtroEmpresa);
                const cumpleLinea = !filtroLinea || celdaLineas.includes(filtroLinea);
                
                fila.style.display = (cumpleBarrio && cumpleEmpresa && cumpleLinea) ? '' : 'none';
            }}
        }}
        
        // Función para inicializar los filtros
        function inicializarFiltros() {{
            const filtroBarrio = document.getElementById('filtro-barrio');
            const filtroEmpresa = document.getElementById('filtro-empresa');
            const filtroLinea = document.getElementById('filtro-linea');
            
            if (filtroBarrio) filtroBarrio.addEventListener('change', filtrarTabla);
            if (filtroEmpresa) filtroEmpresa.addEventListener('change', filtrarTabla);
            if (filtroLinea) filtroLinea.addEventListener('change', filtrarTabla);
        }}
        
        inicializarFiltros();
        </script>
        """
        
        return jsonify({
            'mapa': mapa_html,
            'tabla': tabla_html,
            'desde_cache': desde_cache,
            'totals': {
                'unique_passengers': int(total_pasajeros),
                'unique_buses': int(total_buses),
                'total_validaciones': int(total_validaciones)
            }
        })
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)})

@app.route('/api/franjas_operativas', methods=['GET'])
def api_franjas_operativas():
    """Obtiene todas las franjas operativas activas"""
    print(f"📡 Solicitud recibida para /api/franjas_operativas")
    try:
        print(f"🔌 Conectando a base de datos: {DB_RUTAS_CONFIG.get('host')}/{DB_RUTAS_CONFIG.get('database')}")
        conn = psycopg2.connect(**DB_RUTAS_CONFIG)
        print(f"✓ Conexión exitosa a la base de datos")
        query = """
        SELECT 
            fo.id_franja,
            fo.denominacion,
            fo.hora_inicio,
            fo.hora_fin,
            fo.id_tipo_dia,
            td.codigo as tipo_dia_codigo,
            td.descripcion as tipo_dia_descripcion
        FROM control_metricas.franjas_operativas fo
        INNER JOIN control_metricas.tipo_dia td ON fo.id_tipo_dia = td.id_tipo_dia
        WHERE fo.activo = true
        AND td.activo = true
        AND (fo.inicio_vigencia IS NULL OR fo.inicio_vigencia <= CURRENT_DATE)
        AND (fo.fin_vigencia IS NULL OR fo.fin_vigencia >= CURRENT_DATE)
        ORDER BY fo.id_franja ASC
        """
        print(f"📊 Ejecutando consulta SQL...")
        df = pd.read_sql_query(query, conn)
        conn.close()
        print(f"✓ Consulta ejecutada exitosamente. Filas obtenidas: {len(df)}")
        
        if len(df) == 0:
            print("⚠️ No se encontraron franjas operativas activas en la base de datos")
            return jsonify({'franjas': []}), 200
        
        franjas = []
        for _, row in df.iterrows():
            try:
                # Manejar diferentes formatos de hora
                hora_inicio_val = row['hora_inicio']
                hora_fin_val = row['hora_fin']
                
                # Convertir a string para el display
                if isinstance(hora_inicio_val, str):
                    hora_inicio_str = hora_inicio_val.split(':')[0] if ':' in hora_inicio_val else hora_inicio_val
                    hora_inicio_display = hora_inicio_str
                elif hasattr(hora_inicio_val, 'hour'):
                    hora_inicio_str = f"{hora_inicio_val.hour:02d}:{hora_inicio_val.minute:02d}"
                    hora_inicio_display = f"{hora_inicio_val.hour:02d}"
                else:
                    hora_inicio_str = str(hora_inicio_val)
                    hora_inicio_display = hora_inicio_str.split(':')[0] if ':' in hora_inicio_str else hora_inicio_str
                
                if isinstance(hora_fin_val, str):
                    hora_fin_str = hora_fin_val.split(':')[0] if ':' in hora_fin_val else hora_fin_val
                    hora_fin_display = hora_fin_str
                elif hasattr(hora_fin_val, 'hour'):
                    hora_fin_str = f"{hora_fin_val.hour:02d}:{hora_fin_val.minute:02d}"
                    hora_fin_display = f"{hora_fin_val.hour:02d}"
                else:
                    hora_fin_str = str(hora_fin_val)
                    hora_fin_display = hora_fin_str.split(':')[0] if ':' in hora_fin_str else hora_fin_str
                
                franjas.append({
                    'id_franja': int(row['id_franja']),
                    'denominacion': str(row['denominacion']),
                    'hora_inicio': hora_inicio_str,
                    'hora_fin': hora_fin_str,
                    'hora_inicio_display': hora_inicio_display,
                    'hora_fin_display': hora_fin_display,
                    'id_tipo_dia': int(row['id_tipo_dia']),
                    'tipo_dia_codigo': str(row['tipo_dia_codigo']),
                    'tipo_dia_descripcion': str(row['tipo_dia_descripcion'])
                })
            except Exception as e:
                print(f"⚠️ Error procesando franja {row.get('id_franja', 'unknown')}: {e}")
                import traceback
                print(traceback.format_exc())
                continue
        
        print(f"✓ Franjas operativas cargadas: {len(franjas)}")
        if len(franjas) == 0:
            print("⚠️ No se encontraron franjas operativas después del procesamiento")
            return jsonify({'franjas': []}), 200
        
        print(f"✓ Franjas operativas cargadas: {len(franjas)}")
        return jsonify({'franjas': franjas})
    except psycopg2.Error as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"❌ Error de base de datos en api_franjas_operativas:")
        print(f"   Error: {str(e)}")
        print(f"   Traceback completo: {error_msg}")
        return jsonify({'error': f'Error de base de datos: {str(e)}', 'details': str(e)}), 500
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"❌ Error en api_franjas_operativas:")
        print(f"   Error: {str(e)}")
        print(f"   Traceback completo: {error_msg}")
        return jsonify({'error': str(e), 'details': error_msg}), 500

@app.route('/api/validaciones', methods=['POST'])
def api_validaciones():
    """
    Devuelve GeoJSON con todas las propiedades ya calculadas para que
    el frontend React pueda renderizar y recolorear localmente.
    Request body JSON: { mes: int, anio: int, id_franja: int, incluir_barrios: bool }
    """
    try:
        print(f"\n📡 Solicitud recibida en /api/validaciones")
        data = request.json or {}
        print(f"   Datos recibidos: {data}")
        mes = int(data.get('mes', datetime.now().month))
        anio = int(data.get('anio', datetime.now().year))
        id_franja = int(data.get('id_franja'))
        incluir_barrios = bool(data.get('incluir_barrios', False))
        print(f"   Parámetros: mes={mes}, anio={anio}, id_franja={id_franja}, incluir_barrios={incluir_barrios}")

        # Validar que se proporcione id_franja
        if not id_franja:
            return jsonify({'error': 'id_franja es requerido'}), 400

        # Obtener información de la franja operativa
        franja = obtener_franja_operativa(id_franja)
        if not franja:
            return jsonify({'error': f'No se encontró la franja operativa {id_franja}'}), 400

        # Selecciona la capa base
        print(f"   Seleccionando capa base (incluir_barrios={incluir_barrios})...")
        if incluir_barrios:
            if gdf_barrios is None:
                print(f"   ❌ Error: gdf_barrios es None")
                return jsonify({'error': 'No se encontró el shapefile de barrios'}), 400
            if columna_nombre_barrio is None:
                print(f"   ❌ Error: columna_nombre_barrio es None")
                return jsonify({'error': 'Columna de nombre de barrios no está inicializada'}), 500
            gdf_base = gdf_barrios
            col_nombre = columna_nombre_barrio
            print(f"   ✓ Usando barrios: {len(gdf_base)} barrios, col_nombre='{col_nombre}'")
        else:
            if gdf_distritos is None:
                print(f"   ❌ Error: gdf_distritos es None")
                return jsonify({'error': 'No se encontró el shapefile de distritos'}), 400
            if columna_nombre_distrito is None:
                print(f"   ❌ Error: columna_nombre_distrito es None")
                return jsonify({'error': 'Columna de nombre de distritos no está inicializada'}), 500
            gdf_base = gdf_distritos
            col_nombre = columna_nombre_distrito
            print(f"   ✓ Usando distritos: {len(gdf_base)} distritos, col_nombre='{col_nombre}'")
        
        # Validar que col_nombre existe en gdf_base
        print(f"   Verificando columna '{col_nombre}' en gdf_base...")
        print(f"   Columnas disponibles en gdf_base: {list(gdf_base.columns)}")
        if col_nombre not in gdf_base.columns:
            print(f"   ❌ Error: La columna '{col_nombre}' no existe en el GeoDataFrame base")
            print(f"   Tipo de área: {'barrios' if incluir_barrios else 'distritos'}")
            print(f"   Columnas disponibles: {gdf_base.columns.tolist()}")
            return jsonify({'error': f'Columna de nombre "{col_nombre}" no encontrada en los datos base. Columnas disponibles: {list(gdf_base.columns)}'}), 500
        print(f"   ✓ Columna '{col_nombre}' encontrada en gdf_base")

        # Intentar cargar cache
        print(f"   Intentando cargar desde cache...")
        # Nota: cargar_cache puede devolver (gdf_resultado, desde_cache) o (gdf_resultado, desde_cache, totals_cache)
        cargar_cache_result = cargar_cache(mes, anio, id_franja, incluir_barrios, gdf_base, col_nombre)
        gdf_resultado = None
        desde_cache = False
        totals_cache = None

        if isinstance(cargar_cache_result, tuple):
            if len(cargar_cache_result) == 2:
                gdf_resultado, desde_cache = cargar_cache_result
                print(f"   Cache devolvió 2 valores: desde_cache={desde_cache}")
            elif len(cargar_cache_result) == 3:
                gdf_resultado, desde_cache, totals_cache = cargar_cache_result
                print(f"   Cache devolvió 3 valores: desde_cache={desde_cache}, totals_cache={totals_cache is not None}")
            else:
                print(f"   ⚠️ Cache devolvió tupla con {len(cargar_cache_result)} valores (inesperado)")
        else:
            # por seguridad, si la función retornó algo inesperado
            print(f"   ⚠️ Cache devolvió algo inesperado: {type(cargar_cache_result)}")
            gdf_resultado, desde_cache = None, False

        totals_global = None
        df_validaciones = None

        print(f"   Estado después de cargar cache: gdf_resultado={'existe' if gdf_resultado is not None else 'None'}, desde_cache={desde_cache}")
        if not desde_cache or gdf_resultado is None:
            print(f"   No hay cache válido, consultando base de datos...")
            # No hay cache o no se construyó correctamente -> consultar DB
            try:
                df_validaciones = obtener_validaciones(mes, anio, id_franja)
                if df_validaciones is None:
                    # Si obtener_validaciones retorna None, puede ser un error de BD o no hay datos
                    # Lanzar excepción para que sea capturada por el bloque except general
                    raise Exception('Error al obtener validaciones de la base de datos. Verifique la conexión y el espacio disponible en PostgreSQL.')
                if len(df_validaciones) == 0:
                    raise Exception('No se encontraron validaciones para el período seleccionado')
            except psycopg2_errors.DiskFull as e:
                # Error específico de espacio en disco
                error_msg = f'Error: El servidor de base de datos se quedó sin espacio en disco. Por favor contacte al administrador del sistema. Detalles: {str(e)}'
                print(f"❌ {error_msg}")
                return jsonify({'error': error_msg, 'details': str(e)}), 500
            except psycopg2.Error as e:
                # Otros errores de PostgreSQL
                error_msg = f'Error de base de datos: {str(e)}'
                print(f"❌ {error_msg}")
                return jsonify({'error': error_msg, 'details': str(e)}), 500

            # Totales verdaderos (globales) calculados sobre el dataframe original
            total_validaciones = int(len(df_validaciones))
            unique_passengers = int(df_validaciones['serialmediopago'].nunique())
            unique_buses = int(df_validaciones['idsam'].nunique())

            totals_global = {
                'validaciones': total_validaciones,
                'unique_passengers': unique_passengers,
                'unique_buses': unique_buses,
                'desde_cache': False
            }

            # Asignar validaciones a áreas
            gdf_resultado = asignar_validaciones_a_areas(df_validaciones, gdf_base, col_nombre)

            # Guardar cache: intento pasar totals_global si la función guardar_cache acepta ese parámetro
            try:
                guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre, totals_global)
            except TypeError:
                # versión anterior de guardar_cache sin totals -> llamar sin totals
                guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre)

        else:
            # cargado desde cache
            if totals_cache and totals_cache.get('unique_passengers') is not None:
                totals_global = totals_cache
                totals_global['desde_cache'] = True
            else:
                # si no hay totals en cache o están incompletos, recalcular desde DB
                print(f"Totals no encontrados en cache para {mes}/{anio}, recalculando desde BD...")
                df_validaciones = obtener_validaciones(mes, anio, id_franja)
                if df_validaciones is not None and len(df_validaciones) > 0:
                    total_validaciones = int(len(df_validaciones))
                    unique_passengers = int(df_validaciones['serialmediopago'].nunique())
                    unique_buses = int(df_validaciones['idsam'].nunique())
                    totals_global = {
                        'validaciones': total_validaciones,
                        'unique_passengers': unique_passengers,
                        'unique_buses': unique_buses,
                        'desde_cache': True  # datos desde cache pero totals recalculados
                    }
                    # Actualizar cache con los totals calculados
                    try:
                        guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre, totals_global)
                    except TypeError:
                        guardar_cache(mes, anio, id_franja, incluir_barrios, gdf_resultado, col_nombre)
                else:
                    # fallback si no se pueden obtener los datos
                    totals_global = {
                    'validaciones': int(gdf_resultado['cantidad_validaciones'].sum()),
                    'unique_passengers': None,
                    'unique_buses': None,
                    'desde_cache': True
                }

        # Opcional: simplificar geometría para reducir payload (ajusta tolerance)
        try:
            gdf_send = gdf_resultado.copy()
            gdf_send['geometry'] = gdf_send['geometry'].simplify(0.00012)
        except Exception:
            gdf_send = gdf_resultado

        # Validar que col_nombre existe en el GeoDataFrame
        if col_nombre not in gdf_send.columns:
            print(f"⚠️ Error: La columna '{col_nombre}' no existe en el GeoDataFrame")
            print(f"Columnas disponibles: {gdf_send.columns.tolist()}")
            return jsonify({'error': f'Columna de nombre no encontrada en los datos: {col_nombre}'}), 500
        
        # Agrupar áreas duplicadas por nombre (puede haber múltiples geometrías con el mismo nombre)
        # Esto asegura que cada área tenga un solo registro con valores consolidados
        if col_nombre in gdf_send.columns:
            print(f"Verificando áreas duplicadas antes de consolidar...")
            duplicados = gdf_send.groupby(col_nombre).size()
            duplicados = duplicados[duplicados > 1]
            if len(duplicados) > 0:
                print(f"⚠️ Encontradas {len(duplicados)} áreas con múltiples geometrías. Consolidando...")
                # Agrupar por nombre y consolidar valores
                grupos_consolidados = []
                for nombre, grupo in gdf_send.groupby(col_nombre):
                    if len(grupo) == 1:
                        grupos_consolidados.append(grupo.iloc[0])
                    else:
                        # Consolidar múltiples registros con el mismo nombre
                        primer_registro = grupo.iloc[0].copy()
                        # Sumar valores numéricos
                        primer_registro['cantidad_validaciones'] = grupo['cantidad_validaciones'].sum()
                        primer_registro['cantidad_pasajeros'] = grupo['cantidad_pasajeros'].sum()
                        primer_registro['cantidad_buses'] = grupo['cantidad_buses'].sum()
                        # Para promedios diarios, promediar los promedios (promedio de promedios)
                        if 'promedio_pasajeros_diario' in grupo.columns:
                            promedios_pasajeros = grupo['promedio_pasajeros_diario'].dropna()
                            if len(promedios_pasajeros) > 0:
                                primer_registro['promedio_pasajeros_diario'] = round(promedios_pasajeros.mean(), 1)
                        if 'promedio_buses_diario' in grupo.columns:
                            promedios_buses = grupo['promedio_buses_diario'].dropna()
                            if len(promedios_buses) > 0:
                                primer_registro['promedio_buses_diario'] = round(promedios_buses.mean(), 1)
                        # Para empresas y líneas, combinar listas únicas
                        empresas_unicas = set()
                        lineas_unicas = set()
                        for _, row in grupo.iterrows():
                            if pd.notna(row.get('empresas')) and row.get('empresas'):
                                empresas_unicas.update([e.strip() for e in str(row['empresas']).split(',') if e.strip()])
                            if pd.notna(row.get('lineas')) and row.get('lineas'):
                                lineas_unicas.update([l.strip() for l in str(row['lineas']).split(',') if l.strip()])
                        primer_registro['empresas'] = ', '.join(sorted(empresas_unicas))
                        primer_registro['lineas'] = ', '.join(sorted(lineas_unicas))
                        primer_registro['num_empresas'] = len(empresas_unicas)
                        primer_registro['num_lineas'] = len(lineas_unicas)
                        # Para población, tomar el máximo (o el primero si son iguales)
                        if 'POBLACION' in grupo.columns:
                            poblaciones = grupo['POBLACION'].dropna()
                            if len(poblaciones) > 0:
                                primer_registro['POBLACION'] = poblaciones.max() if poblaciones.max() > 0 else poblaciones.iloc[0]
                        # Consolidar relaciones empresa-línea si existen
                        if 'empresa_lineas' in grupo.columns or 'linea_empresas' in grupo.columns:
                            empresa_lineas_consolidado = {}
                            linea_empresas_consolidado = {}
                            for _, row in grupo.iterrows():
                                try:
                                    if pd.notna(row.get('empresa_lineas')) and row.get('empresa_lineas'):
                                        el_dict = json.loads(row['empresa_lineas']) if isinstance(row['empresa_lineas'], str) else row['empresa_lineas']
                                        for emp, lin in el_dict.items():
                                            if emp not in empresa_lineas_consolidado:
                                                empresa_lineas_consolidado[emp] = set()
                                            empresa_lineas_consolidado[emp].update(lin if isinstance(lin, list) else [lin])
                                    if pd.notna(row.get('linea_empresas')) and row.get('linea_empresas'):
                                        le_dict = json.loads(row['linea_empresas']) if isinstance(row['linea_empresas'], str) else row['linea_empresas']
                                        for lin, emp_list in le_dict.items():
                                            if lin not in linea_empresas_consolidado:
                                                linea_empresas_consolidado[lin] = set()
                                            linea_empresas_consolidado[lin].update(emp_list if isinstance(emp_list, list) else [emp_list])
                                except:
                                    pass
                            # Convertir sets a listas ordenadas
                            empresa_lineas_consolidado = {k: sorted(list(v)) for k, v in empresa_lineas_consolidado.items()}
                            linea_empresas_consolidado = {k: sorted(list(v)) for k, v in linea_empresas_consolidado.items()}
                            primer_registro['empresa_lineas'] = json.dumps(empresa_lineas_consolidado)
                            primer_registro['linea_empresas'] = json.dumps(linea_empresas_consolidado)
                        grupos_consolidados.append(primer_registro)
                
                if grupos_consolidados:
                    gdf_send = gpd.GeoDataFrame(grupos_consolidados, crs=gdf_send.crs)
                    print(f"✓ Consolidación completada. {len(gdf_resultado)} registros → {len(gdf_send)} registros únicos")

        # Precalcular penetración si hay POBLACION
        if 'POBLACION' in gdf_send.columns:
            # evitar división por cero
            gdf_send['penetracion'] = (gdf_send['cantidad_pasajeros'] / gdf_send['POBLACION'].replace({0: pd.NA}) * 100).fillna(0)
        else:
            gdf_send['penetracion'] = 0

        stats = {
            'validaciones': {
                'min': int(gdf_send['cantidad_validaciones'].min()),
                'max': int(gdf_send['cantidad_validaciones'].max())
            },
            'porcentaje': {
                'min': float(gdf_send['penetracion'].min()),
                'max': float(gdf_send['penetracion'].max())
            },
            'buses': {
                'min': int(gdf_send['cantidad_buses'].min()),
                'max': int(gdf_send['cantidad_buses'].max())
            },
            'empresas': {
                'min': int(gdf_send['num_empresas'].min()) if 'num_empresas' in gdf_send.columns else 0,
                'max': int(gdf_send['num_empresas'].max()) if 'num_empresas' in gdf_send.columns else 0
            },
            'lineas': {
                'min': int(gdf_send['num_lineas'].min()) if 'num_lineas' in gdf_send.columns else 0,
                'max': int(gdf_send['num_lineas'].max()) if 'num_lineas' in gdf_send.columns else 0
            }
        }

        # Convertir a GeoJSON (dict)
        geojson = json.loads(gdf_send.to_json())

        # Totales a devolver: preferir totals_global (calculado sobre df_validaciones)
        if totals_global is None:
            # fallback: sumar por área (solo si no hay otra opción)
            totals = {
                'validaciones': int(gdf_send['cantidad_validaciones'].sum()),
                'pasajeros': int(gdf_send['cantidad_pasajeros'].sum()),
                'buses': int(gdf_send['cantidad_buses'].sum()),
                'desde_cache': desde_cache
            }
        else:
            # normalizar nombres para frontend (mantener compatibilidad)
            totals = {
                'validaciones': int(totals_global.get('validaciones', 0)),
                'unique_passengers': int(totals_global.get('unique_passengers')) if totals_global.get('unique_passengers') is not None else None,
                'unique_buses': int(totals_global.get('unique_buses')) if totals_global.get('unique_buses') is not None else None,
                'desde_cache': bool(totals_global.get('desde_cache', desde_cache))
            }

        print(f"   ✓ Datos enviados exitosamente: {len(geojson.get('features', []))} features")
        return jsonify({'geojson': geojson, 'totals': totals, 'stats': stats})

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Error en /api/validaciones:")
        print(f"   Error: {str(e)}")
        print(f"   Traceback completo:\n{error_traceback}")
        return jsonify({'error': str(e), 'details': error_traceback}), 500

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
    
    app.run(debug=True, host='0.0.0.0', port=5000)