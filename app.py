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
data_fallas_adultas = cargar_datos("D:/culo/falles-fallas.csv", 'Falla Adulta', columnas_renombrar_adultas)
data_fallas_infantiles = cargar_datos("D:/culo/falles-infantils-fallas-infantiles.csv", 'Falla Infantil', columnas_renombrar_infantiles)
data_carpas_falleras = cargar_datos("D:/culo/carpes-falles-carpas-fallas.csv", 'Carpa Fallera', {})

# Concatenar las fallas adultas e infantiles para obtener nombres de fallas de carpas
data_fallas = pd.concat([data_fallas_adultas, data_fallas_infantiles], ignore_index=True)

# Añadir nombres de fallas a las carpas falleras
data_carpas_falleras = data_carpas_falleras.merge(data_fallas_adultas[['Id. Falla', 'Nom / Nombre']], on='Id. Falla', how='left')

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
st.title("Fallas de Valencia")

# Crear cliente de OpenRouteService
ors_client = openrouteservice.Client(key='5b3ce3597851110001cf624898e24b3bf3774e8a92088a276b847d49')  # Reemplaza '5b3ce3597851110001cf624898e24b3bf3774e8a92088a276b847d49' con tu clave de OpenRouteService

# Barra lateral con las opciones para ir a cada sección
seccion = st.sidebar.selectbox("Selecciona la sección", ["Buscar Falla Más Cercana", "Calcular Ruta Turística"])

if seccion == "Buscar Falla Más Cercana":
    st.header("Buscar Falla Más Cercana")

    direccion = st.text_input("Introduce tu dirección")

    tipo_falla_seleccionada = st.selectbox("Selecciona el tipo de falla", ['Todas', 'Falla Adulta', 'Falla Infantil', 'Carpa Fallera'])
    
    # Solo mostrar opción de categoría si no es Carpa Fallera
    if tipo_falla_seleccionada != 'Carpa Fallera':
        categoria_seleccionada = st.selectbox("Selecciona la categoría de falla", ['Todas'] + list(data['Secció / Seccion'].unique()))

    # Filtrar los datos según el tipo de falla y la categoría seleccionados
    data_filtrada = data
    if tipo_falla_seleccionada != 'Todas':
        data_filtrada = data[data['Tipo Falla'] == tipo_falla_seleccionada]
    if tipo_falla_seleccionada != 'Carpa Fallera' and 'categoria_seleccionada' in locals() and categoria_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'] == categoria_seleccionada]

    if st.button("Buscar Falla Más Cercana"):
        if direccion:
            geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza '763ed800dfa0492ebffca31d51cf54a4' con tu clave de OpenCageGeocode
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

    if 'falla_cercana' in st.session_state:
        falla_cercana = st.session_state['falla_cercana']
        ubicacion_usuario = st.session_state['ubicacion_usuario']

        with st.expander("Falla Más Cercana", expanded=True):
            if falla_cercana['Tipo Falla'] == 'Carpa Fallera':
                nombre_falla = falla_cercana['Nom / Nombre']
                st.write(f"Nombre de la Carpa: {nombre_falla}")
            else:
                st.write(f"Nombre: {falla_cercana.get('Nom / Nombre', 'N/A')}")
                st.write(f"Tipo: {falla_cercana.get('Tipo Falla', 'N/A')}")
                st.write(f"Sección: {falla_cercana.get('Secció / Seccion', 'N/A')}")
                if falla_cercana['Tipo Falla'] != 'Falla Infantil':
                    any_fundacio = falla_cercana.get('Any_Fundacio', 'N/A')
                    st.write(f"Año de Fundación: {int(any_fundacio) if pd.notna(any_fundacio) else 'N/A'}")
                    st.write(f"Distintivo: {falla_cercana.get('Distintiu / Distintivo', 'N/A')}")
                esbos_url = falla_cercana.get('Esbos', None)
                if isinstance(esbos_url, str) and esbos_url.startswith("http"):
                    st.image(esbos_url, caption="Esbós")

        # Evitar que el mapa se actualice constantemente
        if 'mapa_falla_cercana' not in st.session_state:
            ruta_geojson = obtener_ruta_con_calles(pd.DataFrame([falla_cercana]), ubicacion_usuario, ors_client)
            m = folium.Map(location=ubicacion_usuario, zoom_start=14)
            folium.Marker([ubicacion_usuario[0], ubicacion_usuario[1]], popup="Tu Ubicación", icon=folium.Icon(color="blue")).add_to(m)
            if falla_cercana['Tipo Falla'] == 'Carpa Fallera':
                folium.Marker([falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon']], popup=nombre_falla).add_to(m)
            else:
                folium.Marker([falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon']], popup=falla_cercana['Nom / Nombre']).add_to(m)
            folium.GeoJson(ruta_geojson, name='route').add_to(m)
            folium.LayerControl().add_to(m)
            st.session_state['mapa_falla_cercana'] = m

        st_folium(st.session_state['mapa_falla_cercana'], width=700, height=500)

elif seccion == "Calcular Ruta Turística":
    st.header("Calcular Ruta Turística")

    direccion = st.text_input("Introduce tu dirección")

    tipo_falla_seleccionada = st.selectbox("Selecciona el tipo de falla", ['Todas', 'Falla Adulta', 'Falla Infantil', 'Carpa Fallera'])
    
    # Solo mostrar opción de categoría si no es Carpa Fallera
    if tipo_falla_seleccionada != 'Carpa Fallera':
        categoria_seleccionada = st.selectbox("Selecciona la categoría de falla", ['Todas'] + list(data['Secció / Seccion'].unique()))

    distancia_maxima = st.number_input("Distancia máxima de la ruta (km)", min_value=1, value=5)

    # Filtrar los datos según el tipo de falla y la categoría seleccionados
    data_filtrada = data
    if tipo_falla_seleccionada != 'Todas':
        data_filtrada = data[data['Tipo Falla'] == tipo_falla_seleccionada]
    if tipo_falla_seleccionada != 'Carpa Fallera' and 'categoria_seleccionada' in locals() and categoria_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'] == categoria_seleccionada]

    if st.button("Calcular Ruta Turística"):
        if direccion:
            geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza '763ed800dfa0492ebffca31d51cf54a4' con tu clave de OpenCageGeocode
            results = geocoder.geocode(direccion)
            if results:
                lat, lon = results[0]['geometry']['lat'], results[0]['geometry']['lng']
                ubicacion_usuario = (float(lat), float(lon))
                ruta_turistica = calcular_ruta_turistica(data_filtrada, ubicacion_usuario, distancia_maxima, ors_client)
                # Guardar la información de la ruta turística en session_state
                st.session_state['ruta_turistica'] = ruta_turistica
                st.session_state['ubicacion_usuario'] = ubicacion_usuario
                st.session_state['direccion'] = direccion
                # Obtener la ruta con calles reales
                ruta_geojson = obtener_ruta_con_calles(ruta_turistica, ubicacion_usuario, ors_client)
                st.session_state['ruta_geojson'] = ruta_geojson
            else:
                st.error("No se pudo encontrar la ubicación. Por favor, intenta de nuevo.")
        else:
            st.error("Por favor, introduce una dirección.")

    if 'ruta_turistica' in st.session_state and 'ruta_geojson' in st.session_state:
        ruta_turistica = st.session_state['ruta_turistica']
        ruta_geojson = st.session_state['ruta_geojson']
        ubicacion_usuario = st.session_state['ubicacion_usuario']
        with st.expander("Ruta Turística", expanded=True):
            st.write("Fallas en la ruta:")
            # Excluir las columnas de año de fundación y distintivo para las fallas infantiles
            columnas_mostrar = ['Nom / Nombre', 'distancia_acumulada']
            if tipo_falla_seleccionada == 'Todas':
                columnas_mostrar += ['Tipo Falla']
            st.dataframe(ruta_turistica[columnas_mostrar])
            
            # Mostrar mapa con la ruta
            m = folium.Map(location=ubicacion_usuario, zoom_start=14)
            folium.Marker([ubicacion_usuario[0], ubicacion_usuario[1]], popup="Tu Ubicación", icon=folium.Icon(color="blue")).add_to(m)

            for index, row in ruta_turistica.iterrows():
                if row['Tipo Falla'] == 'Carpa Fallera':
                    nombre_falla = row['Nom / Nombre']
                    folium.Marker([row['geo_point_2d_lat'], row['geo_point_2d_lon']], popup=nombre_falla).add_to(m)
                else:
                    folium.Marker([row['geo_point_2d_lat'], row['geo_point_2d_lon']], popup=row['Nom / Nombre']).add_to(m)

            folium.GeoJson(ruta_geojson, name='route').add_to(m)
            folium.LayerControl().add_to(m)
            st_folium(m, width=700, height=500)
