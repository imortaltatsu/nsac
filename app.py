import streamlit as st
import ee
import geemap.foliumap as geemap
import datetime
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim
import json

geolocator = Nominatim(user_agent="geo_app")
ee.Initialize()
st.title("Enhanced Landsat Satellite Data Viewer")

location_method = st.radio("Specify Location By:", ("Place Name", "Latitude/Longitude", "Select on Map"))

roi = None
m = None
center = [28.7041, 77.1025]

if "center" not in st.session_state:
    st.session_state.center = center
if "roi" not in st.session_state:
    st.session_state.roi = roi
if "m" not in st.session_state:
    st.session_state.m = geemap.Map(center=st.session_state.center, zoom=4, layers_control=True)  # Corrected zoom
    st.session_state.m.add_basemap("HYBRID")


def get_coordinates(place_name):
    try:
        location = geolocator.geocode(place_name)
        if location:
            return (location.latitude, location.longitude)
        else:
            st.warning(f"Place '{place_name}' not found. Defaulting to New Delhi coordinates.")
            return st.session_state.center
    except Exception as e:
        st.error(f"An error occurred during geocoding: {e}")
        return st.session_state.center

if location_method == "Latitude/Longitude":
    lat = st.number_input("Latitude:", min_value=-90.0, max_value=90.0, value=st.session_state.center[0])
    lon = st.number_input("Longitude:", min_value=-180.0, max_value=180.0, value=st.session_state.center[1])
    if lat and lon:
        st.session_state.roi = ee.Geometry.Point(lon, lat)
        st.session_state.center = [lat, lon]
        st.session_state.m = geemap.Map(center=st.session_state.center, zoom=10, layers_control=True) # Corrected zoom
elif location_method == "Place Name":
    place_name = st.text_input("Enter Place Name (e.g., New Delhi):")
    if place_name:
        location = get_coordinates(place_name)
        if location:
            lat, lon = location
            st.session_state.roi = ee.Geometry.Point(lon, lat)
            st.session_state.center = [lat, lon]
            st.session_state.m = geemap.Map(center=st.session_state.center, zoom=10, layers_control=True)  # Corrected zoom, added layers control


elif location_method == "Select on Map":
    if st.session_state.m is None:
        st.session_state.m = geemap.Map(center=st.session_state.center, zoom=4, layers_control=True)  # Ensured m is initialized and added layers control
        st.session_state.m.add_basemap("HYBRID")

if st.session_state.roi:
    with st.expander("Landsat Image Acquisition and Metadata"):
        start_date = st.date_input("Start Date:", value=datetime.date.today() - datetime.timedelta(days=365))
        end_date = st.date_input("End Date:", value=datetime.date.today())
        cloud_cover_threshold = st.slider("Cloud Cover Threshold (%)", 0, 100, 20)

        if start_date and end_date:
            if end_date < start_date:
                st.error("Error: End date must be after or equal to the start date.")
            else:
                try:
                    start_date_str = start_date.strftime('%Y-%m-%d')
                    end_date_str = end_date.strftime('%Y-%m-%d')
                    point = st.session_state.roi
                    roi = point.buffer(2500)  # ROI for Visualization
                    imageCollection = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
                    image_collection_filtered = imageCollection.filterBounds(point).filterDate(start_date_str, end_date_str).filter(ee.Filter.lte('CLOUD_COVER', cloud_cover_threshold))

                    if image_collection_filtered.size().getInfo() > 0:
                        composite_image = image_collection_filtered.median().setDefaultProjection(image_collection_filtered.first().projection())
                        image_info = image_collection_filtered.first().getInfo()
                        st.write("Image Metadata (of the first image):")
                        st.write(image_info)

                        # Download Button (corrected indent, added import)
                        st.download_button(
                            label="Download Metadata (JSON)",
                            data=json.dumps(image_info, indent=4),
                            file_name="landsat_metadata.json",
                            mime="application/json",
                        )


                        roi_vis_params = {'color': 'red', 'width': 2}
                        image_vis_params = {
                            'bands': ['SR_B4', 'SR_B3', 'SR_B2'],
                            'min': 0,
                            'max': 30000,
                            'gamma': 1
                        }
                        st.session_state.m.addLayer(st.session_state.roi.buffer(50000), roi_vis_params, "Region of interest") # Corrected buffer size to match the one submitted.
                        st.session_state.m.addLayer(composite_image, image_vis_params, 'Landsat image')
                        st.session_state.m.centerObject(st.session_state.roi)  # Center the map correctly using ROI


                    else:
                        st.write(f"No images found with cloud cover less than or equal to {cloud_cover_threshold}% for the specified location and date range.")
                except Exception as e:
                    st.write(f"Error during image acquisition: {e}")

elif location_method == "Select on Map": #ROI using drawing tools
    with st.expander("Draw a point on the map to select ROI"):
        if st.session_state.m:


            drawing_tools = geemap.DrawingTools(st.session_state.m)
            drawing_tools.enable_drawing(st.session_state.m)

            if "last_draw" in st.session_state.m.drawing_tools and st.session_state.m.drawing_tools["last_draw"]["geometry"]["type"] == "Point":
                roi_coords = st.session_state.m.drawing_tools["last_draw"]["geometry"]["coordinates"]
                st.session_state.roi = ee.Geometry.Point(roi_coords[::-1])

                st.session_state.m.drawing_tools = {}  #Clear drawings after ROI has been set.

if st.session_state.m:
    try:
        st.session_state.m.to_streamlit(height=600)
    except Exception as e:
        st.write(e)