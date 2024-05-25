# -*- coding: utf-8 -*-
"""
Created on Fri May 24 19:40:42 2024

@author: ruben
"""
import streamlit as st
import pandas as pd
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import folium
from streamlit_folium import st_folium

# Función para encontrar la falla más cercana
def falla_mas_cercana(data, ubicacion_usuario):
    data['distancia'] = data.apply(lambda row: geodesic(ubicacion_usuario, (row['geo_point_2d_lat'], row['geo_point_2d_lon'])).km, axis=1)
    falla_cercana = data.loc[data['distancia'].idxmin()]
    return falla_cercana

# Función para cargar y procesar los datos
def cargar_datos(ruta, tipo_falla):
    data = pd.read_csv(ruta, delimiter=';')
    data[['geo_point_2d_lat', 'geo_point_2d_lon']] = data['geo_point_2d'].str.split(',', expand=True).astype(float)
    data['Tipo Falla'] = tipo_falla
    return data

# Cargar los datos
data_fallas_adultas = cargar_datos('falles-fallas.csv', 'Falla Adulta')
data_fallas_infantiles = cargar_datos("falles-infantils-fallas-infantiles.csv", 'Falla Infantil')
data_carpas_falleras = cargar_datos("carpes-falles-carpas-fallas.csv", 'Carpa Fallera')

# Unir todas las bases de datos
data = pd.concat([data_fallas_adultas, data_fallas_infantiles, data_carpas_falleras], ignore_index=True)

# Título de la aplicación
st.title("Fallas Más Cercanas")

# Pedir la ubicación del usuario
st.sidebar.header("Tu Ubicación")
direccion = st.sidebar.text_input("Introduce tu dirección")

# Seleccionar tipo de falla
tipo_falla_seleccionada = st.sidebar.selectbox("Selecciona el tipo de falla", ['Todas', 'Falla Adulta', 'Falla Infantil', 'Carpa Fallera'])

# Filtrar los datos según el tipo de falla seleccionado
data_filtrada = data
if tipo_falla_seleccionada != 'Todas':
    data_filtrada = data[data['Tipo Falla'] == tipo_falla_seleccionada]

# Buscar la falla más cercana cuando se hace clic en el botón
if st.sidebar.button("Buscar Falla Más Cercana"):
    if direccion:
        geocoder = OpenCageGeocode('763ed800dfa0492ebffca31d51cf54a4')  # Reemplaza 'TU_API_KEY' con tu clave de acceso
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
            st.write(f"Coordenadas: ({falla_cercana['geo_point_2d_lat']}, {falla_cercana['geo_point_2d_lon']})")
            st.write(f"Distancia: {falla_cercana['distancia']:.2f} km")
        else:
            st.write(f"Nombre: {falla_cercana['Nom / Nombre']}")
            st.write(f"Coordenadas: ({falla_cercana['geo_point_2d_lat']}, {falla_cercana['geo_point_2d_lon']})")
            st.write(f"Distancia: {falla_cercana['distancia']:.2f} km")
            st.write(f"Tipo: {falla_cercana['Tipo Falla']}")
            st.write(f"Fallera Mayor: {falla_cercana['Fallera Major / Fallera Mayor']}")
            st.write(f"Presidente: {falla_cercana['President / Presidente']}")
            st.write(f"Artista: {falla_cercana['Artiste / Artista']}")
            st.write(f"Lema: {falla_cercana['Lema']}")
            st.write(f"Año de Fundación: {falla_cercana['Any Fundació / Año Fundacion']}")
            st.write(f"Distintivo: {falla_cercana['Distintiu / Distintivo']}")
            st.write(f"Esbós: {falla_cercana['Esbós / Boceto']}")
            st.write(f"Falla Experimental: {falla_cercana['Falla Experimental']}")

        # Mostrar mapa con la ubicación
        m = folium.Map(location=ubicacion_usuario, zoom_start=14)
        folium.Marker([ubicacion_usuario[0], ubicacion_usuario[1]], popup="Tu Ubicación", icon=folium.Icon(color="blue")).add_to(m)
        folium.Marker([falla_cercana['geo_point_2d_lat'], falla_cercana['geo_point_2d_lon']], popup=falla_cercana['Nom / Nombre']).add_to(m)
        st_folium(m, width=700, height=500)

# Mostrar lista de fallas
st.header("Lista de Fallas")
st.dataframe(data_filtrada[['Nom / Nombre', 'geo_point_2d_lat', 'geo_point_2d_lon', 'Tipo Falla']])



