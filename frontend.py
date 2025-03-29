import streamlit as st
import requests
import pydeck as pdk
import pandas as pd
from streamlit_geolocation import streamlit_geolocation
from streamlit_folium import st_folium
import folium

# --- Configuration ---
BACKEND_URL = "http://localhost:8000"

# Initialize session state
if 'manual_location' not in st.session_state:
    st.session_state.manual_location = None

if 'all_blood_banks' not in st.session_state:
    st.session_state.all_blood_banks = None

# --- Helper Functions ---
def get_location():
    # First check for manual location in session state
    if st.session_state.manual_location:
        return (st.session_state.manual_location[0], st.session_state.manual_location[1])
    
    # Then try geolocation
    location = streamlit_geolocation()
    if location and 'latitude' in location and 'longitude' in location:
        return (location['latitude'], location['longitude'])
    
    # Default fallback
    return None

def show_route(start_coords, end_coords, route_data):
    if not route_data.get('paths'):
        st.error("No route found")
        return
    
    path = route_data['paths'][0]
    points = [
        [coord[0], coord[1]] 
        for coord in path['points']['coordinates']
    ]
    
    st.subheader("Route Details")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Distance", f"{path['distance']/1000:.2f} km")
    with col2:
        time_mins = path['time'] / 60000  # Convert milliseconds to minutes
        if time_mins < 60:
            time_str = f"{time_mins:.0f} min"
        else:
            time_str = f"{time_mins/60:.1f} hours"
        st.metric("Duration", time_str)
    
    # Create a map with the route
    midpoint = [(start_coords[0] + end_coords[0])/2, (start_coords[1] + end_coords[1])/2]
    
    st.pydeck_chart(pdk.Deck(
        initial_view_state=pdk.ViewState(
            latitude=midpoint[0],
            longitude=midpoint[1],
            zoom=11,
            pitch=50,
        ),
        layers=[
            # Route layer
            pdk.Layer(
                'PathLayer',
                data=[{
                    "path": points,
                    "color": [255, 0, 0]
                }],
                get_color="color",
                get_width=5,
                pickable=True,
            ),
            # Start point marker
            pdk.Layer(
                'ScatterplotLayer',
                data=[{
                    "position": [start_coords[1], start_coords[0]],
                    "color": [0, 255, 0],
                    "radius": 100
                }],
                get_position="position",
                get_color="color",
                get_radius="radius",
            ),
            # End point marker
            pdk.Layer(
                'ScatterplotLayer',
                data=[{
                    "position": [end_coords[1], end_coords[0]],
                    "color": [0, 0, 255],
                    "radius": 100
                }],
                get_position="position",
                get_color="color",
                get_radius="radius",
            ),
        ]
    ))

def select_location_on_map():
    st.subheader("Select Your Location on Map")
    
    # Set default center to a reasonable location (e.g., India center)
    center_lat, center_lon = 20.5937, 78.9629
    
    # Create a map centered at the default location
    m = folium.Map(location=[center_lat, center_lon], zoom_start=5)
    
    # Display the map and get click information
    map_data = st_folium(m, height=400, width=700)
    
    # Check if map was clicked
    if map_data["last_clicked"]:
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lng = map_data["last_clicked"]["lng"]
        st.session_state.manual_location = (clicked_lat, clicked_lng)
        st.success(f"Location selected: {clicked_lat:.6f}, {clicked_lng:.6f}")
        return True
    
    return False

def load_all_blood_banks():
    try:
        if st.session_state.all_blood_banks is None:
            response = requests.get(f"{BACKEND_URL}/all-blood-banks")
            if response.status_code == 200:
                st.session_state.all_blood_banks = response.json()
            else:
                st.error(f"Failed to load blood banks: {response.text}")
                return None
        return st.session_state.all_blood_banks
    except Exception as e:
        st.error(f"Error loading blood bank data: {str(e)}")
        return None

def get_nearby_blood_banks(lat, lon):
    try:
        response = requests.post(
            f"{BACKEND_URL}/nearby",
            json={"latitude": lat, "longitude": lon}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error from server: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error connecting to server: {str(e)}")
        return None

# --- Main App ---
st.title("Blood Bank Locator 🩸")
st.markdown("Find the nearest blood banks and get directions to them.")

# Add tabs for different features
tab1, tab2 = st.tabs(["Find Nearby Blood Banks", "Blood Bank Map"])

with tab1:
    # Get User Location
    location = get_location()
    
    # Check if we have a location
    if location and location[0] is not None and location[1] is not None:
        st.success(f"Using location: {location[0]:.6f}, {location[1]:.6f}")
        
        # Get Nearby Blood Banks
        banks = get_nearby_blood_banks(location[0], location[1])
        
        if banks and len(banks) > 0:
            st.subheader("Nearby Blood Banks")
            selected_bank = st.selectbox(
                "Select a blood bank", 
                banks, 
                format_func=lambda x: f"{x['name']} ({x['distance']:.2f} km)"
            )
            
            if selected_bank:
                st.subheader("Blood Bank Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Name:** {selected_bank['name']}")
                    st.write(f"**Address:** {selected_bank['address']}")
                    st.write(f"**City:** {selected_bank['city']}, {selected_bank['state']}")
                with col2:
                    st.write(f"**Distance:** {selected_bank['distance']:.2f} km")
                    st.write(f"**Coordinates:** {selected_bank['latitude']:.6f}, {selected_bank['longitude']:.6f}")
                
                # Get Route Data
                if st.button("Show Route"):
                    with st.spinner("Calculating route..."):
                        route_response = requests.get(
                            f"{BACKEND_URL}/route",
                            params={
                                "start_lat": location[0],
                                "start_lon": location[1],
                                "end_lat": selected_bank['latitude'],
                                "end_lon": selected_bank['longitude']
                            }
                        )
                        
                        if route_response.status_code == 200:
                            show_route(
                                (location[0], location[1]),
                                (selected_bank['latitude'], selected_bank['longitude']),
                                route_response.json()
                            )
                        else:
                            st.error(f"Failed to get route: {route_response.text}")
                            if "API key not configured" in route_response.text:
                                st.info("The Graphhopper API key is missing. Please set the GRAPHHOPPER_API_KEY environment variable.")
        else:
            st.error("No blood banks found nearby or failed to retrieve data from server.")
    else:
        st.warning("Location not detected automatically.")
        
        # Manual location entry methods
        st.subheader("Set Your Location Manually")
        
        method = st.radio("Choose method:", ["Enter Coordinates", "Select on Map"])
        
        if method == "Enter Coordinates":
            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input("Latitude", value=20.5937, format="%.6f")
            with col2:
                lon = st.number_input("Longitude", value=78.9629, format="%.6f")
            
            if st.button("Use This Location"):
                st.session_state.manual_location = (lat, lon)
                st.rerun()
        else:
            if select_location_on_map():
                st.button("Continue with Selected Location", on_click=st.rerun)

with tab2:
    st.subheader("Blood Bank Map")
    
    # Load all blood banks for map view
    all_banks = load_all_blood_banks()
    
    if all_banks:
        # Create a map centered at a middle point of India
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)
        
        # Add markers for each blood bank
        for bank in all_banks:
            folium.Marker(
                location=[bank['latitude'], bank['longitude']],
                popup=f"{bank['name']}<br>{bank['address']}<br>{bank['city']}, {bank['state']}",
                tooltip=bank['name']
            ).add_to(m)
            
        # If we have a user location, add that too
        if 'manual_location' in st.session_state and st.session_state.manual_location:
            folium.Marker(
                location=st.session_state.manual_location,
                popup="Your Location",
                tooltip="Your Location",
                icon=folium.Icon(color='green')
            ).add_to(m)
            
        # Display the map
        st_folium(m, height=500, width=700)
    else:
        st.error("Unable to load blood bank data for map view")
