import streamlit as st
import pandas as pd
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import folium
from streamlit_folium import st_folium
import openrouteservice

# Función para encontrar la falla más cercana
def falla_mas_cercana(data, ubicacion_usuario):
    data['distancia'] = data.apply(lambda row: geodesic(ubicacion_usuario, (row['geo_point_2d_lat'], row['geo_point_2d_lon'])).km, axis=1)
    falla_cercana = data.loc[data['distancia'].idxmin()]
    return falla_cercana

# Función para cargar y procesar los datos, estandarizando nombres de columnas
def cargar_datos(ruta, tipo_falla, columnas_renombrar):
    data = pd.read_csv(ruta, delimiter=';')
    data[['geo_point_2d_lat', 'geo_point_2d_lon']] = data['geo_point_2d'].str.split(',', expand=True).astype(float)
    data['Tipo Falla'] = tipo_falla
    data.rename(columns=columnas_renombrar, inplace=True)
    return data

# Diccionarios para renombrar columnas
columnas_renombrar_adultas = {
    'Esbós / Lema': 'Esbos',
    'Anyo Fundació / Año Fundacion': 'Any_Fundacio'
}
columnas_renombrar_infantiles = {
    'Esbós / Boceto': 'Esbos',
    'Any Fundació / Año Fundacion': 'Any_Fundacio'
}

# Cargar los datos
data_fallas_adultas = cargar_datos("falles-fallas.csv", 'Falla Adulta', columnas_renombrar_adultas)
data_fallas_infantiles = cargar_datos("falles-infantils-fallas-infantiles.csv", 'Falla Infantil', columnas_renombrar_infantiles)
data_carpas_falleras = cargar_datos("carpes-falles-carpas-fallas.csv", 'Carpa Fallera', {})

# Unir todas las bases de datos
data = pd.concat([data_fallas_adultas, data_fallas_infantiles, data_carpas_falleras], ignore_index=True)

# Función para calcular la ruta turística acumulando distancias
def calcular_ruta_turistica(data, ubicacion_usuario, distancia_maxima, ors_client):
    data['distancia'] = data.apply(lambda row: geodesic(ubicacion_usuario, (row['geo_point_2d_lat'], row['geo_point_2d_lon'])).km, axis=1)
    fallas_cercanas = data.sort_values(by='distancia')
    
    ruta = []
    distancia_acumulada = 0.0
    ubicacion_actual = ubicacion_usuario

    for _, falla in fallas_cercanas.iterrows():
        distancia_a_falla = geodesic(ubicacion_actual, (falla['geo_point_2d_lat'], falla['geo_point_2d_lon'])).km
        if distancia_acumulada + distancia_a_falla > distancia_maxima:
            break
        distancia_acumulada += distancia_a_falla
        falla['distancia_acumulada'] = distancia_acumulada
        ruta.append(falla)
        ubicacion_actual = (falla['geo_point_2d_lat'], falla['geo_point_2d_lon'])

    return pd.DataFrame(ruta)

# Función para obtener la ruta con calles reales usando OpenRouteService
def obtener_ruta_con_calles(data, ubicacion_usuario, ors_client):
    coordenadas = [(ubicacion_usuario[1], ubicacion_usuario[0])]  # ORS usa (lon, lat)
    for index, row in data.iterrows():
        coordenadas.append((row['geo_point_2d_lon'], row['geo_point_2d_lat']))

    ruta = ors_client.directions(
        coordinates=coordenadas,
        profile='foot-walking',
        format='geojson'
    )
    return ruta

# Título de la aplicación
st.title("Fallas Más Cercanas y Ruta Turística")

# Pedir la ubicación del usuario
st.sidebar.header("Tu Ubicación")
direccion = st.sidebar.text_input("Introduce tu dirección")

# Seleccionar tipo de falla
tipo_falla_seleccionada = st.sidebar.selectbox("Selecciona el tipo de falla", ['Todas', 'Falla Adulta', 'Falla Infantil', 'Carpa Fallera'])

# Seleccionar categoría de falla
categorias_falla = data['Secció / Seccion'].unique()
categoria_seleccionada = st.sidebar.selectbox("Selecciona la categoría de falla", ['Todas'] + list(categorias_falla))

# Filtrar los datos según el tipo de falla seleccionado
data_filtrada = data
if tipo_falla_seleccionada != 'Todas':
    data_filtrada = data[data['Tipo Falla'] == tipo_falla_seleccionada]

# Filtrar los datos según la categoría seleccionada
if categoria_seleccionada != 'Todas':
    data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'] == categoria_seleccionada]

# Distancia máxima para la ruta turística
distancia_maxima = st.sidebar.number_input("Introduce la distancia máxima (km) para la ruta turística", min_value=0.0, step=1.0)

# Crear cliente de OpenRouteService
ors_client = openrouteservice.Client(key='5b3ce3597851110001cf624898e24b3bf3774e8a92088a276b847d49')  # Reemplaza 'TU_API_KEY' con tu clave de OpenRouteService

# Calcular la ruta turística cuando se hace clic en el botón
if st.sidebar.button("Calcular Ruta Turística"):
    if 'direccion' in st.session_state:
        direccion = st.session_state['direccion']
        geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza 'TU_API_KEY' con tu clave de OpenCageGeocode
        results = geocoder.geocode(direccion)
        if results:
            lat, lon = results[0]['geometry']['lat'], results[0]['geometry']['lng']
            ubicacion_usuario = (float(lat), float(lon))
            ruta_turistica = calcular_ruta_turistica(data_filtrada, ubicacion_usuario, distancia_maxima, ors_client)
            # Guardar la información de la ruta turística en session_state
            st.session_state['ruta_turistica'] = ruta_turistica
            st.session_state['ubicacion_usuario'] = ubicacion_usuario
        else:
            st.error("No se pudo encontrar la ubicación. Por favor, intenta de nuevo.")
    else:
        st.error("Por favor, primero busca una dirección para calcular la ruta turística.")

