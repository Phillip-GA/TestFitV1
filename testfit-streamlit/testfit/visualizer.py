"""
Visualization functions for TestFit Streamlit app
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Polygon
import folium
import numpy as np

def create_site_visualization(buildings, substations, layer_manager, features_data):
    """Create matplotlib visualization of the optimized site layout"""
    fig, ax = plt.subplots(figsize=(16, 12))
    
    # Plot site boundary
    site_boundary = layer_manager.get_site_boundary()
    if site_boundary:
        if hasattr(site_boundary, 'geoms'):
            for geom in site_boundary.geoms:
                if hasattr(geom, 'exterior'):
                    xs, ys = geom.exterior.xy
                    ax.plot(xs, ys, 'k-', linewidth=3, alpha=0.8, label='Site Boundary')
        else:
            if hasattr(site_boundary, 'exterior'):
                xs, ys = site_boundary.exterior.xy
                ax.plot(xs, ys, 'k-', linewidth=3, alpha=0.8, label='Site Boundary')
    
    # Plot features by layer
    for layer_name, features in layer_manager.layers.items():
        if not features:
            continue
            
        color = layer_manager.layer_colors[layer_name]
        
        for feature in features:
            coords = feature['coordinates']
            geom_type = feature['type']
            name = feature['name']
            
            is_constraint = name in layer_manager.constraint_features
            is_power_feature = layer_name in ['power_lines', 'power_generation']
            
            try:
                if geom_type == 'polygon' and len(coords) >= 3:
                    alpha = 0.7 if is_constraint else 0.3
                    fill = is_constraint
                    linewidth = 3 if is_constraint else (2 if is_power_feature else 1)
                    facecolor = 'red' if is_constraint else color
                    edgecolor = 'gold' if is_power_feature else ('darkred' if is_constraint else color)
                    
                    polygon = Polygon(coords, fill=fill, 
                                    facecolor=facecolor, 
                                    alpha=alpha, 
                                    edgecolor=edgecolor, 
                                    linewidth=linewidth)
                    ax.add_patch(polygon)
                    
                elif geom_type == 'linestring' and len(coords) >= 2:
                    xs, ys = zip(*coords)
                    linewidth = 6 if is_constraint else (5 if is_power_feature else (4 if layer_name == 'roads' else 2))
                    line_color = 'red' if is_constraint else ('gold' if is_power_feature else color)
                    ax.plot(xs, ys, color=line_color, linewidth=linewidth, alpha=0.8)
                    
                elif geom_type == 'point' and coords:
                    x, y = coords[0]
                    point_color = 'red' if is_constraint else ('gold' if is_power_feature else color)
                    size = 12 if is_constraint else (10 if is_power_feature else 8)
                    marker = '*' if is_power_feature else 'o'
                    ax.plot(x, y, marker, color=point_color, markersize=size)
            
            except Exception as e:
                print(f"Warning: Could not plot feature {name}: {e}")
                continue
    
    # Plot constraint buffers (setback areas)
    constraints = layer_manager.get_constraint_polygons()
    for constraint in constraints:
        try:
            if hasattr(constraint, 'geoms'):
                for geom in constraint.geoms:
                    if hasattr(geom, 'exterior'):
                        xs, ys = geom.exterior.xy
                        ax.plot(xs, ys, '--', color='red', alpha=0.5, linewidth=1)
            else:
                if hasattr(constraint, 'exterior'):
                    xs, ys = constraint.exterior.xy
                    ax.plot(xs, ys, '--', color='red', alpha=0.5, linewidth=1)
        except Exception as e:
            print(f"Warning: Could not plot constraint buffer: {e}")
            continue
    
    # Plot substations
    for substation in substations:
        try:
            corners = substation.get_corners_local()
            substation_color = 'darkgreen' if substation.is_existing else 'purple'
            polygon = Polygon(corners, facecolor=substation_color, alpha=0.8, 
                            edgecolor='black', linewidth=2)
            ax.add_patch(polygon)
            
            # Add substation label
            center_x = substation.x + substation.width/2
            center_y = substation.y + substation.length/2
            
            existing_marker = "EXIST" if substation.is_existing else "NEW"
            label = f"{existing_marker}\nSUB{substation.substation_id}\n{substation.size_acres:.1f}ac\n{substation.power_capacity_mw:.0f}MW"
            ax.text(center_x, center_y, label, 
                    ha='center', va='center', fontsize=7, fontweight='bold', 
                    color='white')
        except Exception as e:
            print(f"Warning: Could not plot substation {substation.substation_id}: {e}")
            continue
    
    # Plot buildings
    type_colors = {}
    color_cycle = ['blue', 'green', 'purple', 'brown', 'pink', 'orange', 'darkblue']
    
    for building in buildings:
        if building.building_type not in type_colors:
            type_colors[building.building_type] = color_cycle[len(type_colors) % len(color_cycle)]
        
        color = type_colors[building.building_type]
        
        try:
            corners = building.get_corners_local()
            
            # Create polygon patch
            polygon = Polygon(corners, facecolor=color, alpha=0.9, 
                            edgecolor='black', linewidth=2)
            ax.add_patch(polygon)
            
            # Add building label
            if abs(building.rotation) > 0.1:
                xs, ys = zip(*corners)
                center_x = sum(xs) / len(xs)
                center_y = sum(ys) / len(ys)
            else:
                center_x = building.x + building.width/2
                center_y = building.y + building.length/2
            
            spec = building.building_spec
            yard_info = ""
            if building.gen_yard_on_top or building.cool_yard_on_top:
                yard_info = f"\n{'G' if building.gen_yard_on_top else ''}{'C' if building.cool_yard_on_top else ''}↑"
            
            label = f"B{building.building_id}\n{building.data_hall_area:,.0f}sf\n{spec.low_it_mw:.1f}-{spec.high_it_mw:.1f}MW\n{spec.num_data_halls}DH{yard_info}"
            ax.text(center_x, center_y, label, 
                    ha='center', va='center', fontsize=7, fontweight='bold', 
                    color='white')
        
        except Exception as e:
            print(f"Warning: Could not plot building {building.building_id}: {e}")
            continue
    
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('Distance (feet)')
    ax.set_ylabel('Distance (feet)')
    
    # Enhanced title
    constraint_count = len(layer_manager.constraint_features)
    total_data_hall = sum(b.data_hall_area for b in buildings)
    total_power_low = sum(b.building_spec.low_it_mw for b in buildings)
    total_power_high = sum(b.building_spec.high_it_mw for b in buildings)
    substation_count = len(substations)
    new_substation_count = len([s for s in substations if not s.is_existing])
    existing_substation_count = len([s for s in substations if s.is_existing])
    
    existing_sub_text = f" ({existing_substation_count} existing + {new_substation_count} new)" if existing_substation_count > 0 else ""
    
    title = f'Optimized Data Center Layout\n{len(buildings)} Buildings • {total_data_hall:,.0f} sqft Data Hall • {total_power_low:.1f}-{total_power_high:.1f} MW • {substation_count} Substations{existing_sub_text} • {constraint_count} Constraints'
    ax.set_title(title, fontsize=12, pad=20)
    
    # Add legend for building types
    if type_colors:
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, alpha=0.9, edgecolor='black', label=btype) 
                          for btype, color in type_colors.items()]
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))
    
    plt.tight_layout()
    return fig

def create_interactive_map(buildings, substations, kml_parser, features_data):
    """Create interactive Folium map"""
    # Create base map
    m = folium.Map(
        location=[kml_parser.center_lat, kml_parser.center_lon],
        zoom_start=18,
        tiles='OpenStreetMap'
    )
    
    # Add alternative tile layers
    folium.TileLayer('Satellite', 
                    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    attr='Esri',
                    name='Satellite',
                    overlay=False,
                    control=True).add_to(m)
    
    # Building type colors
    type_colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred']
    building_types = list(set(b.building_type for b in buildings))
    type_color_map = {btype: type_colors[i % len(type_colors)] for i, btype in enumerate(building_types)}
    
    # Add buildings to map
    for building in buildings:
        if building.corners_latlon:
            color = type_color_map[building.building_type]
            spec = building.building_spec
            data_hall_ratio = spec.data_hall_ratio * 100
            
            yard_config = []
            if building.gen_yard_on_top:
                yard_config.append("Gen Yard on roof")
            if building.cool_yard_on_top:
                yard_config.append("Cool Yard on roof")
            yard_info = f"<br><b>Yard Config:</b> {', '.join(yard_config)}" if yard_config else ""
            
            popup_html = f"""
            <div style='font-family: Arial; min-width: 250px;'>
                <h4 style='margin: 0 0 10px 0; color: {color};'>{spec.name} #{building.building_id}</h4>
                
                <table style='width: 100%; font-size: 12px;'>
                    <tr><td><b>Rotation:</b></td><td>{building.rotation:.0f}°</td></tr>
                    <tr><td><b>Stories:</b></td><td>{spec.num_stories}</td></tr>
                    <tr><td><b>Data Halls:</b></td><td>{spec.num_data_halls}</td></tr>
                    <tr><td><b>Height:</b></td><td>{spec.building_height:.0f} ft</td></tr>
                    <tr><td><b>Dimensions:</b></td><td>{spec.width:.0f}' × {spec.length:.0f}'</td></tr>
                    <tr><td><b>Gen Yard:</b></td><td>{spec.gen_yard:.0f} ft</td></tr>
                    <tr><td><b>Cool Yard:</b></td><td>{spec.cool_yard:.0f} ft</td></tr>
                    <tr><td><b>Effective Footprint:</b></td><td>{building.width:.0f}' × {building.length:.0f}'</td></tr>
                    <tr><td><b>Gross Area:</b></td><td>{spec.gross_sqft:,.0f} sqft</td></tr>
                    <tr><td><b>Data Hall:</b></td><td>{spec.data_hall_sqft:,.0f} sqft ({data_hall_ratio:.1f}%)</td></tr>
                    <tr><td><b>IT Power:</b></td><td>{spec.low_it_mw:.1f}-{spec.high_it_mw:.1f} MW</td></tr>
                    <tr><td><b>Power Density:</b></td><td>{spec.low_watt_sqft:.0f}-{spec.high_watt_sqft:.0f} W/sqft</td></tr>
                    <tr><td><b>Utility w/ PUE:</b></td><td>{spec.utility_low_pue_mw:.1f}-{spec.utility_high_pue_mw:.1f} MW</td></tr>
                </table>
                {yard_info}
                <p style='margin: 10px 0 0 0; font-size: 10px; color: #666;'>Group: {building.group_id}</p>
            </div>
            """
            
            folium.Polygon(
                locations=building.corners_latlon,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{spec.name} #{building.building_id}<br>{spec.data_hall_sqft:,.0f} sqft<br>{spec.low_it_mw:.1f}-{spec.high_it_mw:.1f} MW",
                color=color,
                weight=2,
                fillColor=color,
                fillOpacity=0.7
            ).add_to(m)
            
            # Add building center marker with summary info
            yard_label = ""
            if building.gen_yard_on_top or building.cool_yard_on_top:
                yard_label = f"<br>{'G' if building.gen_yard_on_top else ''}{'C' if building.cool_yard_on_top else ''}↑"
            
            folium.Marker(
                [building.lat, building.lon],
                icon=folium.DivIcon(
                    html=f"""<div style="
                        background-color: white;
                        border: 2px solid {color};
                        border-radius: 3px;
                        padding: 2px;
                        font-weight: bold;
                        font-size: 9px;
                        text-align: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    ">B{building.building_id}<br>{spec.data_hall_sqft:,.0f}sf<br>{spec.low_it_mw:.1f}-{spec.high_it_mw:.1f}MW<br>{spec.num_data_halls}DH{yard_label}</div>""",
                    icon_size=(85, 40),
                    icon_anchor=(42, 20)
                )
            ).add_to(m)
    
    # Add substations to map
    for substation in substations:
        if hasattr(substation, 'corners_latlon') and substation.corners_latlon:
            substation_color = 'darkgreen' if substation.is_existing else 'purple'
            substation_type = "Existing" if substation.is_existing else "New"
            
            popup_html = f"""
            <div style='font-family: Arial; min-width: 200px;'>
                <h4 style='margin: 0 0 10px 0; color: {substation_color};'>{substation_type} Substation #{substation.substation_id}</h4>
                
                <table style='width: 100%; font-size: 12px;'>
                    <tr><td><b>Type:</b></td><td>{substation_type} Infrastructure</td></tr>
                    <tr><td><b>Area:</b></td><td>{substation.size_acres:.2f} acres ({substation.area:,.0f} sq ft)</td></tr>
                    <tr><td><b>Dimensions:</b></td><td>{substation.width:.0f}' × {substation.length:.0f}'</td></tr>
                    <tr><td><b>Power Capacity:</b></td><td>{substation.power_capacity_mw:.0f} MW</td></tr>
                    <tr><td><b>Rotation:</b></td><td>{substation.rotation:.0f}°</td></tr>
                </table>
                
                <p style='margin: 10px 0 0 0; font-size: 10px; color: #666;'>
                    {"Existing capacity integrated into planning" if substation.is_existing else "New capacity calculated based on building requirements"}
                </p>
            </div>
            """
            
            folium.Polygon(
                locations=substation.corners_latlon,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{substation_type} Substation #{substation.substation_id}<br>{substation.size_acres:.2f} acres<br>{substation.power_capacity_mw:.0f} MW",
                color=substation_color,
                weight=3,
                fillColor=substation_color,
                fillOpacity=0.8
            ).add_to(m)
            
            # Add substation center marker
            folium.Marker(
                [substation.lat, substation.lon],
                icon=folium.DivIcon(
                    html=f"""<div style="
                        background-color: white;
                        border: 2px solid {substation_color};
                        border-radius: 3px;
                        padding: 2px;
                        font-weight: bold;
                        font-size: 9px;
                        text-align: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    ">{substation_type}<br>SUB{substation.substation_id}<br>{substation.size_acres:.1f}ac<br>{substation.power_capacity_mw:.0f}MW</div>""",
                    icon_size=(75, 40),
                    icon_anchor=(37, 20)
                )
            ).add_to(m)
    
    # Add constraint features to map
    layer_manager = kml_parser.layer_manager
    
    # Create feature groups for better organization
    constraints_group = folium.FeatureGroup(name="Constraints", show=True)
    power_features_group = folium.FeatureGroup(name="Power Features", show=True)
    other_features_group = folium.FeatureGroup(name="Other Features", show=False)
    
    for layer_name, features in layer_manager.layers.items():
        if not features:
            continue
        
        layer_color = layer_manager.layer_colors[layer_name]
        
        for feature in features:
            coords = feature['coordinates']
            geom_type = feature['type']
            name = feature['name']
            is_constraint = name in layer_manager.constraint_features
            is_power_feature = layer_name in ['power_lines', 'power_generation']
            
            if coords:
                latlon_coords = []
                for x, y in coords:
                    lat, lon = kml_parser.local_to_latlon(x, y)
                    latlon_coords.append((lat, lon))
                
                display_color = 'red' if is_constraint else ('gold' if is_power_feature else layer_color)
                opacity = 0.7 if is_constraint else (0.8 if is_power_feature else 0.3)
                weight = 3 if is_constraint else (4 if is_power_feature else 1)
                
                popup_text = f"""
                <div style='font-family: Arial;'>
                    <h4 style='margin: 0 0 5px 0; color: {display_color};'>{name}</h4>
                    <p><b>Layer:</b> {layer_name.replace('_', ' ').title()}</p>
                """
                
                if is_constraint:
                    setback = layer_manager.get_effective_setback(layer_name)
                    popup_text += f"<p><b>Status:</b> <span style='color: red;'>CONSTRAINT</span></p>"
                    popup_text += f"<p><b>Setback:</b> {setback:.0f} ft</p>"
                
                if is_power_feature:
                    popup_text += f"<p><b>Function:</b> <span style='color: gold;'>⚡ Guides Substation Placement</span></p>"
                
                popup_text += "</div>"
                
                # Determine which group to add to
                target_group = constraints_group if is_constraint else (power_features_group if is_power_feature else other_features_group)
                
                try:
                    if geom_type == 'polygon' and len(latlon_coords) >= 3:
                        folium.Polygon(
                            locations=latlon_coords,
                            popup=folium.Popup(popup_text, max_width=250),
                            tooltip=name,
                            color=display_color,
                            weight=weight,
                            fillColor=display_color,
                            fillOpacity=opacity
                        ).add_to(target_group)
                    
                    elif geom_type == 'linestring' and len(latlon_coords) >= 2:
                        line_weight = 6 if is_constraint else (5 if is_power_feature else 3)
                        folium.PolyLine(
                            locations=latlon_coords,
                            popup=folium.Popup(popup_text, max_width=250),
                            tooltip=name,
                            color=display_color,
                            weight=line_weight,
                            opacity=opacity
                        ).add_to(target_group)
                    
                    elif geom_type == 'point' and latlon_coords:
                        radius = 12 if is_constraint else (10 if is_power_feature else 8)
                        folium.CircleMarker(
                            location=latlon_coords[0],
                            popup=folium.Popup(popup_text, max_width=250),
                            tooltip=name,
                            color=display_color,
                            radius=radius,
                            fillOpacity=opacity
                        ).add_to(target_group)
                        
                except Exception as e:
                    print(f"Warning: Could not add feature {name} to map: {e}")
                    continue
    
    # Add feature groups to map
    constraints_group.add_to(m)
    power_features_group.add_to(m)
    other_features_group.add_to(m)
    
    # Add site boundary
    site_boundary = layer_manager.get_site_boundary()
    if site_boundary:
        try:
            if hasattr(site_boundary, 'exterior'):
                boundary_coords = []
                for x, y in site_boundary.exterior.coords:
                    lat, lon = kml_parser.local_to_latlon(x, y)
                    boundary_coords.append((lat, lon))
                
                folium.Polygon(
                    locations=boundary_coords,
                    popup="Site Boundary",
                    tooltip="Site Boundary",
                    color='black',
                    weight=3,
                    fill=False
                ).add_to(m)
        except Exception as e:
            print(f"Warning: Could not add site boundary to map: {e}")
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add custom legend
    legend_html = f"""
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px">
    <h4 style="margin: 0 0 10px 0;">Site Layout Legend</h4>
    <p><i class="fa fa-square" style="color:blue"></i> Data Center Buildings</p>
    <p><i class="fa fa-square" style="color:purple"></i> New Substations</p>
    <p><i class="fa fa-square" style="color:darkgreen"></i> Existing Substations</p>
    <p><i class="fa fa-square" style="color:red"></i> Constraints</p>
    <p><i class="fa fa-square" style="color:gold"></i> Power Features</p>
    <p><i class="fa fa-minus" style="color:black"></i> Site Boundary</p>
    <hr>
    <p style="font-size: 10px; margin: 5px 0 0 0;">
        Buildings: {len(buildings)}<br>
        Substations: {len(substations)}<br>
        Total Data Hall: {sum(b.data_hall_area for b in buildings):,.0f} sqft
    </p>
    </div>
    """
    
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m