"""
Location tagging: attach story and grid information to joints and frames.
"""
from typing import Optional
from .model import EtabsModel, Joint, FrameObject, LocationInfo


def attach_story_and_grid_tags(model: EtabsModel, *, coord_tol: float = 1e-3) -> None:
    """
    Mutates the model in-place:
    - For each Joint, infers story, grid_x, grid_y from story elevations & grid lines.
    - For each FrameObject, infers object_type (column/beam/brace) & LocationInfo.

    This should be called after parse_et_file() and before diffing.
    """
    # Tag joints with story and grid
    for joint in model.joints.values():
        _tag_joint_location(joint, model, coord_tol)
    
    # Tag frames with location and object type
    for frame in model.frames.values():
        _tag_frame_location(frame, model, coord_tol)
        classify_frame_object(frame, model)


def _tag_joint_location(joint: Joint, model: EtabsModel, coord_tol: float) -> None:
    """Tag a joint with story and grid information."""
    # Find story by elevation
    joint.story = _find_story_by_elevation(joint.z, model, coord_tol)
    
    # Find grid lines
    joint.grid_x = _find_grid_line(joint.x, model, direction="X", coord_tol=coord_tol)
    joint.grid_y = _find_grid_line(joint.y, model, direction="Y", coord_tol=coord_tol)


def _find_story_by_elevation(z: float, model: EtabsModel, tol: float) -> Optional[str]:
    """Find the story that contains this elevation."""
    best_match = None
    min_diff = float('inf')
    
    for story_name, story in model.stories.items():
        # Check if z is within story height (approximate)
        # For now, match to nearest story elevation
        diff = abs(z - story.elevation)
        if diff < min_diff:
            min_diff = diff
            best_match = story_name
    
    # Only return if within tolerance
    if best_match and min_diff <= tol * 100:  # More lenient for story matching
        return best_match
    
    return best_match


def _find_grid_line(coord: float, model: EtabsModel, direction: str, coord_tol: float) -> Optional[str]:
    """Find the nearest grid line in the given direction."""
    best_match = None
    min_diff = float('inf')
    
    for grid in model.grids:
        if grid.direction == direction:
            diff = abs(coord - grid.coord)
            if diff < min_diff:
                min_diff = diff
                best_match = grid.name
    
    # Only return if within tolerance
    if best_match and min_diff <= coord_tol:
        return best_match
    
    return None


def _tag_frame_location(frame: FrameObject, model: EtabsModel, coord_tol: float) -> None:
    """Tag a frame with location information."""
    joint_i = model.joints.get(frame.joint_i)
    joint_j = model.joints.get(frame.joint_j)
    
    if not joint_i or not joint_j:
        return
    
    # Determine primary story (use the lower story, or both if different)
    story_i = joint_i.story
    story_j = joint_j.story
    
    if story_i and story_j:
        if story_i == story_j:
            frame.story = story_i
            frame.location.story = story_i
        else:
            # Frame spans multiple stories - use the lower one
            elev_i = model.stories.get(story_i, None)
            elev_j = model.stories.get(story_j, None)
            if elev_i and elev_j:
                frame.story = story_i if elev_i.elevation <= elev_j.elevation else story_j
                frame.location.story = frame.story
    
    # Determine grid location
    # For columns: use the grid intersection
    # For beams: use the story and grid lines
    grid_x_i = joint_i.grid_x
    grid_x_j = joint_j.grid_x
    grid_y_i = joint_i.grid_y
    grid_y_j = joint_j.grid_y
    
    # If both joints share the same grid, use it
    if grid_x_i and grid_x_i == grid_x_j:
        frame.location.grid_x = grid_x_i
    
    if grid_y_i and grid_y_i == grid_y_j:
        frame.location.grid_y = grid_y_i
    
    # If grids differ, store span
    if grid_x_i and grid_x_j and grid_x_i != grid_x_j:
        frame.location.grid_x_span = (grid_x_i, grid_x_j)
    
    if grid_y_i and grid_y_j and grid_y_i != grid_y_j:
        frame.location.grid_y_span = (grid_y_i, grid_y_j)


def classify_frame_object(frame: FrameObject, model: EtabsModel) -> None:
    """
    Update frame.object_type based on orientation and section name.
    
    Heuristics:
    - Column: primarily vertical (large Z change, small X/Y change)
    - Beam: primarily horizontal (small Z change, large X or Y change)
    - Brace: diagonal (significant changes in all directions)
    """
    joint_i = model.joints.get(frame.joint_i)
    joint_j = model.joints.get(frame.joint_j)
    
    if not joint_i or not joint_j:
        frame.object_type = "frame"
        return
    
    # Calculate deltas
    dx = abs(joint_j.x - joint_i.x)
    dy = abs(joint_j.y - joint_i.y)
    dz = abs(joint_j.z - joint_i.z)
    
    # Total length
    length = (dx**2 + dy**2 + dz**2)**0.5
    
    if length < 1e-6:
        frame.object_type = "frame"
        return
    
    # Normalize deltas
    dx_norm = dx / length
    dy_norm = dy / length
    dz_norm = dz / length
    
    # Classify based on orientation
    # Column: primarily vertical (dz_norm > 0.7)
    if dz_norm > 0.7:
        frame.object_type = "column"
    # Beam: primarily horizontal (dz_norm < 0.3 and (dx_norm > 0.7 or dy_norm > 0.7))
    elif dz_norm < 0.3 and (dx_norm > 0.7 or dy_norm > 0.7):
        frame.object_type = "beam"
    # Brace: diagonal (everything else)
    else:
        frame.object_type = "brace"
    
    # Override based on section name if it contains keywords
    section = model.frame_sections.get(frame.section)
    if section:
        section_name_upper = section.name.upper()
        if "COLUMN" in section_name_upper or "COL" in section_name_upper:
            frame.object_type = "column"
        elif "BEAM" in section_name_upper or "BM" in section_name_upper:
            frame.object_type = "beam"
        elif "BRACE" in section_name_upper:
            frame.object_type = "brace"

