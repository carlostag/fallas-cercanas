import streamlit as st
import pandas as pd
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import folium
from streamlit_folium import st_folium
import openrouteservice
from openrouteservice import convert

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

# Buscar la falla más cercana cuando se hace clic en el botón
if st.sidebar.button("Buscar Falla Más Cercana"):
    if direccion:
        geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza 'TU_API_KEY' con tu clave de OpenCageGeocode
        results = geocoder.geocode(direccion)
        if results:
            lat, lon = results[0]['geometry']['lat'], results[0]['geometry']['lng']
            ubicacion_usuario = (float(lat), float(lon))
            falla_cercana = falla_mas_cercana(data_filtrada, ubicacion_usuario)
            # Guardar la información de la falla más cercana en session_state
            st.session_state['falla_cercana'] = falla_cercana
            st.session_state['ubicacion_usuario'] = ubicacion_usuario
            st.session_state['direccion'] = direccion
        else:
            st.error("No se pudo encontrar la ubicación. Por favor, intenta de nuevo.")
    else:
        st.error("Por favor, introduce una dirección.")

# Calcular la ruta turística cuando se hace clic en el botón
if st.sidebar.button("Calcular Ruta Turística"):
    if direccion:
        geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza 'TU_API_KEY' con tu clave de OpenCageGeocode
        results = geocoder.geocode(direccion)
        if results:
            lat, lon = results[0]['geometry']['lat'], results[0]['geometry']['lng']
            ubicacion_usuario = (float(lat), float(lon))
            ruta_turistica = calcular_ruta_turistica(data_filtrada, ubicacion_usuario, distancia_maxima, ors_client)
            # Guardar la información de la ruta turística en session_state
            st.session_state['ruta_turistica'] = ruta_turistica
            st.session_state['ubicacion_usuario'] = ubicacion_usuario
            st.session_state['direccion'] = direccion
        else:
            st.error("No se pudo encontrar la ubicación. Por favor, intenta de nuevo.")
    else:
        st.error("Por favor, introduce una dirección.")

# Mostrar resultados si hay una falla cercana guardada en session_state
if 'falla_cercana' in st.session_state:
    falla_cercana = st.session_state['falla_cercana']
    ubicacion_usuario = st.session_state['ubicacion_usuario']
    with st.expander("Falla Más Cercana", expanded=True):
        if falla_cercana['Tipo Falla'] == 'Carpa Fallera':
            # Obtener el nombre de la falla a la que pertenece la carpa
            id_falla = falla_cercana['Id. Falla']  # Ajustar este campo al nombre correcto del ID
            nombre_falla = data_fallas_adultas.loc[data_fallas_adultas['Id. Falla'] == id_falla, 'Nom / Nombre'].values[0]  # Ajustar el nombre del campo ID si es diferente
            st.write(f"Nombre de la Carpa: {nombre_falla}")
            st.write(f"Tipo: {falla_cercana['Tipo Falla']}")
            st.write(f"Dirección: {falla_cercana['Adreça / Dirección']}")
            st.write(f"Sección: {falla_cercana['Secció / Seccion']}")
            any_fundacio = int(falla_cercana['Any_Fundacio']) if pd.notna(falla_cercana['Any_Fundacio']) else 'N/A'
            st.write(f"Año de Fundación: {any_fundacio}")
        else:
            st.write(f"Nombre: {falla_cercana['Nom / Nombre']}")
            st.write(f"Tipo: {falla_cercana['Tipo Falla']}")
            st.write(f"Dirección: {falla_cercana['Adreça / Dirección']}")
            st.write(f"Sección: {falla_cercana['Secció / Seccion']}")
            any_fundacio = int(falla_cercana['Any_Fundacio']) if pd.notna(falla_cercana['Any_Fundacio']) else 'N/A'
            st.write(f"Año de Fundación: {any_fundacio}")
            st.write(f"Distintivo: {falla_cercana['Distintiu / Distintivo']}")
            esbos_url = falla_cercana['Esbos']
            if isinstance(esbos_url, str) and esbos_url.startswith("http"):
                st.image(esbos_url, caption="Esbós / Boceto")
            else:
                st.write(f"Esbós: {'N/A' if not esbos_url else esbos_url}")
            st.write(f"Falla Experimental: {'SI' if falla_cercana['Falla Experimental'] == 1 else 'NO'}")

        # Mostrar mapa con la ubicación
        m = folium.Map(location=ubicacion_usuario, zoom_start=14)
        folium.Marker([ubicacion_usuario[0], ubicacion_usuario[1]], popup="Tu Ubicación", icon=folium.Icon(color="blue")).add_to(m)
        folium.Marker([falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon']], popup=falla_cercana['Nom / Nombre']).add_to(m)
        st_folium(m, width=700, height=500)

# Mostrar la ruta turística si hay una guardada en session_state
if 'ruta_turistica' in st.session_state:
    ruta_turistica = st.session_state['ruta_turistica']
    ubicacion_usuario = st.session_state['ubicacion_usuario']
    with st.expander("Ruta Turística", expanded=True):
        st.write("Fallas en la ruta:")
        st.dataframe(ruta_turistica[['Nom / Nombre', 'distancia_acumulada']])
        
        # Obtener la ruta con calles reales
        ruta_geojson = obtener_ruta_con_calles(ruta_turistica, ubicacion_usuario, ors_client)
        
        # Mostrar mapa con la ruta
        m = folium.Map(location=ubicacion_usuario, zoom_start=14)
        folium.Marker([ubicacion_usuario[0], ubicacion_usuario[1]], popup="Tu Ubicación", icon=folium.Icon(color="blue")).add_to(m)
        
        for index, row in ruta_turistica.iterrows():
            folium.Marker([row['geo_point_2d_lat'], row['geo_point_2d_lon']], popup=row['Nom / Nombre']).add_to(m)
        
        folium.GeoJson(ruta_geojson, name='route').add_to(m)
        folium.LayerControl().add_to(m)
        
        st_folium(m, width=700, height=500)

# Mostrar lista de fallas ordenadas por distancia según el tipo y la categoría seleccionados
if 'ubicacion_usuario' in st.session_state:
    ubicacion_usuario = st.session_state['ubicacion_usuario']
    data_filtrada['distancia'] = data_filtrada.apply(lambda row: geodesic(ubicacion_usuario, (row['geo_point_2d_lat'], row['geo_point_2d_lon'])).km, axis=1)
    data_filtrada = data_filtrada.sort_values(by='distancia')

    # Mostrar las 5 fallas más cercanas en el mapa
    st.header(f"Las 5 {tipo_falla_seleccionada.lower()}s más cercanas a ti")
    m = folium.Map(location=ubicacion_usuario, zoom_start=14)
    folium.Marker([ubicacion_usuario[0], ubicacion_usuario[1]], popup="Tu Ubicación", icon=folium.Icon(color="blue")).add_to(m)
    for i, row in data_filtrada.head(5).iterrows():
        folium.Marker([row['geo_point_2d_lat'], row['geo_point_2d_lon']], popup=row['Nom / Nombre'], icon=folium.Icon(color="red")).add_to(m)
    st_folium(m, width=700, height=500)

    # Mostrar la tabla de fallas ordenadas por distancia
    st.header(f"Lista de {tipo_falla_seleccionada.lower()}s")
    st.dataframe(data_filtrada[['Nom / Nombre', 'distancia']])
