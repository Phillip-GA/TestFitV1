"""
KML Parser and Layer Manager for TestFit
Extracted from your original testfit.py
"""

import xml.etree.ElementTree as ET
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Point, Polygon as ShapelyPolygon, LineString, MultiPolygon
from shapely.ops import unary_union
from pyproj import Transformer

# Layer setback type definitions
SETBACK_TYPES = {
    'standard': {'name': 'Standard', 'multiplier': 1.0},
    'buffer': {'name': 'Buffer Zone', 'multiplier': 1.5},
    'safety': {'name': 'Safety Zone', 'multiplier': 2.0},
    'regulatory': {'name': 'Regulatory', 'multiplier': 2.5},
    'environmental': {'name': 'Environmental', 'multiplier': 3.0},
    'custom': {'name': 'Custom Distance', 'multiplier': 1.0}
}

LAYER_TYPES = {
    'boundaries': 'Site Boundary',
    'roads': 'Road/Access',
    'wetlands': 'Wetland',
    'floodplains': 'Floodplain',
    'power_lines': 'Transmission Line',
    'utilities': 'Utility Line',
    'substations': 'Substation',
    'easements': 'Easement',
    'existing_buildings': 'Existing Building',
    'power_generation': 'Power Generation',
    'other': 'Other'
}

class LayerManager:
    """Enhanced layer manager with automated classification and preset setback distances"""
    
    def __init__(self):
        self.layers = {
            'boundaries': [],
            'roads': [],
            'wetlands': [],
            'floodplains': [],
            'power_lines': [],
            'utilities': [],
            'substations': [],
            'easements': [],
            'existing_buildings': [],
            'power_generation': [],
            'other': []
        }
        self.layer_colors = {
            'boundaries': 'blue',
            'roads': 'gray',
            'wetlands': 'cyan',
            'floodplains': 'lightblue',
            'power_lines': 'red',
            'utilities': 'orange',
            'substations': 'purple',
            'easements': 'yellow',
            'existing_buildings': 'brown',
            'power_generation': 'darkred',
            'other': 'pink'
        }
        # Updated preset setback distances
        self.layer_base_setbacks = {
            'boundaries': 50,
            'roads': 20,
            'wetlands': 100,
            'floodplains': 10,
            'power_lines': 10,
            'utilities': 10,
            'substations': 25,
            'easements': 10,
            'existing_buildings': 100,
            'power_generation': 25,
            'other': 10
        }
        
        # Enhanced setback configuration with types
        self.layer_setback_types = {layer: 'standard' for layer in self.layers.keys()}
        self.custom_setback_distances = {layer: 0 for layer in self.layers.keys()}
        
        # Track which features are marked as constraints
        self.constraint_features = set()
        # All layers enabled by default
        self.enabled_layers = {layer: True for layer in self.layers.keys()}
    
    def get_effective_setback(self, layer_name: str) -> float:
        """Get effective setback distance for a layer"""
        base_distance = self.layer_base_setbacks.get(layer_name, 10)
        setback_type = self.layer_setback_types.get(layer_name, 'standard')
        
        if setback_type == 'custom':
            return self.custom_setback_distances.get(layer_name, base_distance)
        else:
            multiplier = SETBACK_TYPES.get(setback_type, {'multiplier': 1.0})['multiplier']
            return base_distance * multiplier
    
    def classify_feature(self, name: str, description: str = "") -> str:
        """Enhanced feature classification"""
        text = (name + " " + description).lower()
        
        # More specific classification patterns
        if any(word in text for word in ['road', 'street', 'drive', 'lane', 'avenue', 'highway', 'access', 'way', 'parkway', 'boulevard']):
            return 'roads'
        elif any(word in text for word in ['boundary', 'parcel', 'property', 'lot']):
            return 'boundaries'
        elif any(word in text for word in ['wetland', 'swamp', 'marsh', 'bog', 'fen', 'mire', 'slough', 'bayou']):
            return 'wetlands'
        elif any(word in text for word in ['flood', 'floodplain', 'flood zone', '100-year', '500-year', 'floodway', 'inundation']):
            return 'floodplains'
        elif any(word in text for word in ['power line', 'transmission', 'electrical line', 'high voltage', 'kv', 'kilovolt', 'tower']):
            return 'power_lines'
        elif any(word in text for word in ['substation', 'electrical sub', 'transformer', 'switchyard', 'converter']):
            return 'substations'
        elif any(word in text for word in ['utility', 'gas line', 'water line', 'sewer', 'pipeline', 'main', 'service']):
            return 'utilities'
        elif any(word in text for word in ['easement', 'setback', 'buffer', 'right-of-way', 'row', 'servitude']):
            return 'easements'
        elif any(word in text for word in ['building', 'structure', 'existing', 'facility', 'warehouse', 'office']):
            return 'existing_buildings'
        elif any(word in text for word in ['generator', 'generation', 'power gen', 'genset', 'solar', 'wind', 'turbine', 'panel']):
            return 'power_generation'
        else:
            return 'other'
    
    def add_feature(self, name: str, feature_data: dict, description: str = ""):
        """Add feature to appropriate layer using automated classification"""
        layer = self.classify_feature(name, description)
        feature_data['layer'] = layer
        feature_data['name'] = name
        self.layers[layer].append(feature_data)
    
    def mark_as_constraint(self, feature_name: str):
        """Mark a feature as a constraint"""
        self.constraint_features.add(feature_name)
    
    def unmark_as_constraint(self, feature_name: str):
        """Remove a feature from constraints"""
        self.constraint_features.discard(feature_name)
    
    def get_constraint_polygons(self) -> List[ShapelyPolygon]:
        """Get all constraint polygons from marked features with enhanced setbacks"""
        constraints = []
        
        for layer_name, features in self.layers.items():
            if layer_name == 'boundaries':
                continue
                
            setback = self.get_effective_setback(layer_name)
            
            for feature in features:
                feature_name = feature['name']
                if feature_name not in self.constraint_features:
                    continue
                    
                coords = feature['coordinates']
                geom_type = feature['type']
                
                try:
                    if geom_type == 'polygon' and len(coords) >= 3:
                        poly = ShapelyPolygon(coords)
                        if poly.is_valid:
                            buffered = poly.buffer(setback)
                            if buffered.is_valid:
                                constraints.append(buffered)
                    elif geom_type == 'linestring' and len(coords) >= 2:
                        line = LineString(coords)
                        buffered = line.buffer(setback)
                        if buffered.is_valid:
                            constraints.append(buffered)
                    elif geom_type == 'point' and coords:
                        point = Point(coords[0])
                        buffered = point.buffer(setback)
                        if buffered.is_valid:
                            constraints.append(buffered)
                except Exception as e:
                    print(f"Warning: Could not process constraint {feature_name}: {e}")
                    continue
        
        return constraints
    
    def get_power_features(self) -> List[Point]:
        """Get power line and power generation feature locations for substation placement"""
        power_points = []
        
        # Check power lines and power generation layers
        for layer_name in ['power_lines', 'power_generation']:
            for feature in self.layers[layer_name]:
                coords = feature['coordinates']
                geom_type = feature['type']
                
                try:
                    if geom_type == 'polygon' and len(coords) >= 3:
                        poly = ShapelyPolygon(coords)
                        if poly.is_valid:
                            power_points.append(poly.centroid)
                    elif geom_type == 'linestring' and len(coords) >= 2:
                        # Add points along the line
                        for coord in coords[::max(1, len(coords)//3)]:  # Sample points
                            power_points.append(Point(coord))
                    elif geom_type == 'point' and coords:
                        power_points.append(Point(coords[0]))
                except Exception as e:
                    print(f"Warning: Could not process power feature: {e}")
                    continue
        
        return power_points
    
    def get_site_boundary(self) -> Optional[ShapelyPolygon]:
        """Get the overall site boundary"""
        boundary_polygons = []
        
        # First try to get from boundary layer
        for feature in self.layers['boundaries']:
            coords = feature['coordinates']
            if feature['type'] == 'polygon' and len(coords) >= 3:
                try:
                    poly = ShapelyPolygon(coords)
                    if poly.is_valid and poly.area > 1000:
                        boundary_polygons.append(poly)
                except Exception as e:
                    print(f"Warning: Could not process boundary feature: {e}")
                    continue
        
        # If no boundary layer, create bounding box from all features
        if not boundary_polygons:
            all_coords = []
            for layer_features in self.layers.values():
                for feature in layer_features:
                    all_coords.extend(feature['coordinates'])
            
            if all_coords:
                xs, ys = zip(*all_coords)
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                
                buffer = 200
                boundary_coords = [
                    (min_x - buffer, min_y - buffer),
                    (max_x + buffer, min_y - buffer),
                    (max_x + buffer, max_y + buffer),
                    (min_x - buffer, max_y + buffer)
                ]
                try:
                    boundary_polygons.append(ShapelyPolygon(boundary_coords))
                except Exception as e:
                    print(f"Warning: Could not create site boundary: {e}")
                    return None
        
        if boundary_polygons:
            if len(boundary_polygons) == 1:
                return boundary_polygons[0]
            else:
                try:
                    return unary_union(boundary_polygons)
                except Exception as e:
                    print(f"Warning: Could not union boundary polygons: {e}")
                    return max(boundary_polygons, key=lambda p: p.area)
        
        return None


class KMLParser:
    """Enhanced KML parser"""
    
    def __init__(self):
        self.center_lat = 0
        self.center_lon = 0
        self.transformer = None
        self.layer_manager = LayerManager()
    
    def parse_kml_file(self, file_path: str) -> Dict:
        """Parse KML file with enhanced layer detection"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                kml_content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    kml_content = f.read()
            except Exception as e:
                raise ValueError(f"Could not read KML file: {e}")
        
        return self._parse_kml_content(kml_content)
    
    def _parse_kml_content(self, kml_content: str) -> Dict:
        """Parse KML content with folder/layer support"""
        features_data = {}
        
        try:
            root = ET.fromstring(kml_content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid KML format: {e}")
        
        namespaces = {
            'kml': 'http://www.opengis.net/kml/2.2',
            'gx': 'http://www.google.com/kml/ext/2.2'
        }
        
        # Parse folders first for layer organization
        folders = root.findall('.//Folder') or root.findall('.//kml:Folder', namespaces)
        
        for folder in folders:
            folder_name_elem = folder.find('name') or folder.find('kml:name', namespaces)
            folder_name = folder_name_elem.text if folder_name_elem is not None else "Unknown Folder"
            
            placemarks = folder.findall('.//Placemark') or folder.findall('.//kml:Placemark', namespaces)
            for placemark in placemarks:
                self._parse_placemark(placemark, features_data, folder_name, namespaces)
        
        # Parse standalone placemarks
        standalone_placemarks = []
        all_placemarks = root.findall('.//Placemark') or root.findall('.//kml:Placemark', namespaces)
        
        placemarks_in_folders = set()
        for folder in folders:
            folder_placemarks = folder.findall('.//Placemark') or folder.findall('.//kml:Placemark', namespaces)
            for pm in folder_placemarks:
                placemarks_in_folders.add(pm)
        
        for placemark in all_placemarks:
            if placemark not in placemarks_in_folders:
                standalone_placemarks.append(placemark)
        
        for placemark in standalone_placemarks:
            self._parse_placemark(placemark, features_data, "Main", namespaces)
        
        return features_data
    
    def _parse_placemark(self, placemark, features_data, folder_name, namespaces):
        """Parse individual placemark"""
        name_elem = placemark.find('name') or placemark.find('kml:name', namespaces)
        name = name_elem.text if name_elem is not None else f"Feature_{len(features_data) + 1}"
        
        desc_elem = placemark.find('description') or placemark.find('kml:description', namespaces)
        description = desc_elem.text if desc_elem is not None else ""
        
        full_name = f"{folder_name}: {name}" if folder_name != "Main" else name
        
        for geom_type, tag in [('polygon', 'Polygon'), ('linestring', 'LineString'), ('point', 'Point')]:
            elem = placemark.find(f'.//{tag}') or placemark.find(f'.//kml:{tag}', namespaces)
            if elem is not None:
                coords_elem = elem.find('.//coordinates') or elem.find('.//kml:coordinates', namespaces)
                if coords_elem is not None:
                    coordinates = self._parse_coordinates(coords_elem.text)
                    if coordinates and self._validate_coordinates(coordinates, geom_type):
                        feature_data = {
                            'coordinates': coordinates,
                            'type': geom_type,
                            'folder': folder_name,
                            'description': description
                        }
                        features_data[full_name] = feature_data
                        self.layer_manager.add_feature(full_name, feature_data, description)
                break
    
    def _validate_coordinates(self, coordinates, geom_type):
        """Validate coordinates based on geometry type"""
        if geom_type == 'polygon':
            return len(coordinates) >= 3
        elif geom_type == 'linestring':
            return len(coordinates) >= 2
        elif geom_type == 'point':
            return len(coordinates) >= 1
        return False
    
    def _parse_coordinates(self, coords_text: str) -> List[Tuple[float, float]]:
        """Parse coordinate string from KML"""
        coordinates = []
        
        if not coords_text:
            return coordinates
        
        coords_text = coords_text.strip().replace('\n', ' ').replace('\t', ' ')
        coord_groups = coords_text.split()
        
        for coord_group in coord_groups:
            if coord_group.strip():
                try:
                    parts = coord_group.split(',')
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        if -180 <= lon <= 180 and -90 <= lat <= 90:
                            coordinates.append((lon, lat))
                except (ValueError, IndexError):
                    continue
        
        return coordinates
    
    def convert_to_local_coordinates(self, features_data: Dict) -> Dict:
        """Convert lat/lon coordinates to local feet-based system"""
        if not features_data:
            return {}
        
        # Find bounds
        all_lats = []
        all_lons = []
        
        for feature_data in features_data.values():
            for lon, lat in feature_data['coordinates']:
                all_lats.append(lat)
                all_lons.append(lon)
        
        if not all_lats:
            return {}
        
        self.center_lat = np.mean(all_lats)
        self.center_lon = np.mean(all_lons)
        
        try:
            self.transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
            center_x, center_y = self.transformer.transform(self.center_lon, self.center_lat)
        except Exception as e:
            print(f"Warning: Could not create coordinate transformer: {e}")
            return {}
        
        local_features = {}
        
        for name, feature_data in features_data.items():
            local_coords = []
            for lon, lat in feature_data['coordinates']:
                try:
                    x, y = self.transformer.transform(lon, lat)
                    x_feet = (x - center_x) * 3.28084
                    y_feet = (y - center_y) * 3.28084
                    local_coords.append((x_feet, y_feet))
                except Exception as e:
                    print(f"Warning: Could not transform coordinate ({lon}, {lat}): {e}")
                    continue
            
            if local_coords:  # Only add if we have valid coordinates
                local_feature_data = {
                    'coordinates': local_coords,
                    'type': feature_data['type'],
                    'folder': feature_data['folder'],
                    'description': feature_data['description'],
                    'original_coordinates': feature_data['coordinates']
                }
                
                local_features[name] = local_feature_data
                
                # Update layer manager with local coordinates
                layer = self.layer_manager.classify_feature(name, feature_data['description'])
                for layer_features in self.layer_manager.layers.values():
                    for feature in layer_features:
                        if feature['name'] == name:
                            feature['coordinates'] = local_coords
                            break
        
        return local_features
    
    def local_to_latlon(self, x_feet: float, y_feet: float) -> Tuple[float, float]:
        """Convert local coordinates back to lat/lon"""
        if not self.transformer:
            return 0.0, 0.0
        
        try:
            x_meters = x_feet / 3.28084
            y_meters = y_feet / 3.28084
            
            center_x, center_y = self.transformer.transform(self.center_lon, self.center_lat)
            world_x = x_meters + center_x
            world_y = y_meters + center_y
            
            lon, lat = self.transformer.transform(world_x, world_y, direction='INVERSE')
            return lat, lon
        except Exception as e:
            print(f"Warning: Could not convert coordinates back to lat/lon: {e}")
            return 0.0, 0.0