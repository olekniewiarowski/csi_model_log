"""
MCP Server for ETABS Model Log
Provides tools for querying model versions and diffs.
"""
import os
import atexit
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, List, Optional, Dict
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .parser import parse_et_file
from .model import EtabsModel
from .location import attach_story_and_grid_tags
from .diffing import diff_models
from .aggregate import aggregate_diff
from .summarize import aggregated_to_json, get_llm_client, summarize_diff_to_markdown

# Create FastMCP server instance
mcp = FastMCP("ETABS Model Log Server")


##########################################################################
# F I L E   W A T C H E R
##########################################################################

class EtabsFileHandler(FileSystemEventHandler):
    """Handler for ETABS file system events."""
    
    def __init__(self, watcher: 'EtabsFileWatcher'):
        self.watcher = watcher
        self._processing = set()  # Track files being processed to avoid duplicates
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            self._handle_file_event(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            self._handle_file_event(event.src_path)
    
    def _handle_file_event(self, file_path: str):
        """Process a file event for .$et or .e2k files."""
        path = Path(file_path)
        
        # Only process .$et and .e2k files
        if path.suffix.lower() not in ['.$et', '.e2k', '.et']:
            return
        
        # Avoid processing the same file multiple times
        if file_path in self._processing:
            return
        
        # Wait a bit for file to be fully written (ETABS may write in chunks)
        time.sleep(0.5)
        
        # Check if file exists and is readable
        if not path.exists() or not path.is_file():
            return
        
        # Add to processing set
        self._processing.add(file_path)
        
        try:
            # Record the file change
            self.watcher.record_file_change(file_path)
        finally:
            # Remove from processing set after a delay
            threading.Timer(2.0, lambda: self._processing.discard(file_path)).start()


class EtabsFileWatcher:
    """Watches a directory for new ETABS model files."""
    
    def __init__(self):
        self.observer: Optional[Observer] = None
        self.watched_path: Optional[Path] = None
        self.file_changes: deque = deque(maxlen=100)  # Store last 100 changes
        self.lock = threading.Lock()
        self.last_file: Optional[str] = None  # Track last file for auto-diffing
    
    def start_watching(self, directory: str, recursive: bool = True) -> Dict[str, Any]:
        """Start watching a directory for .$et and .e2k files."""
        with self.lock:
            if self.observer is not None and self.observer.is_alive():
                return {
                    "status": "already_watching",
                    "current_path": str(self.watched_path),
                    "message": f"Already watching: {self.watched_path}"
                }
            
            watch_path = Path(directory)
            if not watch_path.exists():
                return {
                    "status": "error",
                    "message": f"Directory does not exist: {directory}"
                }
            
            if not watch_path.is_dir():
                return {
                    "status": "error",
                    "message": f"Path is not a directory: {directory}"
                }
            
            self.watched_path = watch_path
            self.observer = Observer()
            handler = EtabsFileHandler(self)
            self.observer.schedule(handler, str(watch_path), recursive=recursive)
            self.observer.start()
            
            return {
                "status": "started",
                "watched_path": str(watch_path),
                "recursive": recursive,
                "message": f"Started watching: {watch_path}"
            }
    
    def stop_watching(self) -> Dict[str, Any]:
        """Stop watching the directory."""
        with self.lock:
            if self.observer is None or not self.observer.is_alive():
                return {
                    "status": "not_watching",
                    "message": "No active watcher"
                }
            
            self.observer.stop()
            self.observer.join(timeout=2.0)
            watched_path = self.watched_path
            self.observer = None
            self.watched_path = None
            
            return {
                "status": "stopped",
                "watched_path": str(watched_path) if watched_path else None,
                "message": f"Stopped watching: {watched_path}" if watched_path else "Stopped watching"
            }
    
    def record_file_change(self, file_path: str):
        """Record a file change event."""
        with self.lock:
            change_info = {
                "file_path": file_path,
                "timestamp": time.time(),
                "file_name": Path(file_path).name,
                "file_size": Path(file_path).stat().st_size if Path(file_path).exists() else 0
            }
            self.file_changes.append(change_info)
            
            # Update last file
            self.last_file = file_path
    
    def get_pending_changes(self, clear: bool = False) -> List[Dict[str, Any]]:
        """Get all pending file changes."""
        with self.lock:
            changes = list(self.file_changes)
            if clear:
                self.file_changes.clear()
            return changes
    
    def clear_changes(self) -> Dict[str, Any]:
        """Clear all tracked file changes."""
        with self.lock:
            count = len(self.file_changes)
            self.file_changes.clear()
            return {
                "status": "cleared",
                "cleared_count": count,
                "message": f"Cleared {count} tracked file changes"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get watcher status."""
        with self.lock:
            is_watching = self.observer is not None and self.observer.is_alive()
            return {
                "is_watching": is_watching,
                "watched_path": str(self.watched_path) if self.watched_path else None,
                "pending_changes": len(self.file_changes),
                "last_file": self.last_file
            }
    
    def get_last_two_files(self) -> Optional[Dict[str, Any]]:
        """Get the last two unique files for diffing."""
        with self.lock:
            # Get all unique files from changes
            seen_files = {}
            for change in reversed(self.file_changes):
                file_path = change["file_path"]
                if file_path not in seen_files:
                    seen_files[file_path] = change
            
            files = list(seen_files.values())
            if len(files) >= 2:
                return {
                    "old_file": files[-2]["file_path"],
                    "new_file": files[-1]["file_path"],
                    "old_timestamp": files[-2]["timestamp"],
                    "new_timestamp": files[-1]["timestamp"]
                }
            elif len(files) == 1:
                return {
                    "new_file": files[0]["file_path"],
                    "new_timestamp": files[0]["timestamp"],
                    "message": "Only one file detected so far"
                }
            return None


# Global watcher instance
_file_watcher = EtabsFileWatcher()


##########################################################################
# T O O L S
##########################################################################

@mcp.tool()
async def list_model_versions(project_root: str) -> List[dict]:
    """
    List all available model versions in a project directory.
    
    Args:
        project_root: Path to the project root directory containing .$et files
        
    Returns:
        List of version dictionaries with id, path, and metadata
    """
    root = Path(project_root)
    if not root.exists():
        return [{"error": f"Project root not found: {project_root}"}]
    
    versions = []
    
    # Look for .$et files in the project root
    et_files = list(root.glob("**/*.$et")) + list(root.glob("**/*.e2k"))
    
    for i, et_file in enumerate(sorted(et_files, key=lambda p: p.stat().st_mtime, reverse=True)):
        stat = et_file.stat()
        versions.append({
            "id": f"v{i+1}",
            "path": str(et_file),
            "name": et_file.name,
            "created_at": stat.st_mtime,
            "size_bytes": stat.st_size
        })
    
    return versions


@mcp.tool()
async def get_model_info(model_path: str) -> dict:
    """
    Parse and return basic information about an ETABS model file.
    
    Args:
        model_path: Path to the .$et or .e2k file
        
    Returns:
        Dictionary with model metadata and section counts
    """
    try:
        model = parse_et_file(model_path)
        
        return {
            "source_file": model.program_info.source_file,
            "program": model.program_info.program,
            "version": model.program_info.version,
            "sections_found": list(model.raw_sections.keys()),
            "section_count": len(model.raw_sections),
            "stories": len(model.stories),
            "joints": len(model.joints),
            "frames": len(model.frames),
            "materials": len(model.materials),
            "frame_sections": len(model.frame_sections),
            "load_combos": len(model.load_combos)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def get_model_sections(model_path: str, section_name: Optional[str] = None) -> dict:
    """
    Get raw section data from a model file.
    
    Args:
        model_path: Path to the .$et or .e2k file
        section_name: Optional section name to filter (e.g., "JOINT COORDINATES")
                     If None, returns all sections
        
    Returns:
        Dictionary with section data
    """
    try:
        model = parse_et_file(model_path)
        
        if section_name:
            if section_name in model.raw_sections:
                return {
                    "section": section_name,
                    "line_count": len(model.raw_sections[section_name]),
                    "lines": model.raw_sections[section_name][:100]  # First 100 lines
                }
            else:
                return {"error": f"Section '{section_name}' not found"}
        else:
            # Return summary of all sections
            return {
                "sections": {
                    name: {
                        "line_count": len(lines),
                        "sample_lines": lines[:5]  # First 5 lines as sample
                    }
                    for name, lines in model.raw_sections.items()
                }
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def compare_models(old_model_path: str, new_model_path: str) -> dict:
    """
    Compare two model files and return a basic diff summary.
    
    Args:
        old_model_path: Path to the older .$et or .e2k file
        new_model_path: Path to the newer .$et or .e2k file
        
    Returns:
        Dictionary with comparison results
    """
    try:
        old_model = parse_et_file(old_model_path)
        new_model = parse_et_file(new_model_path)
        
        # Basic comparison of sections
        old_sections = set(old_model.raw_sections.keys())
        new_sections = set(new_model.raw_sections.keys())
        
        added_sections = new_sections - old_sections
        removed_sections = old_sections - new_sections
        common_sections = old_sections & new_sections
        
        # Compare line counts for common sections
        section_changes = {}
        for section in common_sections:
            old_count = len(old_model.raw_sections[section])
            new_count = len(new_model.raw_sections[section])
            if old_count != new_count:
                section_changes[section] = {
                    "old_line_count": old_count,
                    "new_line_count": new_count,
                    "delta": new_count - old_count
                }
        
        return {
            "old_model": old_model_path,
            "new_model": new_model_path,
            "added_sections": list(added_sections),
            "removed_sections": list(removed_sections),
            "section_changes": section_changes,
            "summary": f"Found {len(added_sections)} added, {len(removed_sections)} removed sections, "
                      f"{len(section_changes)} sections with line count changes"
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def get_diff_summary(old_model_path: str, new_model_path: str) -> dict:
    """
    Get a semantic diff summary between two model files, ready for LLM consumption.
    
    This tool:
    1. Parses both models
    2. Tags locations (story/grid)
    3. Computes semantic diff
    4. Aggregates changes into meaningful clusters
    5. Returns compact JSON payload ready for LLM
    
    Args:
        old_model_path: Path to the older .$et or .e2k file
        new_model_path: Path to the newer .$et or .e2k file
        
    Returns:
        Dictionary with aggregated diff data ready for LLM summarization
    """
    try:
        # Parse models
        old_model = parse_et_file(old_model_path)
        new_model = parse_et_file(new_model_path)
        
        # Tag locations
        attach_story_and_grid_tags(old_model)
        attach_story_and_grid_tags(new_model)
        
        # Compute diff
        raw_diff = diff_models(old_model, new_model)
        
        # Aggregate changes
        aggregated = aggregate_diff(raw_diff, old_model, new_model)
        
        # Convert to JSON payload
        payload = aggregated_to_json(aggregated)
        
        # Add metadata
        payload["metadata"] = {
            "old_model": old_model_path,
            "new_model": new_model_path,
            "total_changes": {
                "added": len(raw_diff.added),
                "removed": len(raw_diff.removed),
                "modified": len(raw_diff.modified)
            },
            "aggregated_summary": {
                "section_swaps": len(aggregated.section_swaps),
                "load_combo_changes": len(aggregated.load_combo_changes),
                "material_changes": len(aggregated.material_changes),
                "geometry_changes": len(aggregated.geometry_changes),
                "other_changes": len(aggregated.other_changes)
            }
        }
        
        return payload
    except Exception as e:
        return {"error": str(e), "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None}


@mcp.tool()
async def watch_directory(directory: str, recursive: bool = True) -> dict:
    """
    Start watching a directory for new ETABS model files (.$et, .e2k).
    
    When ETABS saves a model, a new file will be detected and recorded.
    Use get_pending_changes() to retrieve detected files.
    
    Args:
        directory: Path to the directory to watch
        recursive: Whether to watch subdirectories (default: True)
        
    Returns:
        Dictionary with watcher status
    """
    return _file_watcher.start_watching(directory, recursive=recursive)


@mcp.tool()
async def stop_watching() -> dict:
    """
    Stop watching the directory.
    
    Returns:
        Dictionary with stop status
    """
    return _file_watcher.stop_watching()


@mcp.tool()
async def get_watcher_status() -> dict:
    """
    Get the current status of the file watcher.
    
    Returns:
        Dictionary with watcher status including:
        - is_watching: Whether watcher is active
        - watched_path: Currently watched directory
        - pending_changes: Number of detected file changes
        - last_file: Path to the most recently detected file
    """
    return _file_watcher.get_status()


@mcp.tool()
async def get_pending_changes(clear: bool = False) -> dict:
    """
    Get all pending file changes detected by the watcher.
    
    Args:
        clear: Whether to clear the pending changes after retrieving (default: False)
        
    Returns:
        Dictionary with list of detected file changes, each containing:
        - file_path: Full path to the file
        - file_name: Just the filename
        - timestamp: When the file was detected
        - file_size: Size of the file in bytes
    """
    changes = _file_watcher.get_pending_changes(clear=clear)
    return {
        "count": len(changes),
        "changes": changes
    }


@mcp.tool()
async def clear_tracked_changes() -> dict:
    """
    Clear all tracked file changes from the watcher.
    
    This resets the change history without retrieving it first.
    Useful when you want to start fresh or clear old changes.
    
    Returns:
        Dictionary with status and count of cleared changes
    """
    return _file_watcher.clear_changes()


@mcp.tool()
async def get_latest_file_pair() -> dict:
    """
    Get the last two unique files detected for diffing.
    
    This is useful when you want to automatically compare the most recent
    two model versions that were saved.
    
    Returns:
        Dictionary with old_file and new_file paths, or None if less than 2 files detected
    """
    result = _file_watcher.get_last_two_files()
    if result is None:
        return {
            "status": "insufficient_files",
            "message": "Need at least 2 files to create a diff"
        }
    return result


@mcp.tool()
async def auto_diff_latest(
    style: str = "short",
    use_llm: bool = True,
    model: str = "gpt-4o-mini"
) -> dict:
    """
    Automatically diff the two most recent files detected by the watcher.
    
    This tool combines get_latest_file_pair() and get_diff_summary_markdown()
    to automatically generate a diff when new files are detected.
    
    Args:
        style: Summary style - "short" or "detailed" (default: "short")
        use_llm: Whether to use OpenAI LLM (default: True)
        model: OpenAI model to use (default: "gpt-4o-mini")
        
    Returns:
        Dictionary with markdown summary and metadata, or error if insufficient files
    """
    file_pair = _file_watcher.get_last_two_files()
    
    if file_pair is None or "old_file" not in file_pair:
        return {
            "error": "Insufficient files detected",
            "message": "Need at least 2 files to create a diff. Use get_pending_changes() to see detected files.",
            "file_pair": file_pair
        }
    
    # Use the existing get_diff_summary_markdown logic
    try:
        old_model = parse_et_file(file_pair["old_file"])
        new_model = parse_et_file(file_pair["new_file"])
        
        attach_story_and_grid_tags(old_model)
        attach_story_and_grid_tags(new_model)
        
        raw_diff = diff_models(old_model, new_model)
        aggregated = aggregate_diff(raw_diff, old_model, new_model)
        
        llm = get_llm_client(use_openai=use_llm, model=model)
        
        old_label = Path(file_pair["old_file"]).stem
        new_label = Path(file_pair["new_file"]).stem
        
        summary = summarize_diff_to_markdown(
            llm=llm,
            old_label=old_label,
            new_label=new_label,
            aggregated=aggregated,
            style=style
        )
        
        return {
            "summary": summary,
            "metadata": {
                "old_model": file_pair["old_file"],
                "new_model": file_pair["new_file"],
                "old_label": old_label,
                "new_label": new_label,
                "style": style,
                "llm_used": "openai" if use_llm and hasattr(llm, 'model') else "dummy",
                "total_changes": {
                    "added": len(raw_diff.added),
                    "removed": len(raw_diff.removed),
                    "modified": len(raw_diff.modified)
                },
                "aggregated_summary": {
                    "section_swaps": len(aggregated.section_swaps),
                    "load_combo_changes": len(aggregated.load_combo_changes),
                    "material_changes": len(aggregated.material_changes),
                    "geometry_changes": len(aggregated.geometry_changes),
                    "other_changes": len(aggregated.other_changes)
                }
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None,
            "file_pair": file_pair
        }


@mcp.tool()
async def get_diff_summary_markdown(
    old_model_path: str,
    new_model_path: str,
    style: str = "short",
    use_llm: bool = True,
    model: str = "gpt-4o-mini"
) -> dict:
    """
    Get a human-readable markdown summary of changes between two model files.
    
    This tool:
    1. Parses both models
    2. Tags locations (story/grid)
    3. Computes semantic diff
    4. Aggregates changes
    5. Generates a markdown summary using LLM (or dummy client if LLM unavailable)
    
    Args:
        old_model_path: Path to the older .$et or .e2k file
        new_model_path: Path to the newer .$et or .e2k file
        style: Summary style - "short" or "detailed" (default: "short")
        use_llm: Whether to use OpenAI LLM (default: True). Falls back to dummy if API key not available.
        model: OpenAI model to use (default: "gpt-4o-mini")
        
    Returns:
        Dictionary with markdown summary and metadata
    """
    try:
        # Parse models
        old_model = parse_et_file(old_model_path)
        new_model = parse_et_file(new_model_path)
        
        # Tag locations
        attach_story_and_grid_tags(old_model)
        attach_story_and_grid_tags(new_model)
        
        # Compute diff
        raw_diff = diff_models(old_model, new_model)
        
        # Aggregate changes
        aggregated = aggregate_diff(raw_diff, old_model, new_model)
        
        # Get LLM client
        llm = get_llm_client(use_openai=use_llm, model=model)
        
        # Generate labels from file paths
        old_label = Path(old_model_path).stem
        new_label = Path(new_model_path).stem
        
        # Generate markdown summary
        summary = summarize_diff_to_markdown(
            llm=llm,
            old_label=old_label,
            new_label=new_label,
            aggregated=aggregated,
            style=style
        )
        
        return {
            "summary": summary,
            "metadata": {
                "old_model": old_model_path,
                "new_model": new_model_path,
                "old_label": old_label,
                "new_label": new_label,
                "style": style,
                "llm_used": "openai" if use_llm and hasattr(llm, 'model') else "dummy",
                "total_changes": {
                    "added": len(raw_diff.added),
                    "removed": len(raw_diff.removed),
                    "modified": len(raw_diff.modified)
                },
                "aggregated_summary": {
                    "section_swaps": len(aggregated.section_swaps),
                    "load_combo_changes": len(aggregated.load_combo_changes),
                    "material_changes": len(aggregated.material_changes),
                    "geometry_changes": len(aggregated.geometry_changes),
                    "other_changes": len(aggregated.other_changes)
                }
            }
        }
    except Exception as e:
        return {"error": str(e), "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None}


##########################################################################
# R E S O U R C E S
##########################################################################

@mcp.resource("etabs://reference/sections")
def etabs_section_reference():
    """Reference guide for ETABS .$et file sections"""
    return {
        "common_sections": [
            "PROGRAM CONTROL",
            "STORY DATA",
            "GRID LINES",
            "JOINT COORDINATES",
            "FRAME OBJECTS",
            "MATERIAL PROPERTIES",
            "FRAME SECTIONS",
            "LOAD PATTERNS",
            "LOAD CASES",
            "LOAD COMBINATIONS"
        ],
        "description": "ETABS model files are organized into sections starting with $",
        "format": "Each section begins with '$ SECTION_NAME' followed by data lines"
    }


##########################################################################
# R U N N I N G   T H E   S E R V E R
##########################################################################

# Register cleanup function to stop watcher on exit
def _cleanup_watcher():
    """Stop the file watcher on server shutdown."""
    _file_watcher.stop_watching()

atexit.register(_cleanup_watcher)


if __name__ == "__main__":
    # Run the MCP server with HTTP transport (Streamable HTTP)
    mcp.run(
        transport="http",  # HTTP or STDIO
        host="0.0.0.0",     # Bind to all interfaces
        port=8000,         # HTTP port
        log_level="INFO"   # Set logging level
    )

