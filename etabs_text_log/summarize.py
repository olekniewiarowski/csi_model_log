"""
Summarization & LLM interface: format aggregated diffs for LLM consumption.
"""
import os
import textwrap
from dataclasses import asdict
from typing import Protocol, Literal, Dict, Any, Optional
from dotenv import load_dotenv
from .aggregate import AggregatedDiff

# Load environment variables from .env file
load_dotenv()


class LLMClient(Protocol):
    """
    Abstract protocol so we can swap OpenAI / local models.
    """
    def summarize(self, prompt: str | Dict[str, str]) -> str:
        ...


def build_summary_prompt(
    old_label: str,
    new_label: str,
    aggregated: AggregatedDiff,
    *,
    style: Literal["short", "detailed"] = "short",
    project_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Build the system + user messages for the LLM call.
    
    Returns a dict with "system" and "user" keys for proper message formatting.
    """
    project_part = f" for project: {project_name}" if project_name else ""
    
    system_message = (
        "You are an expert structural engineering assistant specializing in ETABS model analysis. "
        "You compare two ETABS model versions and produce a precise, concise change log using "
        "structural engineering terminology. "
        "CRITICAL: You MUST only describe differences that are actually present in the provided change data. "
        "ALWAYS use location information (story names like 'L2', 'L3' and grid locations like 'A-1', 'B-2') "
        "when available in the change data. Use phrases like 'columns on Story L2' or 'beam at grid A-1' "
        "instead of generic descriptions."
    )
    
    # Convert aggregated diff to formatted text
    summary_data = _aggregated_to_dict(aggregated)
    change_data = _format_aggregated_for_llm(summary_data)
    
    # Count changes for machine summary
    counts = _count_changes(aggregated)
    
    user_message = textwrap.dedent(
        f"""
        We have two versions of the same ETABS model{project_part}.
        
        OLD VERSION: {old_label}
        NEW VERSION: {new_label}
        
        DETECTED CHANGES:
        -----------------
        {change_data if change_data.strip() else "[No changes detected between these versions.]"}
        
        Your tasks:
        
        1. Identify additions, deletions, and modifications from the change data above.
           Focus on structural modeling changes such as:
             - Materials (property changes, additions, removals)
             - Frame/shell section properties and section swaps
             - Section assignments (area assigns, line assigns)
             - Load patterns and load cases
             - Load combinations
             - Geometry changes (added/removed elements)
             - Any other clearly represented ETABS definitions.
        
        2. Produce a human-readable summary in MARKDOWN with this structure:
        
           ## Key Changes (high-level)
           - Short bullet list summarizing the main types of changes.
        
           ## Materials
           - Bullet points for added/removed/modified materials (if any).
             Include specific property changes (e.g., "Fy changed from 50 ksi to 55 ksi").
        
           ## Sections
           - Bullet points for section swaps. ALWAYS include location information when available.
           - Format examples:
             * "26 columns on Story L3: W14X90 → W14X99"
             * "Column at grid A-1 on Story L2: ConcCol → SteelCol"
             * "5 beams on Story L2 (Grids A-D): ConcBm → ConcBm2"
           - When grid information is available, use it (e.g., "at grid A-1", "at grids A-D / 1-4").
           - When story information is available, use it (e.g., "on Story L2", "on Stories L2-L3").
           - For large groups, summarize by count rather than listing every item.
        
           ## Section Assignments
           - Changes to area assignments, line assignments, or other property assignments.
        
           ## Loads and Load Combinations
           - Bullet points for changes to load patterns, load cases, and load combos.
           - Show old vs new for modified combinations.
        
           ## Geometry Changes
           - Added/removed structural elements (frames, joints, areas, etc.).
        
           ## Other Notable Changes
           - Anything else that is structurally relevant.
        
        3. At the end, add a small machine-readable JSON block under a heading
           '## Machine Summary' in the following format:
        
           ```json
           {{
             "materials_added": {counts['materials_added']},
             "materials_modified": {counts['materials_modified']},
             "materials_removed": {counts['materials_removed']},
             "sections_added": {counts['sections_added']},
             "sections_modified": {counts['sections_modified']},
             "sections_removed": {counts['sections_removed']},
             "section_swaps": {counts['section_swaps']},
             "loads_added": {counts['loads_added']},
             "loads_modified": {counts['loads_modified']},
             "loads_removed": {counts['loads_removed']},
             "geometry_added": {counts['geometry_added']},
             "geometry_removed": {counts['geometry_removed']}
           }}
           ```
        
        Rules:
        - Do NOT invent any changes that you cannot directly infer from the change data.
        - If something is unclear, omit it instead of guessing.
        - Be concise but clear. The primary audience is a structural engineer.
        - Use structural engineering terminology (columns, beams, braces, load combinations, etc.).
        - LOCATION INFORMATION IS CRITICAL: Always use story and grid information when provided:
          * "columns on Story L2" (when story is known)
          * "column at grid A-1" (when grid is known)
          * "columns on Story L2 at grids A-D / 1-4" (when both are known)
          * Prefer specific locations over generic descriptions like "some columns" or "various frames"
        - For large groups of changes, summarize by count rather than listing every item.
        - When grid_region information is provided, format it as "Grids X-Y" or "at grids A-D / 1-4".
        """
    ).strip()
    
    return {
        "system": system_message,
        "user": user_message,
    }


def _aggregated_to_dict(aggregated: AggregatedDiff) -> Dict[str, Any]:
    """Convert AggregatedDiff to a JSON-serializable dict."""
    return {
        "section_swaps": [
            {
                "object_type": swap.object_type,
                "story": swap.story,
                "old_section": swap.old_section,
                "new_section": swap.new_section,
                "count": swap.count,
                "example_objects": swap.example_objects[:3],  # Limit examples
                "grid_region": swap.grid_region
            }
            for swap in aggregated.section_swaps
        ],
        "load_combo_changes": [
            {
                "name": combo.name,
                "change_type": combo.change_type,
                "old_terms": combo.old_terms,
                "new_terms": combo.new_terms
            }
            for combo in aggregated.load_combo_changes
        ],
        "material_changes": [
            {
                "material": mat.material,
                "changed_fields": {
                    field: {"old": change.old, "new": change.new}
                    for field, change in mat.changed_fields.items()
                }
            }
            for mat in aggregated.material_changes
        ],
        "geometry_changes": aggregated.geometry_changes,
        "other_changes": aggregated.other_changes
    }


def _format_aggregated_for_llm(data: Dict[str, Any]) -> str:
    """Format aggregated data into a readable string for LLM."""
    lines = []
    
    # Section swaps
    if data["section_swaps"]:
        lines.append("=== SECTION SWAPS ===")
        for swap in data["section_swaps"]:
            # Build location description with story and grid info
            location_parts = []
            if swap.get("story"):
                location_parts.append(f"Story {swap['story']}")
            
            grid_desc = None
            if swap.get("grid_region"):
                grid_x = swap["grid_region"].get("grid_x", [])
                grid_y = swap["grid_region"].get("grid_y", [])
                if grid_x and grid_y:
                    # Format as "A-D / 1-4" if ranges, or list if small
                    if len(grid_x) <= 4 and len(grid_y) <= 4:
                        grid_desc = f"grids {', '.join(grid_x)} / {', '.join(grid_y)}"
                    else:
                        grid_desc = f"grids {', '.join(grid_x[:4])}{'...' if len(grid_x) > 4 else ''} / {', '.join(grid_y[:4])}{'...' if len(grid_y) > 4 else ''}"
                elif grid_x:
                    grid_desc = f"grids {', '.join(grid_x[:4])}{'...' if len(grid_x) > 4 else ''}"
                elif grid_y:
                    grid_desc = f"grids {', '.join(grid_y[:4])}{'...' if len(grid_y) > 4 else ''}"
            
            if grid_desc:
                location_parts.append(f"at {grid_desc}")
            
            location_desc = " " + " ".join(location_parts) if location_parts else ""
            
            example_str = ""
            if swap.get("example_objects"):
                examples = swap["example_objects"][:3]
                example_str = f" (examples: {', '.join(examples)})"
            
            lines.append(
                f"  • {swap['count']} {swap['object_type']}s{location_desc}: "
                f"{swap['old_section']} → {swap['new_section']}{example_str}"
            )
        lines.append("")
    
    # Material changes
    if data["material_changes"]:
        lines.append("=== MATERIAL PROPERTY CHANGES ===")
        for mat in data["material_changes"]:
            field_changes = []
            for field, change in mat["changed_fields"].items():
                field_changes.append(f"{field}: {change['old']} → {change['new']}")
            lines.append(f"  • {mat['material']}: {', '.join(field_changes)}")
        lines.append("")
    
    # Load combo changes
    if data["load_combo_changes"]:
        lines.append("=== LOAD COMBINATION CHANGES ===")
        for combo in data["load_combo_changes"]:
            if combo["change_type"] == "added":
                terms_str = ", ".join([f"{t['factor']}*{t['name']}" for t in combo["new_terms"]])
                lines.append(f"  • Added: {combo['name']} = {terms_str}")
            elif combo["change_type"] == "removed":
                lines.append(f"  • Removed: {combo['name']}")
            else:  # modified
                old_terms = ", ".join([f"{t['factor']}*{t['name']}" for t in combo["old_terms"]])
                new_terms = ", ".join([f"{t['factor']}*{t['name']}" for t in combo["new_terms"]])
                lines.append(f"  • Modified: {combo['name']} = {old_terms} → {new_terms}")
        lines.append("")
    
    # Geometry changes
    if data["geometry_changes"]:
        lines.append("=== GEOMETRY CHANGES ===")
        for geom in data["geometry_changes"]:
            if geom["added"] > 0:
                lines.append(f"  • Added {geom['added']} {geom['object_type']}(s)")
            if geom["removed"] > 0:
                lines.append(f"  • Removed {geom['removed']} {geom['object_type']}(s)")
        lines.append("")
    
    # Other changes (section assignments, etc.)
    if data["other_changes"]:
        lines.append("=== OTHER CHANGES ===")
        for other in data["other_changes"]:
            if isinstance(other, dict):
                change_type = other.get("type", "unknown")
                if change_type == "section_assignment_change":
                    lines.append(
                        f"  • Section assignments changed in '{other.get('section_name', 'unknown')}': "
                        f"{other.get('lines_added', 0)} added, {other.get('lines_removed', 0)} removed"
                    )
                elif change_type == "section_assignment_added":
                    lines.append(
                        f"  • New section assignments in '{other.get('section_name', 'unknown')}': "
                        f"{other.get('line_count', 0)} assignments"
                    )
                elif change_type == "section_assignment_removed":
                    lines.append(
                        f"  • Removed section assignments in '{other.get('section_name', 'unknown')}': "
                        f"{other.get('line_count', 0)} assignments"
                    )
                else:
                    lines.append(f"  • {other}")
            else:
                lines.append(f"  • {other}")
        lines.append("")
    
    return "\n".join(lines) if lines else "[No changes detected]"


def _count_changes(aggregated: AggregatedDiff) -> Dict[str, int]:
    """Count changes by category for machine summary."""
    counts = {
        "materials_added": 0,
        "materials_modified": 0,
        "materials_removed": 0,
        "sections_added": 0,
        "sections_modified": 0,
        "sections_removed": 0,
        "section_swaps": len(aggregated.section_swaps),
        "loads_added": 0,
        "loads_modified": 0,
        "loads_removed": 0,
        "geometry_added": 0,
        "geometry_removed": 0,
    }
    
    # Count material changes
    for mat_change in aggregated.material_changes:
        counts["materials_modified"] += 1
    
    # Count load combo changes
    for combo_change in aggregated.load_combo_changes:
        if combo_change.change_type == "added":
            counts["loads_added"] += 1
        elif combo_change.change_type == "removed":
            counts["loads_removed"] += 1
        else:
            counts["loads_modified"] += 1
    
    # Count geometry changes
    for geom_change in aggregated.geometry_changes:
        counts["geometry_added"] += geom_change.get("added", 0)
        counts["geometry_removed"] += geom_change.get("removed", 0)
    
    # Count section assignment changes from other_changes
    for other in aggregated.other_changes:
        if isinstance(other, dict):
            if other.get("type") == "section_assignment_added":
                counts["sections_added"] += 1
            elif other.get("type") == "section_assignment_removed":
                counts["sections_removed"] += 1
            elif other.get("type") == "section_assignment_change":
                counts["sections_modified"] += 1
    
    return counts


def summarize_diff_to_markdown(
    llm: LLMClient,
    old_label: str,
    new_label: str,
    aggregated: AggregatedDiff,
    *,
    style: Literal["short", "detailed"] = "short",
    project_name: Optional[str] = None,
) -> str:
    """
    High-level helper: build prompt → call LLM → return markdown summary.
    """
    prompt_dict = build_summary_prompt(old_label, new_label, aggregated, style=style, project_name=project_name)
    
    # For LLM clients that expect dict format, pass it directly
    # For legacy clients that expect string, convert it
    if hasattr(llm, 'summarize'):
        # Try dict format first (new OpenAI client supports it)
        try:
            return llm.summarize(prompt_dict)
        except TypeError:
            # Fall back to string format for legacy clients
            prompt_str = f"{prompt_dict['system']}\n\n{prompt_dict['user']}"
            return llm.summarize(prompt_str)
    else:
        # Legacy string format
        prompt_str = f"{prompt_dict['system']}\n\n{prompt_dict['user']}"
        return llm.summarize(prompt_str)


def aggregated_to_json(aggregated: AggregatedDiff) -> Dict[str, Any]:
    """
    Convert AggregatedDiff to compact JSON for LLM consumption.
    This is the payload that gets sent to the LLM.
    """
    return _aggregated_to_dict(aggregated)


class DummyLLMClient:
    """
    Dummy LLM client for testing - just formats the aggregated diff.
    """
    def summarize(self, prompt: str | Dict[str, str]) -> str:
        # Handle both dict format (new) and string format (legacy)
        if isinstance(prompt, dict):
            user_message = prompt.get("user", "")
            # Extract the change data section
            if "DETECTED CHANGES:" in user_message:
                data_section = user_message.split("DETECTED CHANGES:")[1].split("Your tasks:")[0].strip()
                return f"# Model Change Summary\n\n## Detected Changes\n\n{data_section}\n\n*Note: This is a dummy summary. Connect a real LLM client for actual summarization.*"
            return "# Model Change Summary\n\n*No changes detected or unable to parse changes.*"
        else:
            # Legacy string format
            if "Analyze the following changes" in prompt:
                data_section = prompt.split("Analyze the following changes")[1]
                return f"# Model Change Summary\n\n{data_section}\n\n*Note: This is a dummy summary. Connect a real LLM client for actual summarization.*"
            return "# Model Change Summary\n\n*No changes detected or unable to parse changes.*"


class OpenAILLMClient:
    """
    OpenAI LLM client implementation using the OpenAI API.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
    ):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key. If None, will try to load from OPENAI_API_KEY env var.
            model: Model to use (default: gpt-4o-mini for cost efficiency)
            temperature: Temperature for generation (lower = more deterministic)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required. Install it with: pip install openai"
            )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.temperature = temperature
    
    def summarize(self, prompt: str | Dict[str, str]) -> str:
        """
        Call OpenAI API to summarize the prompt.
        
        Args:
            prompt: Either a dict with "system" and "user" keys, or a string (legacy format)
            
        Returns:
            Generated summary text
        """
        # Handle both dict format (new) and string format (legacy)
        if isinstance(prompt, dict):
            system_message = prompt.get("system", "You are a helpful assistant.")
            user_message = prompt.get("user", "")
        else:
            # Legacy string format - split on double newline
            if "\n\n" in prompt:
                parts = prompt.split("\n\n", 1)
                system_message = parts[0]
                user_message = parts[1]
            else:
                system_message = "You are a helpful assistant."
                user_message = prompt
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=self.temperature,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            return f"# Error generating summary\n\nAn error occurred while calling the OpenAI API: {str(e)}\n\nPlease check your API key and network connection."


def get_llm_client(
    use_openai: bool = True,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> LLMClient:
    """
    Factory function to get an LLM client.
    
    Args:
        use_openai: If True, use OpenAI client (requires API key). If False, use dummy client.
        api_key: Optional OpenAI API key. If None, will try to load from env.
        model: OpenAI model to use (default: gpt-4o-mini)
        
    Returns:
        LLMClient instance
    """
    if use_openai:
        try:
            return OpenAILLMClient(api_key=api_key, model=model)
        except (ValueError, ImportError) as e:
            print(f"Warning: Could not initialize OpenAI client: {e}")
            print("Falling back to DummyLLMClient")
            return DummyLLMClient()
    else:
        return DummyLLMClient()

