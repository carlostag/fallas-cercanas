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
        
    if not ruta:
        st.write("No hay rutas disponibles de ese tipo.")
        return pd.DataFrame()  # Devuelve un DataFrame vacío
        
    return pd.DataFrame(ruta)

# Función para obtener la ruta con calles reales usando OpenRouteService
def obtener_ruta_con_calles(coordenadas, ors_client):
    ruta = ors_client.directions(
        coordinates=coordenadas,
        profile='foot-walking',
        format='geojson'
    )
    return ruta

# Estilos personalizados
st.markdown("""
    <style>
        .main {
            background-color: #FFF38E;
            color: #333;
            font-family: 'Arial', sans-serif;
        }
        h1, h2, h3 {
            text-align: center;
            color: #D14524;
        }
        .stButton button {
            background-color: #D14524;
            color: white !important;
            border-radius: 10px;
        }
        .stButton button:hover {
            background-color: #FF6100;
            color: white !important;
        }
        .stSelectbox div[data-baseweb='select'] {
            background-color: #B3E5FC;
            border-radius: 5px;
            color: #D14524 !important;
        }
        .stSidebar .sidebar-content {
            background-color: #B3E5FC !important;
            color: #D14524;
        }
        .sidebar .sidebar-content {
            background-color: #B3E5FC;
        }
        /* Estilos para todos los textos generados por Streamlit */
        .stTextInput > label, .stTextArea > label, .stNumberInput > label, .stSelectbox > label, .stRadio > label, .stCheckbox > label, .stSlider > label, .stButton, .stMarkdown, .stDataFrame, .stTable, .stColorPicker > label, .stDateInput > label, .stFileUploader > label, .stJson, .stImage, .stVideo, .stAudio, .stProgress, .stExpander > label, .stVegaLiteChart, .stAltairChart, .stPlotlyChart, .stDeckGlJsonChart, .stGraphvizChart, .stTableChart, .stMapboxChart, .stPydeckChart, .stBokehChart, .stPyplot, .stGraphvizChart, .stGraphviz, .stDataFrameSelector, .stFileUploader > label, .stMetric, .stPlotly, .stDeckGl, .stDataFrame, .stArrowVegaLiteChart, .stArrow, .stArrowDataFrame, .stArrowTable, .stArrowChart, .stMetric, .stTabs > label {
            color: #D14524;
        }
        /* Estilos para los inputs y placeholders */
        input[type="text"], input[type="email"], input[type="password"], input[type="number"], textarea {
            color: #D14524 !important;
        }
        input::placeholder, textarea::placeholder {
            color: #D14524 !important;
        }
        /* Estilos específicos para labels y select boxes */
        .css-1cpxqw2, .css-1cpxqw2 p, .css-1cpxqw2 h3, .css-1cpxqw2 h4, .css-1cpxqw2 h5, .css-1cpxqw2 h6, .css-1cpxqw2 div, .css-1cpxqw2 span, .css-1cpxqw2 label {
            color: #D14524 !important;
        }
        .css-1l02zno, .css-1l02zno p, .css-1l02zno h3, .css-1l02zno h4, .css-1l02zno h5, .css-1l02zno h6, .css-1l02zno div, .css-1l02zno span, .css-1l02zno label {
            color: #D14524 !important;
        }
        /* Estilos para el mapa de folium */
        .leaflet-popup-content-wrapper {
            background-color: #FFF38E !important;
            color: #D14524 !important;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
        }
    </style>
""", unsafe_allow_html=True)

# Interfaz de usuario con Streamlit
st.title("Rutas Turísticas de las Fallas de Valencia")
st.markdown("Encuentra las fallas más cercanas y planifica tu ruta turística.")

# Entrada de dirección del usuario
direccion_usuario = st.text_input("Introduce tu dirección en Valencia:")

# Selección de tipo de falla
tipo_falla = st.selectbox("Selecciona el tipo de falla:", ("Todas", "Falla Adulta", "Falla Infantil", "Carpa Fallera"))

# Selección de distancia máxima
distancia_maxima = st.number_input("Introduce la distancia máxima en km:", min_value=1, max_value=100, value=5)

# Configurar el cliente OpenCage y OpenRouteService
clave_opencage = 'tu_clave_opencage'
clave_openrouteservice = 'tu_clave_openrouteservice'
geocoder = OpenCageGeocode(clave_opencage)
ors_client = openrouteservice.Client(key=clave_openrouteservice)

# Botón para encontrar las fallas más cercanas
if st.button("Encontrar Fallas Cercanas"):
    if direccion_usuario:
        # Geocodificar la dirección del usuario
        ubicacion = geocoder.geocode(direccion_usuario)
        if ubicacion:
            ubicacion_usuario = (ubicacion[0]['geometry']['lat'], ubicacion[0]['geometry']['lng'])
            
            # Filtrar datos según el tipo de falla seleccionado
            if tipo_falla != "Todas":
                data_filtrada = data[data['Tipo Falla'] == tipo_falla]
            else:
                data_filtrada = data

            # Calcular la ruta turística
            ruta_turistica = calcular_ruta_turistica(data_filtrada, ubicacion_usuario, distancia_maxima, ors_client)

            if not ruta_turistica.empty:
                # Crear el mapa con Folium
                m = folium.Map(location=ubicacion_usuario, zoom_start=13)
                folium.Marker(location=ubicacion_usuario, popup="Ubicación del Usuario", icon=folium.Icon(color='blue')).add_to(m)

                coordenadas_ruta = [ubicacion_usuario]
                for _, falla in ruta_turistica.iterrows():
                    coordenadas_falla = (falla['geo_point_2d_lat'], falla['geo_point_2d_lon'])
                    coordenadas_ruta.append(coordenadas_falla)
                    popup_text = f"{falla['Nom / Nombre']} ({falla['Tipo Falla']}) - Distancia acumulada: {falla['distancia_acumulada']:.2f} km"
                    folium.Marker(location=coordenadas_falla, popup=popup_text, icon=folium.Icon(color='orange')).add_to(m)
                
                # Obtener la ruta con calles reales
                ruta_con_calles = obtener_ruta_con_calles(coordenadas_ruta, ors_client)
                folium.GeoJson(ruta_con_calles).add_to(m)

                st_folium(m)
            else:
                st.write("No se encontraron fallas cercanas dentro del rango especificado.")
        else:
            st.write("No se pudo geocodificar la dirección proporcionada.")
    else:
        st.write("Por favor, introduce una dirección válida.")
