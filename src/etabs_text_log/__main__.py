"""
Simple script to find the latest two ETABS files and generate a diff summary.

Usage:
    python -m etabs_text_log <directory>
"""
import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple

from .parser import parse_et_file
from .model import EtabsModel
from .location import attach_story_and_grid_tags
from .diffing import diff_models
from .aggregate import aggregate_diff
from .summarize import get_llm_client, summarize_diff_to_markdown


def find_latest_two_files(directory: str) -> Optional[Tuple[str, str]]:
    """
    Find the two most recent .$et or .e2k files in the given directory.
    
    Args:
        directory: Path to directory to search
        
    Returns:
        Tuple of (older_file, newer_file) paths, or None if less than 2 files found
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Error: Directory does not exist: {directory}", file=sys.stderr)
        return None
    
    if not dir_path.is_dir():
        print(f"Error: Path is not a directory: {directory}", file=sys.stderr)
        return None
    
    # Find all .$et and .e2k files
    et_files = list(dir_path.glob("**/*.$et")) + list(dir_path.glob("**/*.e2k")) + list(dir_path.glob("**/*.et"))
    
    if len(et_files) < 2:
        print(f"Error: Found only {len(et_files)} ETABS file(s). Need at least 2 files.", file=sys.stderr)
        return None
    
    # Sort by modification time, most recent first
    et_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Get the two most recent
    newer_file = str(et_files[0])
    older_file = str(et_files[1])
    
    return (older_file, newer_file)


def llm_call(older_file: str, newer_file: str, style: str = "short", use_llm: bool = True, model: str = "gpt-4o-mini") -> str:
    """
    Process two ETABS model files and generate a markdown summary using LLM.
    
    Args:
        older_file: Path to the older model file
        newer_file: Path to the newer model file
        style: Summary style - "short" or "detailed" (default: "short")
        use_llm: Whether to use OpenAI LLM (default: True)
        model: OpenAI model to use (default: "gpt-4o-mini")
        
    Returns:
        Markdown summary string
    """
    # Parse models
    old_model = parse_et_file(older_file)
    new_model = parse_et_file(newer_file)
    
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
    old_label = Path(older_file).stem
    new_label = Path(newer_file).stem
    
    # Generate markdown summary
    summary = summarize_diff_to_markdown(
        llm=llm,
        old_label=old_label,
        new_label=new_label,
        aggregated=aggregated,
        style=style
    )
    
    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Find the latest two ETABS files and generate a diff summary"
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Directory to search for ETABS files (.$et, .e2k, .et)"
    )
    parser.add_argument(
        "--style",
        type=str,
        choices=["short", "detailed"],
        default="short",
        help="Summary style (default: short)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM and use dummy client"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)"
    )
    
    args = parser.parse_args()
    
    # Find the two latest files
    file_pair = find_latest_two_files(args.directory)
    if file_pair is None:
        sys.exit(1)
    
    older_file, newer_file = file_pair
    
    print(f"Processing files:", file=sys.stderr)
    print(f"  Older: {older_file}", file=sys.stderr)
    print(f"  Newer: {newer_file}", file=sys.stderr)
    print("", file=sys.stderr)
    
    # Generate summary
    try:
        summary = llm_call(
            older_file,
            newer_file,
            style=args.style,
            use_llm=not args.no_llm,
            model=args.model
        )
        
        # Print summary to stdout
        print(summary)
        
    except Exception as e:
        print(f"Error processing files: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

