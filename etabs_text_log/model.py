"""
Core data model for parsed ETABS .$et files.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Literal


# --- Basics ---

@dataclass
class ProgramInfo:
    program: str                # "ETABS"
    version: str                # "22.1.0"
    build: Optional[str] = None
    source_file: Optional[str] = None  # path to .$et snapshot


@dataclass
class Story:
    name: str                   # "L14"
    elevation: float            # global Z
    height: Optional[float] = None
    is_master_story: bool = False
    index: Optional[int] = None  # sort order


@dataclass
class GridLine:
    name: str                   # "A", "1"
    coord: float                # X or Y coordinate
    direction: Literal["X", "Y"]


@dataclass
class Joint:
    name: str                   # joint label
    x: float
    y: float
    z: float
    story: Optional[str] = None  # filled by location tagging
    grid_x: Optional[str] = None
    grid_y: Optional[str] = None


# --- Sections / materials ---

@dataclass
class Material:
    name: str                  # "A992Fy50"
    type: Literal["steel", "concrete", "other"]
    # Only the handful of fields we care about in v1:
    E: Optional[float] = None
    Fy: Optional[float] = None
    fc: Optional[float] = None
    density: Optional[float] = None
    # plus raw field dict for anything else:
    raw_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class FrameSection:
    name: str                  # "W14X90"
    material: str              # Material.name
    shape_type: str            # "I", "Channel", etc.
    shape_label: Optional[str] = None   # vendor shape name if different
    # Minimal geometric props:
    area: Optional[float] = None
    Ix: Optional[float] = None
    Iy: Optional[float] = None
    J: Optional[float] = None
    # For unknown / extra fields:
    raw_fields: Dict[str, str] = field(default_factory=dict)


# --- Structural objects ---

@dataclass
class LocationInfo:
    story: Optional[str] = None
    grid_x: Optional[str] = None
    grid_y: Optional[str] = None
    # Optional: bounding region (for members spanning between grids)
    grid_x_span: Optional[Tuple[str, str]] = None
    grid_y_span: Optional[Tuple[str, str]] = None


@dataclass
class FrameObject:
    name: str                  # ETABS object label
    joint_i: str               # Joint.name
    joint_j: str               # Joint.name
    section: str               # FrameSection.name (from FRAME OBJECTS, may be overridden by LINE ASSIGNS)
    story: Optional[str] = None
    # Derived:
    object_type: Optional[Literal["column", "beam", "brace", "frame"]] = None
    location: LocationInfo = field(default_factory=LocationInfo)
    # Extra:
    raw_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class FrameAssignment:
    """
    Frame section assignment from LINE ASSIGNS section.
    Key: (frame_name, story) tuple
    """
    frame_name: str
    story: str
    section: str
    # Optional properties
    propmod_t: Optional[float] = None
    propmod_i22: Optional[float] = None
    propmod_i33: Optional[float] = None
    release: Optional[str] = None
    raw_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class AreaAssignment:
    """
    Area section assignment from AREA ASSIGNS section.
    Key: (area_name, story) tuple
    """
    area_name: str
    story: str
    section: str
    # Optional properties
    diaphragm: Optional[str] = None
    raw_fields: Dict[str, str] = field(default_factory=dict)


# --- Loads ---

@dataclass
class LoadPattern:
    name: str                  # "DEAD", "LL", "WINDX"
    load_type: str             # "DEAD", "LIVE", "WIND", etc. (ETABS type)
    self_weight_multiplier: float = 0.0
    raw_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class LoadCase:
    name: str
    case_type: str             # "Linear Static", etc.
    pattern: Optional[str] = None   # associated primary pattern if simple
    is_auto: bool = False
    raw_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class LoadComboTerm:
    name: str                  # pattern/case/combo name
    factor: float


@dataclass
class LoadCombo:
    name: str
    design_type: Optional[str] = None  # "Strength", "Service", etc.
    terms: List[LoadComboTerm] = field(default_factory=list)
    raw_fields: Dict[str, str] = field(default_factory=dict)


# --- Model root ---

@dataclass
class EtabsModel:
    program_info: ProgramInfo
    stories: Dict[str, Story] = field(default_factory=dict)
    grids: List[GridLine] = field(default_factory=list)
    joints: Dict[str, Joint] = field(default_factory=dict)
    frames: Dict[str, FrameObject] = field(default_factory=dict)
    materials: Dict[str, Material] = field(default_factory=dict)
    frame_sections: Dict[str, FrameSection] = field(default_factory=dict)
    load_patterns: Dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: Dict[str, LoadCase] = field(default_factory=dict)
    load_combos: Dict[str, LoadCombo] = field(default_factory=dict)
    
    # Section assignments (from LINE ASSIGNS and AREA ASSIGNS)
    frame_assignments: Dict[Tuple[str, str], FrameAssignment] = field(default_factory=dict)  # key: (frame_name, story)
    area_assignments: Dict[Tuple[str, str], AreaAssignment] = field(default_factory=dict)  # key: (area_name, story)

    # Optional: raw sections that we don't yet understand
    raw_sections: Dict[str, List[str]] = field(default_factory=dict)

