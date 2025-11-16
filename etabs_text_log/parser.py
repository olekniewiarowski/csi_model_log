"""
Parser for ETABS .$et (and .e2k) model text files.
"""
import re
from pathlib import Path
from typing import Dict, List, Iterable, Optional
from .model import (
    EtabsModel, ProgramInfo, Story, GridLine, Joint, Material, FrameSection,
    FrameObject, LoadPattern, LoadCase, LoadCombo, LoadComboTerm,
    FrameAssignment, AreaAssignment
)


def parse_sections_from_text(text: str) -> Dict[str, List[str]]:
    """
    Split raw text into a mapping: {section_name: [lines_without_header]}
    
    Example:
        "$ JOINT COORDINATES"
        "   J1   0.0 0.0 0.0"
        "$ FRAME OBJECTS"
        "   F1   J1  J2  ..."
    
    Returns:
        {"JOINT COORDINATES": [...], "FRAME OBJECTS": [...], ...}
    """
    sections: Dict[str, List[str]] = {}
    current_section: str | None = None
    current_lines: List[str] = []
    
    for line in text.splitlines():
        original_line = line
        line = line.strip()
        if not line:
            continue
            
        # Check if this is a section header (starts with $)
        if line.startswith("$"):
            # Save previous section if exists
            if current_section is not None:
                sections[current_section] = current_lines
            
            # Start new section
            # Handle special case: "$ File ..." is metadata, not a section
            if line.startswith("$ File "):
                # This is a file metadata line, skip it or store as special section
                current_section = "File"
                current_lines = [line[1:].strip()]  # Store the metadata
            else:
                current_section = line[1:].strip()  # Remove $ and whitespace
                current_lines = []
        else:
            # Add line to current section
            if current_section is not None:
                current_lines.append(line)
    
    # Don't forget the last section
    if current_section is not None:
        sections[current_section] = current_lines
    
    return sections


def extract_quoted_string(s: str) -> Optional[str]:
    """Extract first quoted string from a line."""
    match = re.search(r'"([^"]*)"', s)
    return match.group(1) if match else None


def extract_numeric_value(s: str, key: str) -> Optional[float]:
    """Extract numeric value after a key word."""
    # Look for pattern like "KEY value" or "KEY" value
    pattern = rf'\b{re.escape(key)}\s+([+-]?\d+\.?\d*[Ee]?[+-]?\d*)'
    match = re.search(pattern, s, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def parse_program_information(lines: Iterable[str]) -> ProgramInfo:
    """Parse PROGRAM INFORMATION section."""
    program = "ETABS"
    version = "Unknown"
    build = None
    
    for line in lines:
        line_upper = line.upper()
        if "PROGRAM" in line_upper:
            prog_match = extract_quoted_string(line)
            if prog_match:
                program = prog_match
        
        if "VERSION" in line_upper:
            ver_match = extract_quoted_string(line)
            if ver_match:
                version = ver_match
        
        if "BUILD" in line_upper:
            build_match = extract_numeric_value(line, "BUILD")
            if build_match:
                build = str(int(build_match))
    
    return ProgramInfo(program=program, version=version, build=build)


def parse_story_data(lines: Iterable[str]) -> Dict[str, Story]:
    """Parse STORIES or STORY DATA section."""
    stories: Dict[str, Story] = {}
    elevation_map: Dict[str, float] = {}
    story_list: List[str] = []
    
    for line in lines:
        if not line.strip().startswith("STORY"):
            continue
        
        # Extract story name
        story_name = extract_quoted_string(line)
        if not story_name:
            continue
        
        # Extract elevation or height
        elevation = extract_numeric_value(line, "ELEV")
        height = extract_numeric_value(line, "HEIGHT")
        
        if elevation is not None:
            elevation_map[story_name] = elevation
        elif height is not None:
            # If height is given, we'll need to calculate elevation from previous story
            elevation_map[story_name] = 0.0  # Placeholder, will calculate later
            story_list.append(story_name)
        else:
            elevation_map[story_name] = 0.0
            story_list.append(story_name)
    
    # Calculate elevations from heights (top to bottom)
    if story_list:
        current_elev = 0.0
        for story_name in reversed(story_list):
            if story_name in elevation_map:
                # Check if we have a height value
                for line in lines:
                    if story_name in line and "HEIGHT" in line.upper():
                        height = extract_numeric_value(line, "HEIGHT")
                        if height:
                            current_elev += height
                            elevation_map[story_name] = current_elev
                            break
    
    # Create Story objects
    for story_name, elev in elevation_map.items():
        stories[story_name] = Story(
            name=story_name,
            elevation=elev,
            is_master_story=False
        )
    
    return stories


def parse_grid_lines(lines: Iterable[str]) -> List[GridLine]:
    """Parse GRIDS section."""
    grids: List[GridLine] = []
    
    for line in lines:
        if not line.strip().startswith("GRID"):
            continue
        
        # Extract grid label and direction
        label = extract_quoted_string(line)
        if not label:
            continue
        
        # Extract direction (X or Y)
        direction = None
        if 'DIR "X"' in line or "DIR X" in line:
            direction = "X"
        elif 'DIR "Y"' in line or "DIR Y" in line:
            direction = "Y"
        
        if not direction:
            continue
        
        # Extract coordinate
        coord = extract_numeric_value(line, "COORD")
        if coord is not None:
            grids.append(GridLine(name=label, coord=coord, direction=direction))
    
    return grids


def parse_joint_coordinates(lines: Iterable[str]) -> Dict[str, Joint]:
    """Parse JOINT COORDINATES or POINT COORDINATES section."""
    joints: Dict[str, Joint] = {}
    
    for line in lines:
        # Format: J1 0.0 0.0 120.0 or POINT "1" 84 224
        parts = line.split()
        if len(parts) < 4:
            continue
        
        # Try to extract joint name (first token or quoted)
        joint_name = None
        if parts[0].startswith('"'):
            joint_name = extract_quoted_string(line)
            coords_start = 1
        else:
            joint_name = parts[0]
            coords_start = 1
        
        if not joint_name:
            continue
        
        # Extract coordinates
        try:
            if len(parts) >= coords_start + 3:
                x = float(parts[coords_start])
                y = float(parts[coords_start + 1])
                z = float(parts[coords_start + 2]) if len(parts) > coords_start + 2 else 0.0
            elif len(parts) >= coords_start + 2:
                # 2D coordinates, assume z=0
                x = float(parts[coords_start])
                y = float(parts[coords_start + 1])
                z = 0.0
            else:
                continue
            
            joints[joint_name] = Joint(name=joint_name, x=x, y=y, z=z)
        except (ValueError, IndexError):
            continue
    
    return joints


def parse_frame_objects(lines: Iterable[str], joints: Dict[str, Joint]) -> Dict[str, FrameObject]:
    """Parse FRAME OBJECTS or LINE CONNECTIVITIES section."""
    frames: Dict[str, FrameObject] = {}
    
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        
        # Format: F1 J1 J2 or LINE "C1" COLUMN "3" "3" 1
        frame_name = None
        joint_i = None
        joint_j = None
        section = None
        
        # Check for LINE format
        if parts[0].upper() == "LINE":
            frame_name = extract_quoted_string(line)
            # Extract all quoted strings (frame name, then point names)
            point_matches = re.findall(r'"([^"]*)"', line)
            if len(point_matches) >= 1:
                # First quoted string is the frame name
                # Remaining are point names
                if len(point_matches) >= 2:
                    joint_i = point_matches[1]
                    joint_j = point_matches[2] if len(point_matches) > 2 else point_matches[1]
        else:
            # Traditional format: F1 J1 J2
            frame_name = parts[0]
            if len(parts) >= 3:
                joint_i = parts[1]
                joint_j = parts[2]
            if len(parts) >= 4:
                section = parts[3]
        
        if frame_name and joint_i and joint_j:
            frames[frame_name] = FrameObject(
                name=frame_name,
                joint_i=joint_i,
                joint_j=joint_j,
                section=section or "Unknown"
            )
    
    return frames


def parse_material_properties(lines: Iterable[str]) -> Dict[str, Material]:
    """Parse MATERIAL PROPERTIES section."""
    materials: Dict[str, Material] = {}
    current_material: Optional[str] = None
    
    for line in lines:
        if not line.strip().startswith("MATERIAL"):
            continue
        
        # Extract material name
        mat_name = extract_quoted_string(line)
        if mat_name:
            current_material = mat_name
            if mat_name not in materials:
                # Determine material type
                mat_type = "other"
                if "TYPE" in line.upper():
                    type_match = extract_quoted_string(line)
                    if type_match:
                        type_upper = type_match.upper()
                        if "STEEL" in type_upper:
                            mat_type = "steel"
                        elif "CONCRETE" in type_upper:
                            mat_type = "concrete"
                
                materials[mat_name] = Material(
                    name=mat_name,
                    type=mat_type,
                    raw_fields={}
                )
        
        if current_material and current_material in materials:
            mat = materials[current_material]
            
            # Extract E (modulus of elasticity)
            e_val = extract_numeric_value(line, "E")
            if e_val:
                mat.E = e_val
            
            # Extract Fy (yield stress)
            fy_val = extract_numeric_value(line, "FY")
            if fy_val:
                mat.Fy = fy_val
            
            # Extract fc (concrete strength)
            fc_val = extract_numeric_value(line, "FC")
            if fc_val:
                mat.fc = fc_val
            
            # Extract density/weight per volume
            density = extract_numeric_value(line, "WEIGHTPERVOLUME")
            if density:
                mat.density = density
    
    return materials


def parse_frame_sections(lines: Iterable[str]) -> Dict[str, FrameSection]:
    """Parse FRAME SECTIONS section."""
    sections: Dict[str, FrameSection] = {}
    
    for line in lines:
        if not line.strip().startswith("FRAMESECTION"):
            continue
        
        # Extract section name
        section_name = extract_quoted_string(line)
        if not section_name:
            continue
        
        # Extract material
        material = extract_quoted_string(line.replace(section_name, "", 1))
        if not material:
            # Try to find MATERIAL keyword
            mat_match = re.search(r'MATERIAL\s+"([^"]*)"', line)
            if mat_match:
                material = mat_match.group(1)
        
        # Extract shape
        shape = extract_quoted_string(line.replace(section_name, "", 1).replace(material or "", "", 1))
        if not shape:
            # Try to find SHAPE keyword
            shape_match = re.search(r'SHAPE\s+"([^"]*)"', line)
            if shape_match:
                shape = shape_match.group(1)
        
        if section_name not in sections:
            sections[section_name] = FrameSection(
                name=section_name,
                material=material or "Unknown",
                shape_type="I",  # Default, could be improved
                shape_label=shape,
                raw_fields={}
            )
    
    return sections


def parse_load_patterns(lines: Iterable[str]) -> Dict[str, LoadPattern]:
    """Parse LOAD PATTERNS section."""
    patterns: Dict[str, LoadPattern] = {}
    
    for line in lines:
        if not line.strip().startswith("LOADPATTERN"):
            continue
        
        # Extract pattern name
        pattern_name = extract_quoted_string(line)
        if not pattern_name:
            continue
        
        # Extract type
        load_type = "Dead"
        if "TYPE" in line.upper():
            type_match = extract_quoted_string(line.replace(pattern_name, "", 1))
            if type_match:
                load_type = type_match
        
        # Extract self-weight multiplier
        self_weight = extract_numeric_value(line, "SELFWEIGHT")
        if self_weight is None:
            self_weight = 0.0
        
        patterns[pattern_name] = LoadPattern(
            name=pattern_name,
            load_type=load_type,
            self_weight_multiplier=self_weight
        )
    
    return patterns


def parse_load_cases(lines: Iterable[str]) -> Dict[str, LoadCase]:
    """Parse LOAD CASES section."""
    cases: Dict[str, LoadCase] = {}
    current_case: Optional[str] = None
    
    for line in lines:
        if not line.strip().startswith("LOADCASE"):
            continue
        
        # Extract case name
        case_name = extract_quoted_string(line)
        if case_name:
            current_case = case_name
            if case_name not in cases:
                # Extract case type
                case_type = "Linear Static"
                if "TYPE" in line.upper():
                    type_match = extract_quoted_string(line.replace(case_name, "", 1))
                    if type_match:
                        case_type = type_match
                
                cases[case_name] = LoadCase(
                    name=case_name,
                    case_type=case_type,
                    is_auto=False
                )
        
        if current_case and current_case in cases:
            # Extract associated pattern
            if "LOADPAT" in line.upper():
                pattern = extract_quoted_string(line)
                if pattern:
                    cases[current_case].pattern = pattern
    
    return cases


def parse_load_combinations(lines: Iterable[str]) -> Dict[str, LoadCombo]:
    """Parse LOAD COMBINATIONS section."""
    combos: Dict[str, LoadCombo] = {}
    current_combo: Optional[str] = None
    
    for line in lines:
        if not line.strip().startswith("LOADCOMBO"):
            continue
        
        # Extract combo name
        combo_name = extract_quoted_string(line)
        if combo_name:
            current_combo = combo_name
            if combo_name not in combos:
                # Extract design type
                design_type = None
                if "DESIGNTYPE" in line.upper():
                    dt_match = extract_quoted_string(line.replace(combo_name, "", 1))
                    if dt_match:
                        design_type = dt_match
                
                combos[combo_name] = LoadCombo(
                    name=combo_name,
                    design_type=design_type,
                    terms=[]
                )
        
        if current_combo and current_combo in combos:
            combo = combos[current_combo]
            
            # Parse terms: LOADCOMBO "Combo1" LOADPAT "D" SF 1.2 LOADPAT "L" SF 1.6
            # Look for LOADPAT, LOADCASE, or LOADCOMBO followed by SF
            term_pattern = r'(LOADPAT|LOADCASE|LOADCOMBO)\s+"([^"]*)"\s+SF\s+([+-]?\d+\.?\d*)'
            matches = re.finditer(term_pattern, line, re.IGNORECASE)
            
            for match in matches:
                term_name = match.group(2)
                factor = float(match.group(3))
                combo.terms.append(LoadComboTerm(name=term_name, factor=factor))
    
    return combos


def parse_line_assigns(lines: Iterable[str]) -> Dict[tuple[str, str], FrameAssignment]:
    """
    Parse LINE ASSIGNS section.
    Format: LINEASSIGN "FrameName" "Story" SECTION "SectionName" ...
    
    Returns dict keyed by (frame_name, story) tuple.
    """
    assignments: Dict[tuple[str, str], FrameAssignment] = {}
    
    for line in lines:
        if not line.strip().startswith("LINEASSIGN"):
            continue
        
        # Extract quoted strings: frame name, story, section
        quoted_strings = re.findall(r'"([^"]*)"', line)
        if len(quoted_strings) < 3:
            continue
        
        frame_name = quoted_strings[0]
        story = quoted_strings[1]
        section = None
        
        # Find SECTION keyword and extract section name
        section_match = re.search(r'SECTION\s+"([^"]*)"', line, re.IGNORECASE)
        if section_match:
            section = section_match.group(1)
        elif len(quoted_strings) >= 3:
            # Sometimes section is the third quoted string
            section = quoted_strings[2]
        
        if not section:
            continue
        
        # Extract optional properties
        propmod_t = extract_numeric_value(line, "PROPMODT")
        propmod_i22 = extract_numeric_value(line, "PROPMODI22")
        propmod_i33 = extract_numeric_value(line, "PROPMODI33")
        
        release = None
        release_match = re.search(r'RELEASE\s+"([^"]*)"', line, re.IGNORECASE)
        if release_match:
            release = release_match.group(1)
        
        key = (frame_name, story)
        assignments[key] = FrameAssignment(
            frame_name=frame_name,
            story=story,
            section=section,
            propmod_t=propmod_t,
            propmod_i22=propmod_i22,
            propmod_i33=propmod_i33,
            release=release
        )
    
    return assignments


def parse_area_assigns(lines: Iterable[str]) -> Dict[tuple[str, str], AreaAssignment]:
    """
    Parse AREA ASSIGNS section.
    Format: AREAASSIGN "AreaName" "Story" SECTION "SectionName" ...
    
    Returns dict keyed by (area_name, story) tuple.
    """
    assignments: Dict[tuple[str, str], AreaAssignment] = {}
    
    for line in lines:
        if not line.strip().startswith("AREAASSIGN"):
            continue
        
        # Extract quoted strings: area name, story, section
        quoted_strings = re.findall(r'"([^"]*)"', line)
        if len(quoted_strings) < 2:
            continue
        
        area_name = quoted_strings[0]
        story = quoted_strings[1]
        section = None
        
        # Find SECTION keyword and extract section name
        section_match = re.search(r'SECTION\s+"([^"]*)"', line, re.IGNORECASE)
        if section_match:
            section = section_match.group(1)
        elif len(quoted_strings) >= 3:
            section = quoted_strings[2]
        
        if not section:
            continue
        
        # Extract optional properties
        diaphragm = None
        diaphragm_match = re.search(r'DIAPH\s+"([^"]*)"', line, re.IGNORECASE)
        if diaphragm_match:
            diaphragm = diaphragm_match.group(1)
        
        key = (area_name, story)
        assignments[key] = AreaAssignment(
            area_name=area_name,
            story=story,
            section=section,
            diaphragm=diaphragm
        )
    
    return assignments


def parse_et_file(path: str | Path) -> EtabsModel:
    """
    Parse an ETABS .$et (or .e2k) model text file into an EtabsModel.
    
    Responsibilities:
    - Read file as text.
    - Split into sections using lines starting with '$ ' as headers.
    - For each known section, call a section-specific parser function.
    - Build and return an EtabsModel instance.
    - Unknown sections are stored in EtabsModel.raw_sections.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    
    text = path.read_text(encoding="utf-8", errors="ignore")
    sections = parse_sections_from_text(text)
    
    # Extract program info
    program_info = ProgramInfo(
        program="ETABS",
        version="Unknown",
        source_file=str(path)
    )
    
    if "PROGRAM INFORMATION" in sections:
        program_info = parse_program_information(sections["PROGRAM INFORMATION"])
        program_info.source_file = str(path)
    elif "PROGRAM CONTROL" in sections:
        # Fallback to old format
        for line in sections["PROGRAM CONTROL"]:
            if "VERSION" in line.upper():
                parts = line.split()
                for i, part in enumerate(parts):
                    if "VERSION" in part.upper() and i + 1 < len(parts):
                        program_info.version = parts[i + 1]
                        break
    
    # Create model
    model = EtabsModel(program_info=program_info)
    
    # Parse sections
    if "STORIES - IN SEQUENCE FROM TOP" in sections:
        model.stories = parse_story_data(sections["STORIES - IN SEQUENCE FROM TOP"])
    elif "STORY DATA" in sections:
        model.stories = parse_story_data(sections["STORY DATA"])
    
    if "GRIDS" in sections:
        model.grids = parse_grid_lines(sections["GRIDS"])
    
    if "JOINT COORDINATES" in sections:
        model.joints = parse_joint_coordinates(sections["JOINT COORDINATES"])
    elif "POINT COORDINATES" in sections:
        model.joints = parse_joint_coordinates(sections["POINT COORDINATES"])
    
    if "FRAME OBJECTS" in sections:
        model.frames = parse_frame_objects(sections["FRAME OBJECTS"], model.joints)
    elif "LINE CONNECTIVITIES" in sections:
        model.frames = parse_frame_objects(sections["LINE CONNECTIVITIES"], model.joints)
    
    if "MATERIAL PROPERTIES" in sections:
        model.materials = parse_material_properties(sections["MATERIAL PROPERTIES"])
    
    if "FRAME SECTIONS" in sections:
        model.frame_sections = parse_frame_sections(sections["FRAME SECTIONS"])
    
    if "LOAD PATTERNS" in sections:
        model.load_patterns = parse_load_patterns(sections["LOAD PATTERNS"])
    
    if "LOAD CASES" in sections:
        model.load_cases = parse_load_cases(sections["LOAD CASES"])
    
    if "LOAD COMBINATIONS" in sections:
        model.load_combos = parse_load_combinations(sections["LOAD COMBINATIONS"])
    
    # Parse section assignments
    if "LINE ASSIGNS" in sections:
        model.frame_assignments = parse_line_assigns(sections["LINE ASSIGNS"])
    
    if "AREA ASSIGNS" in sections:
        model.area_assignments = parse_area_assigns(sections["AREA ASSIGNS"])
    
    # Note: All sections are stored in raw_sections for reference
    # The following sections are recognized but not yet fully parsed:
    # - CONTROLS (units, titles, preferences)
    # - DIAPHRAGM NAMES
    # - REBAR DEFINITIONS
    # - AUTO SELECT SECTION LISTS
    # - CONCRETE SECTIONS
    # - TENDON SECTIONS
    # - SLAB PROPERTIES
    # - DECK PROPERTIES
    # - WALL PROPERTIES
    # - LINK PROPERTIES
    # - PANEL ZONE PROPERTIES
    # - PIER/SPANDREL NAMES
    # - ANALYSIS OPTIONS
    # - MASS SOURCE
    # - FUNCTIONS
    # - GENERALIZED DISPLACEMENTS
    # - STEEL DESIGN PREFERENCES
    # - CONCRETE DESIGN PREFERENCES
    # - COMPOSITE DESIGN PREFERENCES
    # - COMPOSITE COLUMN DESIGN PREFERENCES
    # - WALL DESIGN PREFERENCES
    # - CONCRETE SLAB DESIGN PREFERENCES
    # - TABLE SETS
    # - PROJECT INFORMATION
    # - LOG (history/comments)
    # - END OF MODEL FILE (marker)
    
    # Store all sections in raw_sections for reference
    model.raw_sections = sections
    
    return model
