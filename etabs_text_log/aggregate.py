"""
Aggregation layer: convert raw diffs into designer-friendly change clusters.
"""
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Dict, Any
from .model import LocationInfo
from .diffing import RawDiff, ObjectModified, ObjectAdded, ObjectRemoved, FieldChange
from .model import EtabsModel


@dataclass
class SectionSwapCluster:
    """
    Aggregated change: group of frames where the section changed from A → B
    under some common location / object-type pattern.
    """
    object_type: Literal["column", "beam", "brace", "frame"]
    story: Optional[str]                     # e.g. "L14" or None
    old_section: str
    new_section: str
    count: int
    example_objects: List[str] = field(default_factory=list)
    grid_region: Optional[Dict[str, Any]] = None   # e.g. {"grid_x": ["A","D"], "grid_y": ["1","4"]}


@dataclass
class LoadComboChange:
    """
    Changes to a load combination definition.
    """
    name: str
    change_type: Literal["added", "removed", "modified"]
    old_terms: Optional[List[Dict[str, Any]]] = None
    new_terms: Optional[List[Dict[str, Any]]] = None
    # For "modified", maybe a list of term-level diffs:
    term_changes: Optional[List[Dict[str, Any]]] = None


@dataclass
class MaterialPropertyChange:
    material: str
    changed_fields: Dict[str, FieldChange]


@dataclass
class AggregatedDiff:
    """
    High-level, user-facing changes grouped by category.
    """
    section_swaps: List[SectionSwapCluster] = field(default_factory=list)
    load_combo_changes: List[LoadComboChange] = field(default_factory=list)
    material_changes: List[MaterialPropertyChange] = field(default_factory=list)
    geometry_changes: List[Dict[str, Any]] = field(default_factory=list)
    # catch-all for other categories:
    other_changes: List[Dict[str, Any]] = field(default_factory=list)


def aggregate_diff(
    raw_diff: RawDiff,
    old: EtabsModel,
    new: EtabsModel,
) -> AggregatedDiff:
    """
    Convert low-level RawDiff into AggregatedDiff:
    - group frame section changes into SectionSwapClusters
    - map object locations to stories/grids
    - treat added/removed load combos as LoadComboChange objects
    - identify significant material property changes
    """
    aggregated = AggregatedDiff()
    
    # Aggregate frame section swaps
    aggregated.section_swaps = _aggregate_section_swaps(raw_diff, old, new)
    
    # Aggregate load combo changes
    aggregated.load_combo_changes = _aggregate_load_combo_changes(raw_diff, old, new)
    
    # Aggregate material changes
    aggregated.material_changes = _aggregate_material_changes(raw_diff)
    
    # Aggregate geometry changes (added/removed frames, joints, stories)
    aggregated.geometry_changes = _aggregate_geometry_changes(raw_diff)
    
    # Other changes
    aggregated.other_changes = _aggregate_other_changes(raw_diff)
    
    return aggregated


def _aggregate_section_swaps(
    raw_diff: RawDiff,
    old: EtabsModel,
    new: EtabsModel,
) -> List[SectionSwapCluster]:
    """Group frame section changes into clusters from both frame objects and frame assignments."""
    clusters: Dict[str, SectionSwapCluster] = {}
    
    # Look for frame assignment modifications where section changed (from LINE ASSIGNS)
    for mod in raw_diff.modified:
        if mod.object_type == "frame_assignment":
            # Find section change
            section_change = None
            for change in mod.changes:
                if change.field == "section":
                    section_change = change
                    break
            
            if not section_change:
                continue
            
            old_section = section_change.old
            new_section = section_change.new
            
            # Parse key: it's a string representation of (frame_name, story) tuple
            # Format: "('FrameName', 'Story')" or already a tuple
            import ast
            try:
                if isinstance(mod.key, tuple):
                    key_tuple = mod.key
                elif isinstance(mod.key, str) and mod.key.startswith('('):
                    key_tuple = ast.literal_eval(mod.key)
                else:
                    continue
                
                if isinstance(key_tuple, tuple) and len(key_tuple) == 2:
                    frame_name, story = key_tuple
                else:
                    continue
            except (ValueError, SyntaxError):
                continue
            
            # Get frame to determine object type and location
            frame = new.frames.get(frame_name)
            if not frame:
                continue
            
            object_type = frame.object_type or "frame"
            
            # Use story from assignment, but also check frame location for grid info
            story = story or frame.story or (frame.location.story if frame.location else None)
            
            # Create cluster key
            cluster_key = f"{object_type}:{story}:{old_section}:{new_section}"
            
            if cluster_key not in clusters:
                clusters[cluster_key] = SectionSwapCluster(
                    object_type=object_type,
                    story=story,
                    old_section=old_section,
                    new_section=new_section,
                    count=0,
                    example_objects=[],
                    grid_region=None
                )
            
            cluster = clusters[cluster_key]
            cluster.count += 1
            
            # Add example object (limit to 5)
            if len(cluster.example_objects) < 5:
                cluster.example_objects.append(frame_name)
            
            # Update grid region
            if frame.location:
                if frame.location.grid_x and frame.location.grid_y:
                    if cluster.grid_region is None:
                        cluster.grid_region = {"grid_x": set(), "grid_y": set()}
                    cluster.grid_region["grid_x"].add(frame.location.grid_x)
                    cluster.grid_region["grid_y"].add(frame.location.grid_y)
        
        elif mod.object_type == "frame":
            # Also check frame objects directly (for backwards compatibility)
            # Find section change
            section_change = None
            for change in mod.changes:
                if change.field == "section":
                    section_change = change
                    break
            
            if not section_change:
                continue
            
            old_section = section_change.old
            new_section = section_change.new
            
            # Get frame to determine object type and location
            frame = new.frames.get(mod.key)
            if not frame:
                continue
            
            object_type = frame.object_type or "frame"
            story = frame.story or (frame.location.story if frame.location else None)
            
            # Create cluster key
            cluster_key = f"{object_type}:{story}:{old_section}:{new_section}"
            
            if cluster_key not in clusters:
                clusters[cluster_key] = SectionSwapCluster(
                    object_type=object_type,
                    story=story,
                    old_section=old_section,
                    new_section=new_section,
                    count=0,
                    example_objects=[],
                    grid_region=None
                )
            
            cluster = clusters[cluster_key]
            cluster.count += 1
            
            # Add example object (limit to 5)
            if len(cluster.example_objects) < 5:
                cluster.example_objects.append(mod.key)
            
            # Update grid region
            if frame.location:
                if frame.location.grid_x and frame.location.grid_y:
                    if cluster.grid_region is None:
                        cluster.grid_region = {"grid_x": set(), "grid_y": set()}
                    cluster.grid_region["grid_x"].add(frame.location.grid_x)
                    cluster.grid_region["grid_y"].add(frame.location.grid_y)
    
    # Convert sets to lists for JSON serialization
    for cluster in clusters.values():
        if cluster.grid_region:
            cluster.grid_region = {
                "grid_x": sorted(list(cluster.grid_region.get("grid_x", []))),
                "grid_y": sorted(list(cluster.grid_region.get("grid_y", [])))
            }
    
    return list(clusters.values())


def _aggregate_load_combo_changes(
    raw_diff: RawDiff,
    old: EtabsModel,
    new: EtabsModel,
) -> List[LoadComboChange]:
    """Aggregate load combination changes."""
    changes = []
    
    # Added combos
    for added in raw_diff.added:
        if added.object_type == "load_combo":
            combo = new.load_combos.get(added.key)
            if combo:
                terms = [{"name": t.name, "factor": t.factor} for t in combo.terms]
                changes.append(LoadComboChange(
                    name=added.key,
                    change_type="added",
                    new_terms=terms
                ))
    
    # Removed combos
    for removed in raw_diff.removed:
        if removed.object_type == "load_combo":
            combo = old.load_combos.get(removed.key)
            if combo:
                terms = [{"name": t.name, "factor": t.factor} for t in combo.terms]
                changes.append(LoadComboChange(
                    name=removed.key,
                    change_type="removed",
                    old_terms=terms
                ))
    
    # Modified combos
    for mod in raw_diff.modified:
        if mod.object_type == "load_combo":
            old_combo = old.load_combos.get(mod.key)
            new_combo = new.load_combos.get(mod.key)
            
            if old_combo and new_combo:
                old_terms = [{"name": t.name, "factor": t.factor} for t in old_combo.terms]
                new_terms = [{"name": t.name, "factor": t.factor} for t in new_combo.terms]
                
                changes.append(LoadComboChange(
                    name=mod.key,
                    change_type="modified",
                    old_terms=old_terms,
                    new_terms=new_terms
                ))
    
    return changes


def _aggregate_material_changes(raw_diff: RawDiff) -> List[MaterialPropertyChange]:
    """Aggregate material property changes."""
    changes = []
    
    for mod in raw_diff.modified:
        if mod.object_type == "material":
            changed_fields = {change.field: change for change in mod.changes}
            if changed_fields:
                changes.append(MaterialPropertyChange(
                    material=mod.key,
                    changed_fields=changed_fields
                ))
    
    return changes


def _aggregate_geometry_changes(raw_diff: RawDiff) -> List[Dict[str, Any]]:
    """Aggregate geometry changes (added/removed objects)."""
    changes = []
    
    # Count added/removed by type
    counts = {}
    for added in raw_diff.added:
        obj_type = added.object_type
        counts[obj_type] = counts.get(obj_type, {"added": 0, "removed": 0})
        counts[obj_type]["added"] += 1
    
    for removed in raw_diff.removed:
        obj_type = removed.object_type
        counts[obj_type] = counts.get(obj_type, {"added": 0, "removed": 0})
        counts[obj_type]["removed"] += 1
    
    # Create summary entries
    for obj_type, counts_dict in counts.items():
        if counts_dict["added"] > 0 or counts_dict["removed"] > 0:
            changes.append({
                "object_type": obj_type,
                "added": counts_dict["added"],
                "removed": counts_dict["removed"]
            })
    
    return changes


def _aggregate_other_changes(raw_diff: RawDiff) -> List[Dict[str, Any]]:
    """Aggregate other types of changes."""
    changes = []
    
    # Frame section changes (not swaps, but property changes)
    for mod in raw_diff.modified:
        if mod.object_type == "frame_section":
            # Check if it's not just a section swap (those are handled separately)
            non_section_changes = [c for c in mod.changes if c.field != "section"]
            if non_section_changes:
                changes.append({
                    "type": "frame_section_property_change",
                    "section": mod.key,
                    "fields_changed": [c.field for c in non_section_changes]
                })
    
    # Load pattern/case changes
    for mod in raw_diff.modified:
        if mod.object_type in ["load_pattern", "load_case"]:
            changes.append({
                "type": f"{mod.object_type}_change",
                "name": mod.key,
                "fields_changed": [c.field for c in mod.changes]
            })
    
    # Raw section changes (unparsed sections like AREA ASSIGNS, LINE ASSIGNS)
    # These are important for detecting section property changes
    for mod in raw_diff.modified:
        if mod.object_type == "raw_section":
            # Check if this is a section-related section
            section_name_upper = mod.key.upper()
            if "AREA ASSIGN" in section_name_upper or "LINE ASSIGN" in section_name_upper:
                # Count lines added/removed
                lines_added = 0
                lines_removed = 0
                for change in mod.changes:
                    if change.field == "lines_added" and change.new:
                        lines_added = len(change.new)
                    elif change.field == "lines_removed" and change.old:
                        lines_removed = len(change.old)
                
                changes.append({
                    "type": "section_assignment_change",
                    "section_name": mod.key,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "net_change": lines_added - lines_removed
                })
            else:
                # Other raw section changes
                changes.append({
                    "type": "raw_section_change",
                    "section_name": mod.key,
                    "fields_changed": [c.field for c in mod.changes]
                })
    
    # Raw sections added/removed
    for added in raw_diff.added:
        if added.object_type == "raw_section":
            section_name_upper = added.key.upper()
            if "AREA ASSIGN" in section_name_upper or "LINE ASSIGN" in section_name_upper:
                changes.append({
                    "type": "section_assignment_added",
                    "section_name": added.key,
                    "line_count": added.new_data.get("line_count", 0)
                })
    
    for removed in raw_diff.removed:
        if removed.object_type == "raw_section":
            section_name_upper = removed.key.upper()
            if "AREA ASSIGN" in section_name_upper or "LINE ASSIGN" in section_name_upper:
                changes.append({
                    "type": "section_assignment_removed",
                    "section_name": removed.key,
                    "line_count": removed.old_data.get("line_count", 0)
                })
    
    return changes

