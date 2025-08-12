import streamlit as st
import pandas as pd
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import folium
from streamlit_folium import st_folium
import openrouteservice
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Función para encontrar la falla más cercana
def falla_mas_cercana(data, ubicacion_usuario):
    data['distancia'] = data.apply(lambda row: geodesic(ubicacion_usuario, (row['geo_point_2d_lat'], row['geo_point_2d_lon'])).km, axis=1)
    falla_cercana = data.loc[data['distancia'].idxmin()]
    return falla_cercana

# Función para cargar y procesar los datos, estandarizando nombres de columnas
@st.cache_data
def cargar_datos(ruta, tipo_falla, columnas_renombrar):
    try:
        data = pd.read_csv(ruta, delimiter=';')
        if 'geo_point_2d' not in data.columns:
            raise ValueError(f"El archivo {ruta} no contiene la columna 'geo_point_2d'.")
        data[['geo_point_2d_lat', 'geo_point_2d_lon']] = data['geo_point_2d'].str.split(',', expand=True).astype(float)
        data['Tipo Falla'] = tipo_falla
        data.rename(columns=columnas_renombrar, inplace=True)
        return data
    except FileNotFoundError:
        st.error(f"No se encontró el archivo {ruta}.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar el archivo {ruta}: {str(e)}")
        return pd.DataFrame()

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

# Verificar si los datos se cargaron correctamente
if data_fallas_adultas.empty or data_fallas_infantiles.empty or data_carpas_falleras.empty:
    st.error("No se pudieron cargar los datos. Verifica los archivos CSV.")
    st.stop()

# Concatenar las fallas adultas e infantiles para obtener nombres de fallas de carpas
data_fallas = pd.concat([data_fallas_adultas, data_fallas_infantiles], ignore_index=True)

# Añadir nombres de fallas a las carpas falleras
data_carpas_falleras = data_carpas_falleras.merge(data_fallas_adultas[['Id. Falla', 'Nom / Nombre']], on='Id. Falla', how='left')

# Unir todas las bases de datos
data = pd.concat([data_fallas_adultas, data_fallas_infantiles, data_carpas_falleras], ignore_index=True)

# Función para calcular la ruta turística acumulando distancias
def calcular_ruta_turistica(data, ubicacion_usuario, distancia_maxima, ors_client):
    data = data.copy()  # Avoid modifying the original DataFrame
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
        st.warning("No se encontraron fallas dentro de la distancia máxima especificada.")
        return pd.DataFrame()
    
    return pd.DataFrame(ruta)

# Función para obtener la ruta con calles reales usando OpenRouteService
def obtener_ruta_con_calles(coordenadas, ors_client):
    try:
        ruta = ors_client.directions(
            coordinates=coordenadas,
            profile='foot-walking',
            format='geojson'
        )
        return ruta
    except Exception as e:
        st.error(f"Error al obtener la ruta: {str(e)}")
        return None

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
        .stTextInput > label, .stTextArea > label, .stNumberInput > label, .stSelectbox > label, .stRadio > label, .stCheckbox > label, .stSlider > label, .stButton, .stMarkdown, .stDataFrame, .stTable, .stColorPicker > label, .stDateInput > label, .stFileUploader > label, .stJson, .stImage, .stVideo, .stAudio, .stProgress, .stExpander > label, .stVegaLiteChart, .stAltairChart, .stPlotlyChart, .stDeckGlJsonChart, .stGraphvizChart, .stTableChart, .stMapboxChart, .stPydeckChart, .stBokehChart, .stPyplot, .stGraphvizChart, .stGraphviz, .stDataFrameSelector, .stFileUploader > label, .stMetric, .stPlotly, .stDeckGl, .stDataFrame, .stArrowVegaLiteChart, .stArrow, .stArrowDataFrame, .stArrowTable, .stArrowChart, .stMetric, .stTabs > label {
            color: #D14524;
        }
        input[type="text"], input[type="email"], input[type="password"], input[type="number"], textarea {
            color: #D14524 !important;
        }
        input::placeholder, textarea::placeholder {
            color: #D14524 !important;
        }
        .css-1cpxqw2, .css-1cpxqw2 p, .css-1cpxqw2 h3, .css-1cpxqw2 h4, .css-1cpxqw2 h5, .css-1cpxqw2 h6, .css-1cpxqw2 div, .css-1cpxqw2 span, .css-1cpxqw2 label {
            color: #D14524 !important;
        }
        .css-1l02zno, .css-1l02zno p, .css-1l02zno h3, .css-1l02zno h4, .css-1l02zno h5, .css-1l02zno h6, .css-1l02zno div, .css-1l02zno span, .css-1l02zno label {
            color: #D14524 !important;
        }
        .css-1d391kg p, .css-1d391kg, .css-1d391kg h3, .css-1d391kg h4, .css-1d391kg h5, .css-1d391kg h6, .css-1d391kg div, .css-1d391kg span, .css-1d391kg label {
            color: #D14524 !important;
        }
        .css-1v0mbdj p, .css-1v0mbdj, .css-1v0mbdj h3, .css-1v0mbdj h4, .css-1v0mbdj h5, .css-1v0mbdj h6, .css-1v0mbdj div, .css-1v0mbdj span, .css-1v0mbdj label {
            color: #D14524 !important;
        }
    </style>
    """, 
    unsafe_allow_html=True
)

# Título de la aplicación
st.title("FALL-ASS")

# Crear cliente de OpenRouteService
load_dotenv()

# Obtener la clave
api_key = os.getenv("API_KEY")

# Usar la clave en el cliente
ors_client = openrouteservice.Client(key=api_key)

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
        categorias = sorted(data_fallas_infantiles['Secció / Seccion'].astype(str).unique(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    else:
        categorias = sorted(data['Secció / Seccion'].astype(str).dropna().unique())

    if tipo_falla_seleccionada != 'Carpa Fallera':
        categoria_seleccionada = st.selectbox("Selecciona la categoría de falla", ['Todas'] + categorias)

    # Filtrar los datos según el tipo de falla y la categoría seleccionados
    data_filtrada = data.copy()
    if tipo_falla_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Tipo Falla'] == tipo_falla_seleccionada]
    if tipo_falla_seleccionada != 'Carpa Fallera' and 'categoria_seleccionada' in locals() and categoria_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'].astype(str) == categoria_seleccionada]

    if st.button("Buscar Falla Más Cercana", key="boton_buscar_falla"):
        if direccion:
            try:
                st.write(f"Dirección ingresada: {direccion}")
                geocoder = OpenCageGeocode(os.getenv('OPENCAGE_API_KEY'))
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
                    
                    if ruta_con_calles:
                        st.session_state.mapa = folium.Map(location=ubicacion_usuario, zoom_start=13)
                        folium.Marker(location=ubicacion_usuario, popup="Tu Ubicación", icon=folium.Icon(color='blue')).add_to(st.session_state.mapa)
                        folium.Marker(location=[falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon']], popup=falla_cercana['Nom / Nombre'], icon=folium.Icon(color='red')).add_to(st.session_state.mapa)
                        folium.GeoJson(ruta_con_calles, name="Ruta").add_to(st.session_state.mapa)
                        folium.PolyLine([(ubicacion_usuario[0], ubicacion_usuario[1]), (falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon'])], color='blue', weight=2.5, opacity=1).add_to(st.session_state.mapa)
                    else:
                        st.error("No se pudo calcular la ruta.")
                else:
                    st.error("Dirección no encontrada. Verifica la dirección ingresada.")
            except Exception as e:
                st.error(f"Error al geocodificar: {str(e)}. Verifica la clave API o la conexión a internet.")
        else:
            st.warning("Por favor, introduce una dirección.")

    if 'mostrar_falla' in st.session_state and st.session_state.mostrar_falla:
        falla_cercana = st.session_state.falla_cercana
        if falla_cercana['Tipo Falla'] == 'Falla Adulta':
            st.write(f"Nombre: {falla_cercana['Nom / Nombre']}")
            st.write(f"Sección: {falla_cercana['Secció / Seccion']}")
            st.write(f"Fallera Mayor: {falla_cercana['Fallera Major / Fallera Mayor']}")
            st.write(f"Presidente: {falla_cercana['President / Presidente']}")
            st.write(f"Artista: {falla_cercana['Artiste / Artista']}")
            st.write(f"Lema: {falla_cercana['Lema']}")
            st.write(f"Año Fundación: {int(falla_cercana['Any_Fundacio'])}")
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
        elif falla_cercana['Tipo Falla'] == 'Carpa Fallera':
            st.write(f"Nombre de la Falla de la Carpa: {falla_cercana['Nom / Nombre']}")

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
        categorias = sorted(data_fallas_infantiles['Secció / Seccion'].astype(str).unique(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    else:
        categorias = sorted(data['Secció / Seccion'].astype(str).dropna().unique())
    
    if tipo_falla_seleccionada != 'Carpa Fallera':
        categoria_seleccionada = st.selectbox("Selecciona la categoría de falla", ['Todas'] + categorias)
    
    data_filtrada = data.copy()
    if tipo_falla_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Tipo Falla'] == tipo_falla_seleccionada]
    if tipo_falla_seleccionada != 'Carpa Fallera' and 'categoria_seleccionada' in locals() and categoria_seleccionada != 'Todas':
        data_filtrada = data_filtrada[data_filtrada['Secció / Seccion'].astype(str) == categoria_seleccionada]
    
    if st.button("Calcular Ruta", key="boton_calcular_ruta"):
        if direccion:
            try:
                st.write(f"Dirección ingresada: {direccion}")
                geocoder = OpenCageGeocode(os.getenv('OPENCAGE_API_KEY'))
                ubicacion = geocoder.geocode(direccion)
                if ubicacion:
                    ubicacion_usuario = (ubicacion[0]['geometry']['lat'], ubicacion[0]['geometry']['lng'])
                    ruta_turistica = calcular_ruta_turistica(data_filtrada, ubicacion_usuario, distancia_maxima, ors_client)
                    
                    if not ruta_turistica.empty:
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
                        
                        if ruta_con_calles:
                            st.session_state.mapa_turistica = folium.Map(location=ubicacion_usuario, zoom_start=13)
                            folium.Marker(location=ubicacion_usuario, popup="Tu Ubicación", icon=folium.Icon(color='blue')).add_to(st.session_state.mapa_turistica)
                            folium.GeoJson(ruta_con_calles, name="Ruta").add_to(st.session_state.mapa_turistica)
                            for _, row in ruta_turistica.iterrows():
                                folium.Marker(location=[row['geo_point_2d_lat'], row['geo_point_2d_lon']], popup=row['Nom / Nombre'], icon=folium.Icon(color='red')).add_to(st.session_state.mapa_turistica)
                            folium.PolyLine([(ubicacion_usuario[0], ubicacion_usuario[1])] + [(row['geo_point_2d_lat'], row['geo_point_2d_lon']) for _, row in ruta_turistica.iterrows()], color='blue', weight=2.5, opacity=1).add_to(st.session_state.mapa_turistica)
                        else:
                            st.error("No se pudo calcular la ruta.")
                    else:
                        st.warning("No se encontraron fallas dentro de la distancia máxima especificada.")
                else:
                    st.error("Dirección no encontrada. Verifica la dirección ingresada.")
            except Exception as e:
                st.error(f"Error al geocodificar: {str(e)}. Verifica la clave API o la conexión a internet.")
        else:
            st.warning("Por favor, introduce una dirección.")
    
    if 'mapa_turistica' in st.session_state:
        st_folium(st.session_state.mapa_turistica, width=700, height=500)
    
    if 'mostrar_ruta' in st.session_state and st.session_state.mostrar_ruta:
        ruta_turistica = st.session_state.ruta_turistica
        st.write("Ruta Turística Calculada:")
        st.dataframe(ruta_turistica[['Nom / Nombre', 'distancia_acumulada']])


