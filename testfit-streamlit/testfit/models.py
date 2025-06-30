"""
TestFit Data Models
Extracted from your original testfit.py
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
from shapely.geometry import Polygon as ShapelyPolygon

@dataclass
class BuildingSpec:
    """Enhanced building specification with comprehensive data center specifics"""
    name: str
    num_stories: int
    num_data_halls: int
    building_height: float
    screen_height: float
    width: float
    length: float
    gen_yard: float
    cool_yard: float
    gross_sqft: float
    data_hall_sqft: float
    low_it_mw: float
    high_it_mw: float
    low_watt_sqft: float
    high_watt_sqft: float
    utility_low_pue_mw: float
    utility_high_pue_mw: float
    color: str = 'lightblue'
    enabled: bool = True
    
    @property
    def footprint_width(self) -> float:
        """Width including gen yard or cool yard (whichever applies to width dimension)"""
        if self.width <= self.length:  # Width is shorter dimension
            return self.width + self.gen_yard + self.cool_yard
        else:  # Width is longer dimension
            return self.width + self.gen_yard
    
    @property
    def footprint_length(self) -> float:
        """Length including cool yard if length is shorter dimension"""
        if self.length < self.width:  # Length is shorter dimension
            return self.length + self.cool_yard
        else:  # Length is longer dimension  
            return self.length
    
    def get_footprint_with_stacking(self, gen_yard_on_top: bool, cool_yard_on_top: bool) -> Tuple[float, float]:
        """Get footprint dimensions considering stacking options"""
        base_width = self.width
        base_length = self.length
        
        # Apply gen yard (always to width in base implementation)
        if gen_yard_on_top:
            width_with_gen = base_width
        else:
            width_with_gen = base_width + self.gen_yard
        
        # Apply cool yard based on which dimension is shorter
        if self.width <= self.length:  # Width is shorter
            if cool_yard_on_top:
                final_width = width_with_gen
                final_length = base_length
            else:
                final_width = width_with_gen + self.cool_yard
                final_length = base_length
        else:  # Length is shorter
            if cool_yard_on_top:
                final_width = width_with_gen
                final_length = base_length
            else:
                final_width = width_with_gen
                final_length = base_length + self.cool_yard
        
        return final_width, final_length
    
    @property
    def total_footprint(self) -> float:
        """Total building footprint area"""
        return self.footprint_width * self.footprint_length
    
    @property
    def data_hall_ratio(self) -> float:
        """Ratio of data hall to gross area"""
        return self.data_hall_sqft / max(self.gross_sqft, 1.0) if self.gross_sqft > 0 else 0
    
    @property
    def avg_it_mw(self) -> float:
        """Average IT power capacity"""
        return (self.low_it_mw + self.high_it_mw) / 2.0
    
    @property
    def avg_watt_sqft(self) -> float:
        """Average watts per square foot"""
        return (self.low_watt_sqft + self.high_watt_sqft) / 2.0
    
    @property
    def avg_utility_pue_mw(self) -> float:
        """Average utility power with PUE"""
        return (self.utility_low_pue_mw + self.utility_high_pue_mw) / 2.0

@dataclass
class SubstationSpec:
    """Substation specification"""
    size_acres: float
    width: float
    length: float
    
    @property
    def area_sqft(self) -> float:
        return self.size_acres * 43560  # Convert acres to square feet
    
    @property
    def footprint_area(self) -> float:
        return self.width * self.length

@dataclass
class Building:
    x: float  # feet from origin
    y: float  # feet from origin
    building_spec: BuildingSpec
    rotation: float = 0.0  # rotation angle in degrees
    lat: float = 0.0
    lon: float = 0.0
    building_id: int = 0
    corners_latlon: List[Tuple[float, float]] = None
    group_id: int = 0  # buildings in same group share orientation
    gen_yard_on_top: bool = False
    cool_yard_on_top: bool = False
    
    def __post_init__(self):
        """Initialize corners_latlon if None"""
        if self.corners_latlon is None:
            self.corners_latlon = []
    
    @property
    def width(self) -> float:
        w, l = self.building_spec.get_footprint_with_stacking(self.gen_yard_on_top, self.cool_yard_on_top)
        return w
    
    @property
    def length(self) -> float:
        w, l = self.building_spec.get_footprint_with_stacking(self.gen_yard_on_top, self.cool_yard_on_top)
        return l
    
    @property
    def area(self) -> float:
        return self.width * self.length
    
    @property
    def data_hall_area(self) -> float:
        return self.building_spec.data_hall_sqft
    
    @property
    def megawatts(self) -> float:
        return self.building_spec.avg_it_mw
    
    @property
    def building_type(self) -> str:
        return self.building_spec.name
    
    def get_corners_local(self) -> List[Tuple[float, float]]:
        """Get building corners in local coordinates with rotation"""
        corners = [
            (0, 0),
            (self.width, 0),
            (self.width, self.length),
            (0, self.length)
        ]
        
        if abs(self.rotation) > 0.1:
            rad = math.radians(self.rotation)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            
            center_x = self.width / 2.0
            center_y = self.length / 2.0
            
            rotated_corners = []
            for x, y in corners:
                x_rel = x - center_x
                y_rel = y - center_y
                
                new_x_rel = x_rel * cos_r - y_rel * sin_r
                new_y_rel = x_rel * sin_r + y_rel * cos_r
                
                final_x = new_x_rel + center_x + self.x
                final_y = new_y_rel + center_y + self.y
                
                rotated_corners.append((final_x, final_y))
            
            return rotated_corners
        else:
            return [(x + self.x, y + self.y) for x, y in corners]
    
    def get_shapely_polygon(self) -> ShapelyPolygon:
        """Get building as Shapely polygon for collision detection"""
        corners = self.get_corners_local()
        try:
            poly = ShapelyPolygon(corners)
            if not poly.is_valid:
                poly = poly.buffer(0)
            return poly
        except Exception as e:
            print(f"Warning: Could not create polygon for building {self.building_id}: {e}")
            return ShapelyPolygon([
                (self.x, self.y),
                (self.x + self.width, self.y),
                (self.x + self.width, self.y + self.length),
                (self.x, self.y + self.length)
            ])

@dataclass
class Substation:
    """Substation object"""
    x: float
    y: float
    substation_spec: SubstationSpec
    rotation: float = 0.0
    substation_id: int = 0
    lat: float = 0.0
    lon: float = 0.0
    corners_latlon: List[Tuple[float, float]] = None
    is_existing: bool = False
    
    def __post_init__(self):
        if self.corners_latlon is None:
            self.corners_latlon = []
    
    @property
    def width(self) -> float:
        return self.substation_spec.width
    
    @property
    def length(self) -> float:
        return self.substation_spec.length
    
    @property
    def area(self) -> float:
        return self.substation_spec.footprint_area
    
    @property
    def size_acres(self) -> float:
        return self.substation_spec.size_acres
    
    @property
    def power_capacity_mw(self) -> float:
        return self.size_acres * 500
    
    def get_corners_local(self) -> List[Tuple[float, float]]:
        """Get substation corners in local coordinates with rotation"""
        corners = [
            (0, 0),
            (self.width, 0),
            (self.width, self.length),
            (0, self.length)
        ]
        
        if abs(self.rotation) > 0.1:
            rad = math.radians(self.rotation)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            
            center_x = self.width / 2.0
            center_y = self.length / 2.0
            
            rotated_corners = []
            for x, y in corners:
                x_rel = x - center_x
                y_rel = y - center_y
                
                new_x_rel = x_rel * cos_r - y_rel * sin_r
                new_y_rel = x_rel * sin_r + y_rel * cos_r
                
                final_x = new_x_rel + center_x + self.x
                final_y = new_y_rel + center_y + self.y
                
                rotated_corners.append((final_x, final_y))
            
            return rotated_corners
        else:
            return [(x + self.x, y + self.y) for x, y in corners]
    
    def get_shapely_polygon(self) -> ShapelyPolygon:
        """Get substation as Shapely polygon for collision detection"""
        corners = self.get_corners_local()
        try:
            poly = ShapelyPolygon(corners)
            if not poly.is_valid:
                poly = poly.buffer(0)
            return poly
        except Exception as e:
            print(f"Warning: Could not create polygon for substation {self.substation_id}: {e}")
            return ShapelyPolygon([
                (self.x, self.y),
                (self.x + self.width, self.y),
                (self.x + self.width, self.y + self.length),
                (self.x, self.y + self.length)
            ])

# Standard substation configurations
SUBSTATION_CONFIGS = [
    SubstationSpec(1.0, 208, 209),
    SubstationSpec(1.0, 156, 278),
    SubstationSpec(1.0, 209, 209),
    SubstationSpec(0.75, 181, 181),
    SubstationSpec(0.5, 148, 148),
    SubstationSpec(0.25, 104, 104),
]

# Default building specifications
DEFAULT_BUILDING_SPECS = [
    BuildingSpec(
        name="Small Data Center", num_stories=1, num_data_halls=1, building_height=20, screen_height=16,
        width=100, length=60, gen_yard=20, cool_yard=15, gross_sqft=7200, data_hall_sqft=5400,
        low_it_mw=10.0, high_it_mw=20.0, low_watt_sqft=185, high_watt_sqft=370,
        utility_low_pue_mw=15.0, utility_high_pue_mw=30.0, color="lightcoral", enabled=True
    ),
    BuildingSpec(
        name="Medium Data Center", num_stories=1, num_data_halls=2, building_height=24, screen_height=20,
        width=150, length=80, gen_yard=30, cool_yard=20, gross_sqft=14400, data_hall_sqft=10800,
        low_it_mw=20.0, high_it_mw=30.0, low_watt_sqft=185, high_watt_sqft=278,
        utility_low_pue_mw=30.0, utility_high_pue_mw=45.0, color="lightblue", enabled=True
    ),
    BuildingSpec(
        name="Large Data Center", num_stories=1, num_data_halls=3, building_height=28, screen_height=24,
        width=200, length=100, gen_yard=40, cool_yard=25, gross_sqft=24000, data_hall_sqft=18000,
        low_it_mw=35.0, high_it_mw=45.0, low_watt_sqft=194, high_watt_sqft=250,
        utility_low_pue_mw=52.5, utility_high_pue_mw=67.5, color="lightgreen", enabled=True
    ),
    BuildingSpec(
        name="Hyperscale Data Center", num_stories=1, num_data_halls=6, building_height=36, screen_height=32,
        width=300, length=150, gen_yard=60, cool_yard=40, gross_sqft=54000, data_hall_sqft=40500,
        low_it_mw=80.0, high_it_mw=120.0, low_watt_sqft=198, high_watt_sqft=296,
        utility_low_pue_mw=120.0, utility_high_pue_mw=180.0, color="orange", enabled=True
    )
]