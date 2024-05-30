
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
def obtener_ruta_con_calles(coordenadas, ors_client):
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

# Botones de funcionalidad en el sidebar
st.sidebar.header("Selecciona la funcionalidad")
if st.sidebar.button("Buscar Falla Más Cercana", key="buscar_falla"):
    st.session_state.seccion = "Buscar Falla Más Cercana"
if st.sidebar.button("Calcular Ruta Turística", key="calcular_ruta"):
    st.session_state.seccion = "Calcular Ruta Turística"

# Manejo de la sección seleccionada
if 'seccion' in st.session_state:
    seccion = st.session_state.seccion
else:
    seccion = "Buscar Falla Más Cercana"

if seccion == "Buscar Falla Más Cercana":
    st.header("Buscar Falla Más Cercana")

    direccion = st.text_input("Introduce tu dirección")

    tipo_falla_seleccionada = st.selectbox("Selecciona el tipo de falla", ['Todas', 'Falla Adulta', 'Falla Infantil', 'Carpa Fallera'])
    
    # Mostrar categorías solo para el tipo de falla seleccionado
    if tipo_falla_seleccionada == 'Falla Adulta':
        categorias = sorted(data_fallas_adultas['Secció / Seccion'].astype(str).unique())
    elif tipo_falla_seleccionada == 'Falla Infantil':
        # Convertir todos los valores a str para evitar errores de comparación
        categorias_infantiles = data_fallas_infantiles['Secció / Seccion'].astype(str).unique()
        categorias_infantiles = [c for c in categorias_infantiles if c not in ['FC', 'IE']]  # Filtrar categorías incorrectas
        
        # Ordenar considerando números y cadenas
        def sort_key(x):
            try:
                return int(x)
            except ValueError:
                return x
        
        categorias_infantiles = sorted(categorias_infantiles, key=lambda x: (not x.isdigit(), sort_key(x)))
        categorias = categorias_infantiles
    else:
        categorias = sorted(data['Secció / Seccion'].astype(str).dropna().unique())

    if tipo_falla_seleccionada != 'Carpa Fallera':
        categoria_seleccionada = st.selectbox("Selecciona la categoría de falla", ['Todas'] + categorias)

    # Filtrar los datos según el tipo de falla y la categoría seleccionados
    data_filtrada = data
    if tipo_falla_seleccionada != 'Todas':
        data_filtrada = data[data['Tipo Falla'] == tipo_falla_seleccionada]
    if tipo_falla_seleccionada != 'Carpa Fallera' and 'categoria_seleccionada' in locals() and categoria_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'] == categoria_seleccionada]

    if st.button("Buscar Falla Más Cercana", key="boton_buscar_falla"):
        if direccion:
            geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza '763ed800dfa0492ebffca31d51cf54a4' con tu clave de OpenCageGeocode
            ubicacion = geocoder.geocode(direccion)
            if ubicacion:
                ubicacion_usuario = (ubicacion[0]['geometry']['lat'], ubicacion[0]['geometry']['lng'])
                falla_cercana = falla_mas_cercana(data_filtrada, ubicacion_usuario)
                
                st.session_state.falla_cercana = falla_cercana
                st.session_state.ubicacion_usuario = ubicacion_usuario
                st.session_state.mostrar_falla = True
                
                # Obtener la ruta con calles reales usando OpenRouteService
                coordenadas = [(ubicacion_usuario[1], ubicacion_usuario[0]), (falla_cercana['geo_point_2d_lon'], falla_cercana['geo_point_2d_lat'])]
                ruta_con_calles = obtener_ruta_con_calles(coordenadas, ors_client)
                
                # Mostrar mapa con la ubicación de la falla más cercana y la ruta
                st.session_state.mapa = folium.Map(location=ubicacion_usuario, zoom_start=13)
                folium.Marker(location=ubicacion_usuario, popup="Tu Ubicación", icon=folium.Icon(color='blue')).add_to(st.session_state.mapa)
                folium.Marker(location=[falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon']], popup=falla_cercana['Nom / Nombre'], icon=folium.Icon(color='red')).add_to(st.session_state.mapa)
                folium.GeoJson(ruta_con_calles, name="Ruta").add_to(st.session_state.mapa)
            else:
                st.write("Dirección no encontrada.")
        else:
            st.write("Por favor, introduce una dirección.")

    if 'mostrar_falla' in st.session_state and st.session_state.mostrar_falla:
        falla_cercana = st.session_state.falla_cercana
        if falla_cercana['Tipo Falla'] == 'Falla Adulta':
            st.write(f"Nombre: {falla_cercana['Nom / Nombre']}")
            st.write(f"Sección: {falla_cercana['Secció / Seccion']}")
            st.write(f"Fallera Mayor: {falla_cercana['Fallera Major / Fallera Mayor']}")
            st.write(f"Presidente: {falla_cercana['President / Presidente']}")
            st.write(f"Artista: {falla_cercana['Artiste / Artista']}")
            st.write(f"Lema: {falla_cercana['Lema']}")
            st.write(f"Año Fundación: {int(falla_cercana['Any_Fundacio'])}")  # Mostrar como entero
            st.write(f"Distintivo: {falla_cercana['Distintiu / Distintivo']}")
            st.image(falla_cercana['Esbos'], caption="Esbós")
            st.write(f"Falla Experimental: {'SI' if falla_cercana['Falla Experimental'] == 1 else 'NO'}")
        elif falla_cercana['Tipo Falla'] == 'Falla Infantil':
            st.write(f"Nombre: {falla_cercana['Nom / Nombre']}")
            st.write(f"Sección: {falla_cercana['Secció / Seccion']}")
            st.write(f"Fallera Mayor: {falla_cercana['Fallera Major / Fallera Mayor']}")
            st.write(f"Presidente: {falla_cercana['President / Presidente']}")
            st.write(f"Artista: {falla_cercana['Artiste / Artista']}")
            st.write(f"Lema: {falla_cercana['Lema']}")
            st.image(falla_cercana['Esbos'], caption="Esbós")

    if 'mapa' in st.session_state:
        st_folium(st.session_state.mapa, width=700, height=500)

elif seccion == "Calcular Ruta Turística":
    st.header("Calcular Ruta Turística")

    direccion = st.text_input("Introduce tu dirección")
    distancia_maxima = st.number_input("Introduce la distancia máxima de la ruta (km)", min_value=1.0, max_value=100.0, value=10.0, step=0.1)

    tipo_falla_seleccionada = st.selectbox("Selecciona el tipo de falla", ['Todas', 'Falla Adulta', 'Falla Infantil', 'Carpa Fallera'])

    # Mostrar categorías solo para el tipo de falla seleccionado
    if tipo_falla_seleccionada == 'Falla Adulta':
        categorias = sorted(data_fallas_adultas['Secció / Seccion'].astype(str).unique())
    elif tipo_falla_seleccionada == 'Falla Infantil':
        # Convertir todos los valores a str para evitar errores de comparación
        categorias_infantiles = data_fallas_infantiles['Secció / Seccion'].astype(str).unique()
        categorias_infantiles = [c for c in categorias_infantiles if c not in ['FC', 'IE']]  # Filtrar categorías incorrectas
        
        # Ordenar considerando números y cadenas
        def sort_key(x):
            try:
                return int(x)
            except ValueError:
                return x
        
        categorias_infantiles = sorted(categorias_infantiles, key=lambda x: (not x.isdigit(), sort_key(x)))
        categorias = categorias_infantiles
    else:
        categorias = sorted(data['Secció / Seccion'].astype(str).dropna().unique())

    if tipo_falla_seleccionada != 'Carpa Fallera':
        categoria_seleccionada = st.selectbox("Selecciona la categoría de falla", ['Todas'] + categorias)

    # Filtrar los datos según el tipo de falla y la categoría seleccionados
    data_filtrada = data
    if tipo_falla_seleccionada != 'Todas':
        data_filtrada = data[data['Tipo Falla'] == tipo_falla_seleccionada]
    if tipo_falla_seleccionada != 'Carpa Fallera' and 'categoria_seleccionada' in locals() and categoria_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'] == categoria_seleccionada]

    if st.button("Calcular Ruta", key="boton_calcular_ruta"):
        if direccion:
            geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza '763ed800dfa0492ebffca31d51cf54a4' con tu clave de OpenCageGeocode
            ubicacion = geocoder.geocode(direccion)
            if ubicacion:
                ubicacion_usuario = (ubicacion[0]['geometry']['lat'], ubicacion[0]['geometry']['lng'])
                ruta_turistica = calcular_ruta_turistica(data_filtrada, ubicacion_usuario, distancia_maxima, ors_client)
                
                st.session_state.ruta_turistica = ruta_turistica
                st.session_state.ubicacion_usuario = ubicacion_usuario
                st.session_state.mostrar_ruta = True

                st.write("Ruta Turística Calculada:")
                st.dataframe(ruta_turistica[['Nom / Nombre', 'distancia_acumulada']])
                
                # Obtener la ruta con calles reales usando OpenRouteService
                coordenadas = [(ubicacion_usuario[1], ubicacion_usuario[0])]
                for _, row in ruta_turistica.iterrows():
                    coordenadas.append((row['geo_point_2d_lon'], row['geo_point_2d_lat']))
                ruta_con_calles = obtener_ruta_con_calles(coordenadas, ors_client)
                
                # Mostrar el mapa con la ruta turística
                st.session_state.mapa_turistica = folium.Map(location=ubicacion_usuario, zoom_start=13)
                folium.GeoJson(ruta_con_calles, name="Ruta").add_to(st.session_state.mapa_turistica)
                for _, row in ruta_turistica.iterrows():
                    folium.Marker(location=[row['geo_point_2d_lat'], row['geo_point_2d_lon']], popup=row['Nom / Nombre'], icon=folium.Icon(color='red')).add_to(st.session_state.mapa_turistica)
            else:
                st.write("Dirección no encontrada.")
        else:
            st.write("Por favor, introduce una dirección.")
    
    if 'mapa_turistica' in st.session_state:
        st_folium(st.session_state.mapa_turistica, width=700, height=500)

    if 'mostrar_ruta' in st.session_state and st.session_state.mostrar_ruta:
        ruta_turistica = st.session_state.ruta_turistica
        st.write("Ruta Turística Calculada:")
        st.dataframe(ruta_turistica[['Nom / Nombre', 'distancia_acumulada']])
