"""
Diff engine: compare two EtabsModel instances and produce raw diff objects.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from .model import EtabsModel, LocationInfo


@dataclass
class FieldChange:
    field: str
    old: Any
    new: Any


@dataclass
class ObjectAdded:
    object_type: str           # "frame", "joint", "material", "load_combo", ...
    key: str                   # e.g. frame name
    new_data: Dict[str, Any]   # serialized snapshot


@dataclass
class ObjectRemoved:
    object_type: str
    key: str
    old_data: Dict[str, Any]


@dataclass
class ObjectModified:
    object_type: str
    key: str
    changes: List[FieldChange]
    # Optional helper fields:
    location: Optional[LocationInfo] = None  # for frames/joints/areas


@dataclass
class RawDiff:
    """
    Raw, un-aggregated changes grouped by type.
    """
    added: List[ObjectAdded]
    removed: List[ObjectRemoved]
    modified: List[ObjectModified]


def diff_models(
    old: EtabsModel,
    new: EtabsModel,
    *,
    numeric_tol: Optional[Dict[str, float]] = None,
) -> RawDiff:
    """
    Compare two EtabsModel instances and produce a RawDiff.

    - numeric_tol: Optional mapping from field name to absolute tolerance;
      values below tolerance are treated as unchanged.
    - object identity:
        - For collections keyed by name (materials, frame sections, load combos),
          set identity is straightforward.
        - For frames/joints, rely primarily on object name; identity heuristics
          can be extended later if needed.
    """
    if numeric_tol is None:
        numeric_tol = {
            "elevation": 1e-3,
            "coord": 1e-3,
            "E": 1e3,
            "Fy": 100,
            "fc": 10,
        }
    
    added: List[ObjectAdded] = []
    removed: List[ObjectRemoved] = []
    modified: List[ObjectModified] = []
    
    # Diff each collection type
    added.extend(_diff_dict_collection("story", old.stories, new.stories, numeric_tol))
    removed.extend(_diff_dict_collection_removed("story", old.stories, new.stories))
    modified.extend(_diff_dict_collection_modified("story", old.stories, new.stories, numeric_tol))
    
    # Grids are stored as a list, need special handling
    added.extend(_diff_list_collection("grid", old.grids, new.grids, numeric_tol))
    removed.extend(_diff_list_collection_removed("grid", old.grids, new.grids))
    
    added.extend(_diff_dict_collection("joint", old.joints, new.joints, numeric_tol))
    removed.extend(_diff_dict_collection_removed("joint", old.joints, new.joints))
    modified.extend(_diff_dict_collection_modified("joint", old.joints, new.joints, numeric_tol, include_location=True))
    
    added.extend(_diff_dict_collection("frame", old.frames, new.frames, numeric_tol))
    removed.extend(_diff_dict_collection_removed("frame", old.frames, new.frames))
    modified.extend(_diff_dict_collection_modified("frame", old.frames, new.frames, numeric_tol, include_location=True))
    
    added.extend(_diff_dict_collection("material", old.materials, new.materials, numeric_tol))
    removed.extend(_diff_dict_collection_removed("material", old.materials, new.materials))
    modified.extend(_diff_dict_collection_modified("material", old.materials, new.materials, numeric_tol))
    
    added.extend(_diff_dict_collection("frame_section", old.frame_sections, new.frame_sections, numeric_tol))
    removed.extend(_diff_dict_collection_removed("frame_section", old.frame_sections, new.frame_sections))
    modified.extend(_diff_dict_collection_modified("frame_section", old.frame_sections, new.frame_sections, numeric_tol))
    
    added.extend(_diff_dict_collection("load_pattern", old.load_patterns, new.load_patterns, numeric_tol))
    removed.extend(_diff_dict_collection_removed("load_pattern", old.load_patterns, new.load_patterns))
    modified.extend(_diff_dict_collection_modified("load_pattern", old.load_patterns, new.load_patterns, numeric_tol))
    
    added.extend(_diff_dict_collection("load_case", old.load_cases, new.load_cases, numeric_tol))
    removed.extend(_diff_dict_collection_removed("load_case", old.load_cases, new.load_cases))
    modified.extend(_diff_dict_collection_modified("load_case", old.load_cases, new.load_cases, numeric_tol))
    
    added.extend(_diff_dict_collection("load_combo", old.load_combos, new.load_combos, numeric_tol))
    removed.extend(_diff_dict_collection_removed("load_combo", old.load_combos, new.load_combos))
    modified.extend(_diff_dict_collection_modified("load_combo", old.load_combos, new.load_combos, numeric_tol))
    
    # Diff frame assignments (from LINE ASSIGNS)
    added.extend(_diff_dict_collection("frame_assignment", old.frame_assignments, new.frame_assignments, numeric_tol))
    removed.extend(_diff_dict_collection_removed("frame_assignment", old.frame_assignments, new.frame_assignments))
    modified.extend(_diff_dict_collection_modified("frame_assignment", old.frame_assignments, new.frame_assignments, numeric_tol))
    
    # Diff area assignments (from AREA ASSIGNS)
    added.extend(_diff_dict_collection("area_assignment", old.area_assignments, new.area_assignments, numeric_tol))
    removed.extend(_diff_dict_collection_removed("area_assignment", old.area_assignments, new.area_assignments))
    modified.extend(_diff_dict_collection_modified("area_assignment", old.area_assignments, new.area_assignments, numeric_tol))
    
    # Diff raw_sections (unparsed sections like AREA ASSIGNS, LINE ASSIGNS, etc.)
    # Note: We still diff raw_sections for sections we don't parse, but LINE/AREA ASSIGNS
    # are now handled above via frame_assignments and area_assignments
    added.extend(_diff_raw_sections(old.raw_sections, new.raw_sections))
    removed.extend(_diff_raw_sections_removed(old.raw_sections, new.raw_sections))
    modified.extend(_diff_raw_sections_modified(old.raw_sections, new.raw_sections))
    
    return RawDiff(added=added, removed=removed, modified=modified)


def _diff_dict_collection(
    object_type: str,
    old_dict: Dict[Any, Any],
    new_dict: Dict[Any, Any],
    numeric_tol: Dict[str, float],
) -> List[ObjectAdded]:
    """Find objects added in new_dict."""
    added = []
    for key in new_dict:
        if key not in old_dict:
            obj = new_dict[key]
            # Serialize to dict
            if hasattr(obj, '__dict__'):
                data = asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__
            else:
                data = {"value": str(obj)}
            # Convert tuple keys to string for serialization
            key_str = str(key) if isinstance(key, tuple) else key
            added.append(ObjectAdded(object_type=object_type, key=key_str, new_data=data))
    return added


def _diff_dict_collection_removed(
    object_type: str,
    old_dict: Dict[Any, Any],
    new_dict: Dict[Any, Any],
) -> List[ObjectRemoved]:
    """Find objects removed from old_dict."""
    removed = []
    for key in old_dict:
        if key not in new_dict:
            obj = old_dict[key]
            # Serialize to dict
            if hasattr(obj, '__dict__'):
                data = asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__
            else:
                data = {"value": str(obj)}
            # Convert tuple keys to string for serialization
            key_str = str(key) if isinstance(key, tuple) else key
            removed.append(ObjectRemoved(object_type=object_type, key=key_str, old_data=data))
    return removed


def _diff_dict_collection_modified(
    object_type: str,
    old_dict: Dict[Any, Any],
    new_dict: Dict[Any, Any],
    numeric_tol: Dict[str, float],
    include_location: bool = False,
) -> List[ObjectModified]:
    """Find objects modified between old_dict and new_dict."""
    modified = []
    for key in old_dict:
        if key not in new_dict:
            continue
        
        old_obj = old_dict[key]
        new_obj = new_dict[key]
        
        changes = _compare_objects(old_obj, new_obj, numeric_tol)
        
        if changes:
            location = None
            if include_location and hasattr(new_obj, 'location'):
                location = new_obj.location
            elif include_location and hasattr(new_obj, 'story'):
                from .model import LocationInfo
                location = LocationInfo(story=getattr(new_obj, 'story', None))
            
            # Convert tuple keys to string for serialization
            key_str = str(key) if isinstance(key, tuple) else key
            modified.append(ObjectModified(
                object_type=object_type,
                key=key_str,
                changes=changes,
                location=location
            ))
    
    return modified


def _compare_objects(old_obj: Any, new_obj: Any, numeric_tol: Dict[str, float]) -> List[FieldChange]:
    """Compare two objects and return list of field changes."""
    changes = []
    
    # Handle dataclasses
    if hasattr(old_obj, '__dataclass_fields__') and hasattr(new_obj, '__dataclass_fields__'):
        for field_name in old_obj.__dataclass_fields__:
            if field_name in ['raw_fields', 'raw_sections']:  # Skip raw fields
                continue
            
            old_val = getattr(old_obj, field_name, None)
            new_val = getattr(new_obj, field_name, None)
            
            if old_val != new_val:
                # Check if it's a numeric difference within tolerance
                if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                    tol = numeric_tol.get(field_name, numeric_tol.get("coord", 1e-3))
                    if abs(old_val - new_val) <= tol:
                        continue  # Within tolerance, ignore
                
                changes.append(FieldChange(field=field_name, old=old_val, new=new_val))
    
    return changes


def _diff_list_collection(
    object_type: str,
    old_list: List[Any],
    new_list: List[Any],
    numeric_tol: Dict[str, float],
) -> List[ObjectAdded]:
    """Find objects added in new_list (for collections stored as lists like grids)."""
    added = []
    # Create dicts keyed by a unique identifier (name for grids)
    old_dict = {}
    new_dict = {}
    
    for obj in old_list:
        if hasattr(obj, 'name'):
            old_dict[obj.name] = obj
    
    for obj in new_list:
        if hasattr(obj, 'name'):
            new_dict[obj.name] = obj
            if obj.name not in old_dict:
                # Serialize to dict
                if hasattr(obj, '__dict__'):
                    data = asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__
                else:
                    data = {"value": str(obj)}
                added.append(ObjectAdded(object_type=object_type, key=obj.name, new_data=data))
    
    return added


def _diff_list_collection_removed(
    object_type: str,
    old_list: List[Any],
    new_list: List[Any],
) -> List[ObjectRemoved]:
    """Find objects removed from old_list."""
    removed = []
    old_dict = {}
    new_dict = {}
    
    for obj in old_list:
        if hasattr(obj, 'name'):
            old_dict[obj.name] = obj
    
    for obj in new_list:
        if hasattr(obj, 'name'):
            new_dict[obj.name] = obj
    
    for name, obj in old_dict.items():
        if name not in new_dict:
            # Serialize to dict
            if hasattr(obj, '__dict__'):
                data = asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__
            else:
                data = {"value": str(obj)}
            removed.append(ObjectRemoved(object_type=object_type, key=name, old_data=data))
    
    return removed


def _diff_raw_sections(
    old_sections: Dict[str, List[str]],
    new_sections: Dict[str, List[str]],
) -> List[ObjectAdded]:
    """Find raw sections added in new_sections."""
    added = []
    for section_name in new_sections:
        if section_name not in old_sections:
            # New section added
            added.append(ObjectAdded(
                object_type="raw_section",
                key=section_name,
                new_data={"lines": new_sections[section_name], "line_count": len(new_sections[section_name])}
            ))
    return added


def _diff_raw_sections_removed(
    old_sections: Dict[str, List[str]],
    new_sections: Dict[str, List[str]],
) -> List[ObjectRemoved]:
    """Find raw sections removed from old_sections."""
    removed = []
    for section_name in old_sections:
        if section_name not in new_sections:
            # Section removed
            removed.append(ObjectRemoved(
                object_type="raw_section",
                key=section_name,
                old_data={"lines": old_sections[section_name], "line_count": len(old_sections[section_name])}
            ))
    return removed


def _diff_raw_sections_modified(
    old_sections: Dict[str, List[str]],
    new_sections: Dict[str, List[str]],
) -> List[ObjectModified]:
    """Find raw sections modified between old_sections and new_sections."""
    modified = []
    for section_name in old_sections:
        if section_name not in new_sections:
            continue  # Handled by removed
        
        old_lines = set(old_sections[section_name])
        new_lines = set(new_sections[section_name])
        
        if old_lines != new_lines:
            # Section content changed
            added_lines = new_lines - old_lines
            removed_lines = old_lines - new_lines
            
            changes = []
            if added_lines:
                changes.append(FieldChange(
                    field="lines_added",
                    old=None,
                    new=list(added_lines)
                ))
            if removed_lines:
                changes.append(FieldChange(
                    field="lines_removed",
                    old=list(removed_lines),
                    new=None
                ))
            if len(old_sections[section_name]) != len(new_sections[section_name]):
                changes.append(FieldChange(
                    field="line_count",
                    old=len(old_sections[section_name]),
                    new=len(new_sections[section_name])
                ))
            
            if changes:
                modified.append(ObjectModified(
                    object_type="raw_section",
                    key=section_name,
                    changes=changes
                ))
    
    return modified

