"""
Optimization algorithms for TestFit
Extracted from your original testfit.py
"""

import numpy as np
from typing import List, Tuple, Optional
from shapely.geometry import Point, Polygon as ShapelyPolygon
from shapely.ops import unary_union

from .models import BuildingSpec, Building, Substation, SUBSTATION_CONFIGS
from .parser import LayerManager

def calculate_required_substations(total_power_mw: float, existing_power_mw: float = 0) -> List:
    """Calculate required substations based on total power minus existing capacity (500MW per acre rule)"""
    net_power_needed = max(0, total_power_mw - existing_power_mw)
    
    if net_power_needed <= 0:
        return []
    
    # Calculate total acres needed (500MW per acre)
    total_acres_needed = net_power_needed / 500.0
    
    substations = []
    remaining_acres = total_acres_needed
    
    # Add 1.0 acre substations first
    while remaining_acres >= 1.0:
        substations.append(SUBSTATION_CONFIGS[0])  # Default 1.0 acre config
        remaining_acres -= 1.0
    
    # Add smaller substations for remaining capacity
    if remaining_acres > 0:
        # Find best fit from available configs
        best_config = None
        for config in SUBSTATION_CONFIGS:
            if config.size_acres <= remaining_acres:
                if best_config is None or config.size_acres > best_config.size_acres:
                    best_config = config
        
        if best_config:
            substations.append(best_config)
        else:
            # If no perfect fit, use smallest available
            substations.append(SUBSTATION_CONFIGS[-1])
    
    return substations


class DataHallOptimizedPlacer:
    """Enhanced building placer with fixed constraint overlapping and existing substation support"""
    
    def __init__(self, layer_manager: LayerManager, building_specs: List[BuildingSpec], 
                 max_power_mw: float = 0, max_height_ft: float = 0, 
                 gen_yard_on_top: bool = False, cool_yard_on_top: bool = False,
                 existing_substation_mw: float = 0):
        self.layer_manager = layer_manager
        self.enabled_specs = [spec for spec in building_specs if spec.enabled]
        self.max_power_mw = max_power_mw
        self.max_height_ft = max_height_ft
        self.gen_yard_on_top = gen_yard_on_top
        self.cool_yard_on_top = cool_yard_on_top
        self.existing_substation_mw = existing_substation_mw
        
        # Filter building specs by height constraint
        if max_height_ft > 0:
            self.enabled_specs = [spec for spec in self.enabled_specs if spec.building_height <= max_height_ft]
        
        self.site_boundary = layer_manager.get_site_boundary()
        self.total_area = self.site_boundary.area if self.site_boundary else 0
        self.power_features = layer_manager.get_power_features()
        
        # Calculate buildable area once for reuse
        self.buildable_polygons = self._calculate_buildable_polygons()
    
    def _calculate_buildable_polygons(self) -> List[ShapelyPolygon]:
        """Calculate buildable polygons after applying all constraints"""
        if not self.site_boundary:
            return []
        
        # Start with site boundary
        buildable_area = self.site_boundary
        
        # Apply all constraint polygons
        constraints = self.layer_manager.get_constraint_polygons()
        
        for constraint in constraints:
            try:
                if constraint.is_valid and constraint.area > 0:
                    # Use buffer(0) to fix any topology issues
                    if not buildable_area.is_valid:
                        buildable_area = buildable_area.buffer(0)
                    if not constraint.is_valid:
                        constraint = constraint.buffer(0)
                    
                    buildable_area = buildable_area.difference(constraint)
            except Exception as e:
                print(f"Warning: Constraint application failed: {e}")
                continue
        
        # Handle multipolygon results and filter small areas
        buildable_areas = []
        if hasattr(buildable_area, 'geoms'):
            for geom in buildable_area.geoms:
                if hasattr(geom, 'area') and geom.area > 5000:  # Minimum 5000 sqft areas
                    if geom.is_valid:
                        buildable_areas.append(geom)
        elif hasattr(buildable_area, 'area') and buildable_area.area > 5000:
            if buildable_area.is_valid:
                buildable_areas.append(buildable_area)
        
        return buildable_areas
    
    def place_buildings_optimized(self, num_trials: int = 50, single_type_only: bool = True) -> Tuple[List[Building], List[Substation], dict]:
        """Optimize building placement with fixed constraint handling and existing substation support"""
        if not self.enabled_specs:
            return [], [], {'error': 'No enabled building specifications (check height constraints)'}
        
        if not self.buildable_polygons:
            return [], [], {'error': 'No buildable area after applying constraints'}
        
        best_buildings = []
        best_substations = []
        best_data_hall_area = 0
        all_results = []
        
        # Test each building type separately if single_type_only is True
        specs_to_test = self.enabled_specs if single_type_only else [self.enabled_specs]
        
        for spec_group in ([spec] if single_type_only else [self.enabled_specs] for spec in specs_to_test):
            for trial in range(num_trials):
                try:
                    buildings, substations = self._single_placement_trial(spec_group)
                    
                    total_data_hall = sum(b.data_hall_area for b in buildings)
                    total_power = sum(b.megawatts for b in buildings)
                    building_count = len(buildings)
                    total_area = sum(b.area for b in buildings)
                    total_substation_area = sum(s.area for s in substations)
                    
                    # Check power constraint
                    power_constrained = self.max_power_mw > 0 and total_power > self.max_power_mw
                    
                    result = {
                        'trial': trial,
                        'building_type': spec_group[0].name if len(spec_group) == 1 else 'Mixed',
                        'building_count': building_count,
                        'substation_count': len(substations),
                        'total_footprint_area': total_area,
                        'total_substation_area': total_substation_area,
                        'total_data_hall_area': total_data_hall,
                        'total_power_mw': total_power,
                        'power_constrained': power_constrained,
                        'buildings': buildings,
                        'substations': substations,
                        'existing_substation_capacity_mw': self.existing_substation_mw,
                        'new_substation_capacity_mw': sum(s.power_capacity_mw for s in substations if not s.is_existing)
                    }
                    all_results.append(result)
                    
                    # Only consider results that meet power constraints
                    if not power_constrained and total_data_hall > best_data_hall_area:
                        best_buildings = buildings[:]
                        best_substations = substations[:]
                        best_data_hall_area = total_data_hall
                
                except Exception as e:
                    print(f"Warning: Trial {trial} failed: {e}")
                    continue
        
        # Calculate statistics with division by zero protection
        buildable_area = sum(poly.area for poly in self.buildable_polygons)
        
        # Filter valid results (those meeting power constraints)
        valid_results = [r for r in all_results if not r['power_constrained']]
        
        if valid_results:
            data_hall_areas = [r['total_data_hall_area'] for r in valid_results]
            building_counts = [r['building_count'] for r in valid_results]
            substation_counts = [r['substation_count'] for r in valid_results]
            power_usage = [r['total_power_mw'] for r in valid_results]
        else:
            data_hall_areas = [0]
            building_counts = [0]
            substation_counts = [0]
            power_usage = [0]
        
        # Group results by building type
        type_results = {}
        for result in valid_results:
            btype = result['building_type']
            if btype not in type_results:
                type_results[btype] = []
            type_results[btype].append(result)
        
        total_substation_capacity = self.existing_substation_mw + sum(s.power_capacity_mw for s in best_substations if not s.is_existing)
        
        stats = {
            'best_building_count': len(best_buildings),
            'best_substation_count': len(best_substations),
            'best_data_hall_area': best_data_hall_area,
            'best_total_power_mw': sum(b.megawatts for b in best_buildings),
            'best_building_type': best_buildings[0].building_type if best_buildings else 'None',
            'mean_data_hall_area': np.mean(data_hall_areas) if data_hall_areas else 0,
            'mean_building_count': np.mean(building_counts) if building_counts else 0,
            'mean_substation_count': np.mean(substation_counts) if substation_counts else 0,
            'mean_power_usage': np.mean(power_usage) if power_usage else 0,
            'max_power_constraint': self.max_power_mw,
            'max_height_constraint': self.max_height_ft,
            'gen_yard_on_top': self.gen_yard_on_top,
            'cool_yard_on_top': self.cool_yard_on_top,
            'power_constrained_trials': len([r for r in all_results if r['power_constrained']]),
            'total_trials': len(all_results),
            'valid_trials': len(valid_results),
            'total_site_area': self.total_area,
            'buildable_area': buildable_area,
            'constraint_area': max(0, self.total_area - buildable_area) if buildable_area else 0,
            'type_performance': type_results,
            'all_results': all_results,
            'substation_area_required': sum(s.area for s in best_substations if not s.is_existing),
            'substation_acres_required': sum(s.size_acres for s in best_substations if not s.is_existing),
            'existing_substation_capacity_mw': self.existing_substation_mw,
            'total_substation_capacity_mw': total_substation_capacity,
            'new_substations_needed': len([s for s in best_substations if not s.is_existing])
        }
        
        return best_buildings, best_substations, stats
    
    def _single_placement_trial(self, building_specs: List[BuildingSpec]) -> Tuple[List[Building], List[Substation]]:
        """Single placement trial with proper constraint checking and existing substation support"""
        buildings = []
        substations = []
        building_id = 1
        group_id = 1
        current_power = 0.0
        
        if not self.buildable_polygons:
            return buildings, substations
        
        # Track placed infrastructure for collision detection
        placed_polygons = []
        
        # Place buildings in each buildable area
        for area in self.buildable_polygons:
            bounds = area.bounds
            area_width = bounds[2] - bounds[0]
            area_height = bounds[3] - bounds[1]
            
            # Choose best building spec for this area
            best_spec = None
            best_count = 0
            
            for spec in building_specs:
                # Skip if this would exceed power limit
                if self.max_power_mw > 0 and current_power + spec.avg_it_mw > self.max_power_mw:
                    continue
                
                # Test both orientations
                for orientation in [0, 90]:
                    width, length = spec.get_footprint_with_stacking(self.gen_yard_on_top, self.cool_yard_on_top)
                    if orientation == 90:
                        width, length = length, width
                    
                    # Estimate how many buildings could fit with proper spacing
                    spacing = 25
                    if width > 0 and length > 0:
                        cols = max(1, int((area_width - 100) // (width + spacing)))  # 50ft margin on each side
                        rows = max(1, int((area_height - 100) // (length + spacing)))
                        estimated_count = cols * rows
                        
                        if estimated_count > best_count:
                            best_count = estimated_count
                            best_spec = spec
            
            if best_spec:
                area_buildings = self._place_buildings_in_area(area, best_spec, building_id, group_id, current_power, placed_polygons)
                buildings.extend(area_buildings)
                current_power += sum(b.megawatts for b in area_buildings)
                building_id += len(area_buildings)
                group_id += 1
                
                # Add building polygons to placed infrastructure
                for building in area_buildings:
                    placed_polygons.append(building.get_shapely_polygon())
                
                # Stop if we've reached power limit
                if self.max_power_mw > 0 and current_power >= self.max_power_mw:
                    break
        
        # Calculate and place required substations with existing capacity consideration
        total_power = sum(b.megawatts for b in buildings)
        required_substation_specs = calculate_required_substations(total_power, self.existing_substation_mw)
        
        # Place new substations in available areas with preference for power features
        substation_id = 1
        for substation_spec in required_substation_specs:
            placed_substation = self._place_single_substation_smart(self.buildable_polygons, substation_spec, substation_id, placed_polygons)
            if placed_substation:
                placed_substation.is_existing = False  # Mark as new substation
                substations.append(placed_substation)
                placed_polygons.append(placed_substation.get_shapely_polygon())
                substation_id += 1
        
        return buildings, substations
    
    def _place_buildings_in_area(self, area: ShapelyPolygon, spec: BuildingSpec, 
                                start_id: int, group_id: int, current_power: float, placed_polygons: List[ShapelyPolygon]) -> List[Building]:
        """Place buildings in area with proper constraint validation"""
        buildings = []
        bounds = area.bounds
        
        # Try both orientations and pick the best
        best_buildings = []
        best_data_hall_area = 0
        
        for orientation in [0, 90]:
            trial_buildings = []
            trial_power = current_power
            
            width, length = spec.get_footprint_with_stacking(self.gen_yard_on_top, self.cool_yard_on_top)
            if orientation == 90:
                width, length = length, width
            
            spacing = 25
            margin = 50
            building_id = start_id
            
            # Grid placement with proper spacing
            y = bounds[1] + margin
            while y + length < bounds[3] - margin:
                x = bounds[0] + margin
                while x + width < bounds[2] - margin:
                    # Check power constraint
                    if self.max_power_mw > 0 and trial_power + spec.avg_it_mw > self.max_power_mw:
                        break
                    
                    # Create building for testing
                    test_building = Building(
                        x, y, spec,
                        rotation=orientation,
                        building_id=building_id,
                        group_id=group_id,
                        gen_yard_on_top=self.gen_yard_on_top,
                        cool_yard_on_top=self.cool_yard_on_top
                    )
                    
                    building_poly = test_building.get_shapely_polygon()
                    
                    # Validate placement
                    if self._validate_building_placement(building_poly, area, placed_polygons):
                        trial_buildings.append(test_building)
                        trial_power += spec.avg_it_mw
                        building_id += 1
                    
                    x += width + spacing
                    
                    if len(trial_buildings) >= 50:  # Limit per area
                        break
                
                y += length + spacing
                
                if len(trial_buildings) >= 50:
                    break
            
            # Check if this orientation is better
            trial_data_hall = sum(b.data_hall_area for b in trial_buildings)
            if trial_data_hall > best_data_hall_area:
                best_data_hall_area = trial_data_hall
                best_buildings = trial_buildings
        
        return best_buildings
    
    def _validate_building_placement(self, building_poly: ShapelyPolygon, area: ShapelyPolygon, placed_polygons: List[ShapelyPolygon]) -> bool:
        """Validate building placement against constraints"""
        try:
            # 1. Must be fully contained in buildable area
            if not area.contains(building_poly):
                return False
            
            # 2. Must not intersect with any placed infrastructure
            for placed_poly in placed_polygons:
                if building_poly.intersects(placed_poly):
                    return False
            
            # 3. Additional safety check with buffer
            buffered_building = building_poly.buffer(10)  # 10ft safety buffer
            if not area.contains(buffered_building):
                return False
            
            return True
        
        except Exception as e:
            print(f"Warning: Building validation failed: {e}")
            return False
    
    def _place_single_substation_smart(self, buildable_areas: List[ShapelyPolygon], substation_spec, 
                                      substation_id: int, placed_polygons: List[ShapelyPolygon]) -> Optional[Substation]:
        """Place a single substation with proper constraint validation"""
        best_position = None
        best_score = -1
        
        for area in buildable_areas:
            bounds = area.bounds
            area_width = bounds[2] - bounds[0]
            area_height = bounds[3] - bounds[1]
            
            # Try both orientations
            for orientation in [0, 90]:
                if orientation == 0:
                    sub_width = substation_spec.width
                    sub_length = substation_spec.length
                else:
                    sub_width = substation_spec.length
                    sub_length = substation_spec.width
                
                # Check if substation can fit in this area
                margin = 50
                if sub_width + 2*margin > area_width or sub_length + 2*margin > area_height:
                    continue
                
                # Try to place substation with proper spacing
                step_size = 50
                
                y = bounds[1] + margin
                while y + sub_length < bounds[3] - margin:
                    x = bounds[0] + margin
                    while x + sub_width < bounds[2] - margin:
                        # Create test substation
                        test_substation = Substation(
                            x, y, substation_spec,
                            rotation=orientation,
                            substation_id=substation_id
                        )
                        
                        substation_poly = test_substation.get_shapely_polygon()
                        
                        # Validate placement
                        if self._validate_substation_placement(substation_poly, area, placed_polygons):
                            # Calculate score based on proximity to power features
                            center_x = x + sub_width/2
                            center_y = y + sub_length/2
                            substation_center = Point(center_x, center_y)
                            score = self._calculate_substation_score(substation_center)
                            
                            if score > best_score:
                                best_score = score
                                best_position = {
                                    'x': x, 'y': y, 'orientation': orientation,
                                    'spec': substation_spec, 'id': substation_id
                                }
                        
                        x += step_size
                    y += step_size
        
        if best_position:
            return Substation(
                best_position['x'], best_position['y'], best_position['spec'],
                rotation=best_position['orientation'],
                substation_id=best_position['id']
            )
        
        return None
    
    def _validate_substation_placement(self, substation_poly: ShapelyPolygon, area: ShapelyPolygon, placed_polygons: List[ShapelyPolygon]) -> bool:
        """Validate substation placement"""
        try:
            # 1. Must be fully contained in buildable area
            if not area.contains(substation_poly):
                return False
            
            # 2. Must not intersect with any placed infrastructure
            for placed_poly in placed_polygons:
                if substation_poly.intersects(placed_poly):
                    return False
            
            # 3. Additional safety check with buffer
            buffered_substation = substation_poly.buffer(15)  # 15ft safety buffer
            if not area.contains(buffered_substation):
                return False
            
            return True
        
        except Exception as e:
            print(f"Warning: Substation validation failed: {e}")
            return False
    
    def _calculate_substation_score(self, substation_center: Point) -> float:
        """Calculate score for substation placement based on proximity to power features"""
        base_score = 1.0  # Base score for any valid placement
        
        if not self.power_features:
            return base_score
        
        # Find distance to nearest power feature
        min_distance = float('inf')
        for power_point in self.power_features:
            try:
                distance = substation_center.distance(power_point)
                min_distance = min(min_distance, distance)
            except Exception as e:
                print(f"Warning: Could not calculate distance to power feature: {e}")
                continue
        
        # Score decreases with distance (higher score for closer placement)
        # Max bonus of 10 points for being very close to power features
        if min_distance < float('inf'):
            proximity_bonus = max(0, 10 * (1 - min_distance / 1000))  # 1000 ft normalization
            return base_score + proximity_bonus
        
        return base_score