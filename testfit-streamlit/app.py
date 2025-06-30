"""
TestFit Data Center Site Optimizer - Streamlit Web Application
Converted from PyQt5 desktop application to web-based interface
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import tempfile
import os
import json
import folium
from streamlit_folium import st_folium
import zipfile
import io
from pathlib import Path

# Import your existing modules (we'll create these)
from testfit.models import DEFAULT_BUILDING_SPECS, Building, Substation
from testfit.parser import KMLParser
from testfit.optimizer import DataHallOptimizedPlacer
from testfit.visualizer import create_site_visualization, create_interactive_map

# Configure Streamlit page
st.set_page_config(
    page_title="TestFit Data Center Optimizer",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 0.75rem;
        margin-bottom: 1rem;
        border-radius: 0.25rem;
    }
    .warning-message {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 0.75rem;
        margin-bottom: 1rem;
        border-radius: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

def check_password():
    """Simple password protection"""
    def password_entered():
        if st.session_state["password"] == st.secrets.get("app_password", "testfit2024"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Enter Password to Access TestFit Optimizer", 
                     type="password", on_change=password_entered, key="password")
        st.info("Enter the access password to use the TestFit Data Center Site Optimizer")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 Enter Password to Access TestFit Optimizer", 
                     type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Please try again.")
        return False
    else:
        return True

def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'kml_parser' not in st.session_state:
        st.session_state.kml_parser = None
    if 'features_data' not in st.session_state:
        st.session_state.features_data = {}
    if 'buildings' not in st.session_state:
        st.session_state.buildings = []
    if 'substations' not in st.session_state:
        st.session_state.substations = []
    if 'optimization_stats' not in st.session_state:
        st.session_state.optimization_stats = {}
    if 'building_specs' not in st.session_state:
        st.session_state.building_specs = DEFAULT_BUILDING_SPECS.copy()

def process_uploaded_file(uploaded_file):
    """Process uploaded KML/KMZ file"""
    try:
        # Handle KMZ files (ZIP archives containing KML)
        if uploaded_file.name.lower().endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file, 'r') as kmz:
                kml_files = [f for f in kmz.namelist() if f.lower().endswith('.kml')]
                if not kml_files:
                    st.error("No KML file found in KMZ archive")
                    return False
                
                # Use the first KML file found
                with kmz.open(kml_files[0]) as kml_file:
                    kml_content = kml_file.read().decode('utf-8')
        else:
            # Regular KML file
            kml_content = uploaded_file.getvalue().decode('utf-8')
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.kml', encoding='utf-8') as tmp:
            tmp.write(kml_content)
            tmp_path = tmp.name
        
        # Parse KML
        st.session_state.kml_parser = KMLParser()
        raw_features = st.session_state.kml_parser.parse_kml_file(tmp_path)
        st.session_state.features_data = st.session_state.kml_parser.convert_to_local_coordinates(raw_features)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        return True
        
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return False

def create_constraint_selection():
    """Create constraint feature selection interface"""
    if not st.session_state.features_data:
        return []
    
    st.subheader("🗺️ Constraint Features")
    st.caption("Select features to use as constraints (no-build zones):")
    
    selected_constraints = []
    layer_manager = st.session_state.kml_parser.layer_manager
    
    # Group features by layer type for better organization
    layer_features = {}
    for name, feature_data in st.session_state.features_data.items():
        layer_type = layer_manager.classify_feature(name, feature_data.get('description', ''))
        if layer_type not in layer_features:
            layer_features[layer_type] = []
        layer_features[layer_type].append((name, feature_data))
    
    # Display features by layer with checkboxes
    for layer_type, features in layer_features.items():
        if features:
            layer_name = layer_type.replace('_', ' ').title()
            setback = layer_manager.get_effective_setback(layer_type)
            is_power_layer = layer_type in ['power_lines', 'power_generation']
            
            st.write(f"**{layer_name}** ({setback:.0f}ft setback) {'⚡ Power Features' if is_power_layer else ''}")
            
            for name, feature_data in features:
                # Auto-select likely constraints
                default_constraint = any(word in name.lower() for word in 
                                       ['road', 'wetland', 'flood', 'utility', 'easement', 'power', 'transmission', 'existing'])
                
                if st.checkbox(
                    f"📍 {name}",
                    value=default_constraint,
                    key=f"constraint_{name}",
                    help=f"Type: {layer_type}, Setback: {setback:.0f}ft"
                ):
                    selected_constraints.append(name)
    
    return selected_constraints

def run_optimization(selected_constraints, config):
    """Run the optimization process"""
    try:
        with st.spinner("🔄 Running optimization... This may take a few minutes."):
            # Mark selected constraints
            layer_manager = st.session_state.kml_parser.layer_manager
            layer_manager.constraint_features.clear()
            for constraint_name in selected_constraints:
                layer_manager.mark_as_constraint(constraint_name)
            
            # Get enabled building specs
            enabled_specs = [spec for spec in st.session_state.building_specs if spec.enabled]
            if not enabled_specs:
                st.error("❌ No building types are enabled. Please enable at least one building type.")
                return False
            
            # Create optimizer
            placer = DataHallOptimizedPlacer(
                layer_manager,
                enabled_specs,
                max_power_mw=config['max_power_mw'],
                max_height_ft=config['max_height_ft'],
                gen_yard_on_top=config['gen_yard_on_top'],
                cool_yard_on_top=config['cool_yard_on_top'],
                existing_substation_mw=config['existing_substation_mw']
            )
            
            # Run optimization
            buildings, substations, stats = placer.place_buildings_optimized(
                num_trials=config['num_trials'],
                single_type_only=config['single_type_only']
            )
            
            if 'error' in stats:
                st.error(f"❌ Optimization failed: {stats['error']}")
                return False
            
            # Add geographic coordinates
            parser = st.session_state.kml_parser
            for building in buildings:
                corners = building.get_corners_local()
                if corners:
                    xs, ys = zip(*corners)
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                else:
                    center_x = building.x + building.width/2
                    center_y = building.y + building.length/2
                
                building.lat, building.lon = parser.local_to_latlon(center_x, center_y)
                building.corners_latlon = []
                for x, y in corners:
                    lat, lon = parser.local_to_latlon(x, y)
                    building.corners_latlon.append((lat, lon))
            
            for substation in substations:
                center_x = substation.x + substation.width/2
                center_y = substation.y + substation.length/2
                substation.lat, substation.lon = parser.local_to_latlon(center_x, center_y)
                
                corners_local = substation.get_corners_local()
                substation.corners_latlon = []
                for x, y in corners_local:
                    lat, lon = parser.local_to_latlon(x, y)
                    substation.corners_latlon.append((lat, lon))
            
            # Store results in session state
            st.session_state.buildings = buildings
            st.session_state.substations = substations
            st.session_state.optimization_stats = stats
            
            return True
            
    except Exception as e:
        st.error(f"❌ Optimization error: {str(e)}")
        return False

def display_results():
    """Display optimization results"""
    if not st.session_state.buildings and not st.session_state.substations:
        return
    
    # Key metrics
    total_data_hall = sum(b.data_hall_area for b in st.session_state.buildings)
    total_power_low = sum(b.building_spec.low_it_mw for b in st.session_state.buildings)
    total_power_high = sum(b.building_spec.high_it_mw for b in st.session_state.buildings)
    total_footprint = sum(b.area for b in st.session_state.buildings)
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🏢 Buildings",
            value=len(st.session_state.buildings),
            help="Total number of optimally placed buildings"
        )
    
    with col2:
        st.metric(
            label="⚡ Substations", 
            value=len(st.session_state.substations),
            help="Required electrical substations"
        )
    
    with col3:
        st.metric(
            label="📊 Data Hall Area",
            value=f"{total_data_hall:,.0f} sqft",
            help="Total revenue-generating data hall space"
        )
    
    with col4:
        st.metric(
            label="🔌 IT Power Range",
            value=f"{total_power_low:.1f}-{total_power_high:.1f} MW",
            help="Total IT power capacity range"
        )

def create_building_management_tab():
    """Create building specifications management interface"""
    st.header("🏗️ Building Type Management")
    
    # Add/remove building types
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Available Building Types")
    
    with col2:
        if st.button("➕ Add Custom Type"):
            new_spec = DEFAULT_BUILDING_SPECS[0].__class__(
                name="Custom Data Center",
                num_stories=1,
                num_data_halls=2,
                building_height=24,
                screen_height=20,
                width=150,
                length=80,
                gen_yard=30,
                cool_yard=20,
                gross_sqft=12000,
                data_hall_sqft=9000,
                low_it_mw=20.0,
                high_it_mw=30.0,
                low_watt_sqft=185,
                high_watt_sqft=278,
                utility_low_pue_mw=30.0,
                utility_high_pue_mw=45.0,
                color="purple",
                enabled=True
            )
            st.session_state.building_specs.append(new_spec)
            st.rerun()
    
    # Display building specs in editable format
    for i, spec in enumerate(st.session_state.building_specs):
        with st.expander(f"📋 {spec.name}", expanded=False):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                spec.name = st.text_input("Name", value=spec.name, key=f"name_{i}")
                spec.width = st.number_input("Width (ft)", value=spec.width, min_value=10.0, key=f"width_{i}")
                spec.length = st.number_input("Length (ft)", value=spec.length, min_value=10.0, key=f"length_{i}")
                spec.building_height = st.number_input("Height (ft)", value=spec.building_height, min_value=10.0, key=f"height_{i}")
            
            with col2:
                spec.data_hall_sqft = st.number_input("Data Hall (sqft)", value=spec.data_hall_sqft, min_value=100.0, key=f"data_hall_{i}")
                spec.low_it_mw = st.number_input("Min IT Power (MW)", value=spec.low_it_mw, min_value=0.1, key=f"low_power_{i}")
                spec.high_it_mw = st.number_input("Max IT Power (MW)", value=spec.high_it_mw, min_value=spec.low_it_mw, key=f"high_power_{i}")
                spec.num_data_halls = st.number_input("Data Halls", value=spec.num_data_halls, min_value=1, key=f"data_halls_{i}")
            
            with col3:
                spec.enabled = st.checkbox("Enabled", value=spec.enabled, key=f"enabled_{i}")
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.building_specs.pop(i)
                    st.rerun()
    
    # Display summary table
    if st.session_state.building_specs:
        st.subheader("📊 Building Types Summary")
        
        summary_data = []
        for spec in st.session_state.building_specs:
            summary_data.append({
                "Name": spec.name,
                "Enabled": "✅" if spec.enabled else "❌",
                "Dimensions": f"{spec.width:.0f}' × {spec.length:.0f}'",
                "Data Hall": f"{spec.data_hall_sqft:,.0f} sqft",
                "Power Range": f"{spec.low_it_mw:.1f}-{spec.high_it_mw:.1f} MW",
                "Efficiency": f"{(spec.data_hall_sqft/max(spec.gross_sqft,1)*100):.1f}%"
            })
        
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True)

def create_export_options():
    """Create export functionality"""
    if not st.session_state.buildings and not st.session_state.substations:
        st.info("Run optimization first to enable export options")
        return
    
    st.subheader("📤 Export Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # JSON Export
        if st.button("📄 Export JSON Data"):
            export_data = {
                'summary': {
                    'total_buildings': len(st.session_state.buildings),
                    'total_substations': len(st.session_state.substations),
                    'total_data_hall_area_sqft': sum(b.data_hall_area for b in st.session_state.buildings),
                    'total_power_capacity_mw': sum(b.megawatts for b in st.session_state.buildings),
                },
                'buildings': [
                    {
                        'id': b.building_id,
                        'type': b.building_type,
                        'data_hall_sqft': b.data_hall_area,
                        'power_mw': b.megawatts,
                        'rotation_degrees': b.rotation,
                        'lat': b.lat,
                        'lon': b.lon,
                        'corners_latlon': b.corners_latlon
                    } for b in st.session_state.buildings
                ],
                'substations': [
                    {
                        'id': s.substation_id,
                        'size_acres': s.size_acres,
                        'power_capacity_mw': s.power_capacity_mw,
                        'type': 'existing' if s.is_existing else 'new',
                        'lat': s.lat,
                        'lon': s.lon,
                        'corners_latlon': s.corners_latlon
                    } for s in st.session_state.substations
                ]
            }
            
            st.download_button(
                label="💾 Download JSON",
                data=json.dumps(export_data, indent=2),
                file_name="testfit_optimization_results.json",
                mime="application/json"
            )
    
    with col2:
        # KML Export
        if st.button("🗺️ Export KML"):
            kml_content = create_kml_export()
            st.download_button(
                label="💾 Download KML",
                data=kml_content,
                file_name="testfit_site_layout.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
    
    with col3:
        # CSV Export
        if st.button("📊 Export CSV Summary"):
            csv_content = create_csv_export()
            st.download_button(
                label="💾 Download CSV",
                data=csv_content,
                file_name="testfit_building_summary.csv",
                mime="text/csv"
            )

def create_kml_export():
    """Create KML export content"""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<name>TestFit Optimized Site Layout</name>
"""
    
    # Export buildings
    for building in st.session_state.buildings:
        if building.corners_latlon:
            coords_str = " ".join([f"{lon},{lat},0" for lat, lon in building.corners_latlon])
            # Close the polygon
            if building.corners_latlon:
                first_lat, first_lon = building.corners_latlon[0]
                coords_str += f" {first_lon},{first_lat},0"
            
            kml_content += f"""
<Placemark>
<name>{building.building_type} #{building.building_id}</name>
<description>
Data Hall: {building.data_hall_area:,.0f} sqft
Power: {building.building_spec.low_it_mw:.1f}-{building.building_spec.high_it_mw:.1f} MW
Rotation: {building.rotation:.0f}°
</description>
<Polygon>
<outerBoundaryIs>
<LinearRing>
<coordinates>{coords_str}</coordinates>
</LinearRing>
</outerBoundaryIs>
</Polygon>
</Placemark>"""
    
    # Export substations
    for substation in st.session_state.substations:
        if substation.corners_latlon:
            coords_str = " ".join([f"{lon},{lat},0" for lat, lon in substation.corners_latlon])
            if substation.corners_latlon:
                first_lat, first_lon = substation.corners_latlon[0]
                coords_str += f" {first_lon},{first_lat},0"
            
            kml_content += f"""
<Placemark>
<name>Substation #{substation.substation_id}</name>
<description>
Size: {substation.size_acres:.2f} acres
Capacity: {substation.power_capacity_mw:.0f} MW
Type: {'Existing' if substation.is_existing else 'New'}
</description>
<Polygon>
<outerBoundaryIs>
<LinearRing>
<coordinates>{coords_str}</coordinates>
</LinearRing>
</outerBoundaryIs>
</Polygon>
</Placemark>"""
    
    kml_content += "\n</Document>\n</kml>"
    return kml_content

def create_csv_export():
    """Create CSV export content"""
    building_data = []
    for b in st.session_state.buildings:
        building_data.append({
            'Building_ID': b.building_id,
            'Type': b.building_type,
            'Data_Hall_SQFT': b.data_hall_area,
            'Power_MW_Low': b.building_spec.low_it_mw,
            'Power_MW_High': b.building_spec.high_it_mw,
            'Rotation_Degrees': b.rotation,
            'Latitude': b.lat,
            'Longitude': b.lon,
            'Local_X': b.x,
            'Local_Y': b.y,
            'Width_FT': b.width,
            'Length_FT': b.length
        })
    
    df = pd.DataFrame(building_data)
    return df.to_csv(index=False)

def main():
    """Main Streamlit application"""
    # Password protection
    if not check_password():
        return
    
    # Initialize session state
    initialize_session_state()
    
    # Main header
    st.markdown('<h1 class="main-header">🏢 TestFit Data Center Site Optimizer</h1>', unsafe_allow_html=True)
    st.markdown("**Optimize data center building placement with AI-powered site analysis**")
    
    # Sidebar configuration
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60/1f77b4/white?text=TestFit", width=200)
        st.header("📋 Configuration")
        
        # File upload
        st.subheader("📁 Site Data")
        uploaded_file = st.file_uploader(
            "Upload KML/KMZ site file",
            type=['kml', 'kmz'],
            help="Upload a KML or KMZ file containing site boundaries and constraints"
        )
        
        if uploaded_file is not None:
            if process_uploaded_file(uploaded_file):
                st.success(f"✅ Loaded {len(st.session_state.features_data)} features")
                
                # Configuration options
                st.subheader("⚙️ Optimization Settings")
                
                max_power_mw = st.number_input(
                    "Max Power Available (MW)",
                    min_value=0.0,
                    value=0.0,
                    help="Maximum power capacity available (0 = no limit)"
                )
                
                max_height_ft = st.number_input(
                    "Max Building Height (ft)",
                    min_value=0.0,
                    value=0.0,
                    help="Maximum building height allowed (0 = no limit)"
                )
                
                # Yard configuration
                st.subheader("🏗️ Yard Configuration")
                gen_yard_on_top = st.checkbox(
                    "Gen Yard can be on building roof",
                    help="Allow generator yard to be placed on top of building"
                )
                
                cool_yard_on_top = st.checkbox(
                    "Cool Yard can be on building roof",
                    help="Allow cooling yard to be placed on top of building"
                )
                
                # Existing infrastructure
                st.subheader("⚡ Existing Infrastructure")
                has_existing_substation = st.checkbox("Site has existing substation")
                existing_substation_mw = 0.0
                if has_existing_substation:
                    existing_substation_mw = st.number_input(
                        "Existing Substation Capacity (MW)",
                        min_value=0.0,
                        value=100.0
                    )
                
                # Advanced settings
                with st.expander("🔧 Advanced Settings"):
                    num_trials = st.slider(
                        "Optimization Trials",
                        min_value=5,
                        max_value=100,
                        value=30,
                        help="More trials = better optimization but slower processing"
                    )
                    
                    single_type_only = st.checkbox(
                        "Single building type per site",
                        value=True,
                        help="Test each building type separately (recommended)"
                    )
        
        # Quick stats
        if st.session_state.features_data:
            st.subheader("📊 Quick Stats")
            st.info(f"📍 **Features loaded:** {len(st.session_state.features_data)}")
            if st.session_state.buildings:
                st.success(f"🏢 **Buildings placed:** {len(st.session_state.buildings)}")
                st.success(f"⚡ **Substations:** {len(st.session_state.substations)}")
    
    # Main content area
    if not st.session_state.features_data:
        # Welcome screen
        st.info("👆 **Upload a KML/KMZ file in the sidebar to get started**")
        
        st.markdown("""
        ### 🚀 How to Use TestFit Optimizer
        
        1. **📁 Upload Site Data**: Load your KML/KMZ file containing site boundaries and constraints
        2. **⚙️ Configure Settings**: Set power limits, height constraints, and yard options  
        3. **🗺️ Select Constraints**: Choose which features should be treated as no-build zones
        4. **🏗️ Manage Building Types**: Customize available data center building specifications
        5. **🎯 Run Optimization**: Execute the AI-powered layout optimization
        6. **📊 View Results**: Analyze the optimized layout and export results
        
        ### 🎯 Key Features
        - **AI-Powered Optimization**: Advanced algorithms find optimal building placement
        - **Constraint-Aware**: Respects setbacks, environmental features, and regulations
        - **Multiple Building Types**: Support for various data center configurations
        - **Smart Substation Placement**: Automatically calculates and places required substations
        - **Interactive Visualization**: 2D plots and interactive maps
        - **Export Capabilities**: KML, JSON, and CSV export options
        """)
        
        return
    
    # Constraint selection
    selected_constraints = create_constraint_selection()
    
    # Optimization controls
    st.subheader("🎯 Run Optimization")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"📍 **{len(selected_constraints)} constraints selected** • Ready to optimize with {len([s for s in st.session_state.building_specs if s.enabled])} building types")
    
    with col2:
        if st.button("🚀 **Optimize Layout**", type="primary", use_container_width=True):
            config = {
                'max_power_mw': max_power_mw if 'max_power_mw' in locals() else 0,
                'max_height_ft': max_height_ft if 'max_height_ft' in locals() else 0,
                'gen_yard_on_top': gen_yard_on_top if 'gen_yard_on_top' in locals() else False,
                'cool_yard_on_top': cool_yard_on_top if 'cool_yard_on_top' in locals() else False,
                'existing_substation_mw': existing_substation_mw if 'existing_substation_mw' in locals() else 0,
                'num_trials': num_trials if 'num_trials' in locals() else 30,
                'single_type_only': single_type_only if 'single_type_only' in locals() else True
            }
            
            if run_optimization(selected_constraints, config):
                st.success("✅ **Optimization completed successfully!**")
    
    # Results display
    if st.session_state.buildings or st.session_state.substations:
        st.markdown("---")
        display_results()
        
        # Tabbed interface for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Site Layout", "🗺️ Interactive Map", "🏗️ Building Types", "📤 Export"])
        
        with tab1:
            st.subheader("📊 Optimized Site Layout")
            
            # Create and display visualization
            fig = create_site_visualization(
                st.session_state.buildings,
                st.session_state.substations,
                st.session_state.kml_parser.layer_manager,
                st.session_state.features_data
            )
            
            st.pyplot(fig, use_container_width=True)
            
            # Detailed results table
            if st.session_state.buildings:
                st.subheader("📋 Building Details")
                
                building_data = []
                for b in st.session_state.buildings:
                    building_data.append({
                        'ID': b.building_id,
                        'Type': b.building_type,
                        'Data Hall (sqft)': f"{b.data_hall_area:,.0f}",
                        'Power Range (MW)': f"{b.building_spec.low_it_mw:.1f}-{b.building_spec.high_it_mw:.1f}",
                        'Rotation': f"{b.rotation:.0f}°",
                        'Dimensions': f"{b.width:.0f}' × {b.length:.0f}'",
                        'Group': b.group_id
                    })
                
                df = pd.DataFrame(building_data)
                st.dataframe(df, use_container_width=True)
        
        with tab2:
            st.subheader("🗺️ Interactive Site Map")
            
            if st.session_state.kml_parser:
                interactive_map = create_interactive_map(
                    st.session_state.buildings,
                    st.session_state.substations,
                    st.session_state.kml_parser,
                    st.session_state.features_data
                )
                
                st_folium(interactive_map, width=700, height=500)
        
        with tab3:
            create_building_management_tab()
        
        with tab4:
            create_export_options()

if __name__ == "__main__":
    main()