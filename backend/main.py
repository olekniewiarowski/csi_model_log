"""
LLM backend for ETABS model diff summarization.

- Main use in hackathon:
    * ETABS plugin calls this script with a TARGET DIRECTORY.
    * Script finds the 2 most recent ETABS export files in that directory.
    * Older file = OLD, newest file = NEW.
    * Sends both to an OpenAI model with a structured prompt.
    * Writes:
        - <new_model_basename>_summary.txt  (markdown content)
        - <new_model_basename>_summary.md   (same markdown, for UIs)
        - <new_model_basename>_stats.json   (machine-readable counts)
    * Optionally launches a Streamlit frontend server.

Requirements:
    pip install openai python-dotenv streamlit

Environment:
    .env at project root with:
        OPENAI_API_KEY=sk-...

Example CLI usage (from repo root):
    python -m backend.llm data --project "DemoBuilding"
"""

import argparse
import json
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from openai import OpenAI  # pip install openai
from dotenv import load_dotenv  # pip install python-dotenv

# ----------------- ENV / PATH SETUP ----------------- #

# Project root = parent of this file's directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load .env from project root so OPENAI_API_KEY is available
env_path = PROJECT_ROOT / ".env"
load_dotenv(env_path)

# ----------------- LLM CONFIG ----------------- #

# Default OpenAI model (adjust as you like)
# e.g. "gpt-4.1-mini", "gpt-4.1", etc. depending on your access
DEFAULT_LLM_MODEL = "gpt-5.1"


def get_client() -> OpenAI:
    """
    Create an OpenAI client using the OPENAI_API_KEY environment variable.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Set it in your .env file at project root."
        )
    return OpenAI(api_key=api_key)


# ----------------- CORE UTILITIES ----------------- #

def read_text_file(path: str) -> str:
    """
    Read a text file with safe defaults.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def get_filename(path: str) -> str:
    """
    Extract the filename from a given file path.
    """
    return os.path.basename(path)


def find_two_most_recent_files(
    directory: str,
    allowed_extensions: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Find the two most recently modified files in a directory.

    Returns:
        (oldest_of_two, newest_of_two)

    allowed_extensions: e.g. [".$et", ".et", ".txt"] or None for all files.
    """
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Target directory not found: {directory}")

    entries: List[Tuple[float, str]] = []
    for name in os.listdir(directory):
        full = os.path.join(directory, name)
        if not os.path.isfile(full):
            continue

        if allowed_extensions:
            _, ext = os.path.splitext(name)
            if ext.lower() not in [e.lower() for e in allowed_extensions]:
                continue

        mtime = os.path.getmtime(full)
        entries.append((mtime, full))

    if len(entries) < 2:
        raise RuntimeError(
            f"Need at least 2 model files in directory '{directory}', "
            f"found {len(entries)}."
        )

    # Sort by modification time, oldest first
    entries.sort(key=lambda x: x[0])
    old_path = entries[-2][1]
    new_path = entries[-1][1]
    return old_path, new_path


# ----------------- PROMPT BUILDING ----------------- #

def build_prompt(
    old_model_path: str,
    new_model_path: str,
    old_text: str,
    new_text: str,
    project_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the system + user messages for the LLM call.
    """
    project_part = f" for project: {project_name}" if project_name else ""

    system_message = (
        "You are an expert structural engineering assistant. "
        "You compare two ETABS model text exports and produce a precise, "
        "concise change log. You MUST only describe differences that are "
        "actually present between the two versions. "
        "You MUST NOT invent any changes or guess about unclear items. "
        "You can understand the relation between grid lines, levels, and structural elements. "
    )

    user_message = textwrap.dedent(
        f"""
        We have two versions of the same ETABS model{project_part}.

        OLD VERSION (previous model export)
        -----------------------------------
        {old_text if old_text.strip() else "[No previous model – this is the first version.]"}

        NEW VERSION (current model export)
        -----------------------------------
        {new_text}

        Your tasks:

        1. Identify additions, deletions, and modifications between OLD and NEW.
           Focus on structural modeling changes such as:
             - Materials
             - Frame/shell section properties
             - Assignments (if clearly visible in the text)
             - Load patterns and load cases
             - Load combinations
             - Any other clearly represented ETABS definitions.

           You should identify relationships such as the grid location of elements,
           points, slabs and levels.

        2. Produce a human-readable summary in MARKDOWN with this structure:

           ## Compared Model: {get_filename(new_model_path)}

           ## Base Model: {get_filename(old_model_path)}

           ## Key Changes (high-level)
           - Short bullet list summarizing the main types of changes, by providing more context with relevant features.
           - While describing the changes, describe the location of the change in terms of grid lines, levels, and element types.
             Example: "Changed column on L2 at Grid-Line A-1 from W12x50 to W14x65."
             Example: "Added new load combination 'Wind-2' with 0.3*WindX + 0.3*WindY."

           ### Detailed Changes

           ## Materials
           - Bullet points for added/removed/modified materials (if any).

           ## Sections
           - Bullet points for added/removed/modified frame/shell/section properties.

           ## Loads and Load Combinations
           - Bullet points for changes to load patterns, load cases, and load combos.

           ## Other Notable Changes
           - Anything else that is structurally relevant.

        3. At the end, add a small machine-readable JSON block under a heading
           '## Machine Summary' in the following format:

           ```json
           {{
             "materials_added": <int>,
             "materials_modified": <int>,
             "materials_removed": <int>,
             "sections_added": <int>,
             "sections_modified": <int>,
             "sections_removed": <int>,
             "loads_added": <int>,
             "loads_modified": <int>,
             "loads_removed": <int>
           }}
           ```

           If a category is not mentioned in the diff, use 0 for those counts.
           Reformat the markdown to sort the changes by most changes to least changes.

        Rules:
        - Do NOT invent any changes that you cannot directly infer from the two texts.
        - If something is unclear, omit it instead of guessing.
        - Be concise but clear. The primary audience is a structural engineer.
        """
    ).strip()

    return {
        "system": system_message,
        "user": user_message,
    }


# ----------------- LLM CALL ----------------- #

def call_llm(
    client: OpenAI,
    model: str,
    system_message: str,
    user_message: str,
) -> str:
    """
    Call the OpenAI LLM and return the raw markdown response text.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,  # keep it factual and stable
    )
    return response.choices[0].message.content or ""


def extract_machine_stats_from_markdown(markdown_text: str) -> Dict[str, Any]:
    """
    Parse the JSON block under the '## Machine Summary' section.

    If parsing fails, return an empty dict. This keeps the backend robust even
    if the model slightly misformats the section.
    """
    start_tag = "```json"
    end_tag = "```"

    start_idx = markdown_text.find(start_tag)
    if start_idx == -1:
        return {}

    start_idx += len(start_tag)
    end_idx = markdown_text.find(end_tag, start_idx)
    if end_idx == -1:
        return {}

    json_str = markdown_text[start_idx:end_idx].strip()
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def analyze_models(
    old_model_path: Optional[str],
    new_model_path: str,
    project_name: Optional[str] = None,
    model: str = DEFAULT_LLM_MODEL,
) -> Dict[str, Any]:
    """
    Main entrypoint for backend logic.

    - Reads the two model files.
    - Builds prompt and calls LLM.
    - Returns a dict with:
        {
          "summary_markdown": str,
          "machine_stats": dict,
          "new_model_path": str,
          "old_model_path": Optional[str]
        }
    """

    if not os.path.isfile(new_model_path):
        raise FileNotFoundError(f"New model file not found: {new_model_path}")

    old_text = ""
    if old_model_path:
        if not os.path.isfile(old_model_path):
            raise FileNotFoundError(f"Old model file not found: {old_model_path}")
        old_text = read_text_file(old_model_path)

    new_text = read_text_file(new_model_path)

    prompt = build_prompt(old_model_path, new_model_path, old_text, new_text, project_name=project_name)

    client = get_client()
    markdown = call_llm(
        client=client,
        model=model,
        system_message=prompt["system"],
        user_message=prompt["user"],
    )

    stats = extract_machine_stats_from_markdown(markdown)

    return {
        "summary_markdown": markdown,
        "machine_stats": stats,
        "new_model_path": new_model_path,
        "old_model_path": old_model_path,
    }


# ----------------- OUTPUT HELPERS ----------------- #

def write_outputs(result: Dict[str, Any]) -> None:
    """
    Given the result from analyze_models, write summary + stats
    next to the new model file.

    - <new_base>_summary.txt   (markdown text)
    - <new_base>_summary.md    (same markdown, for UIs)
    - <new_base>_stats.json    (machine summary)
    """
    new_model_path = result["new_model_path"]
    new_dir = os.path.dirname(new_model_path)
    new_base = os.path.splitext(os.path.basename(new_model_path))[0]

    summary_txt = os.path.join(new_dir, f"{new_base}_summary.txt")
    summary_md = os.path.join(new_dir, f"{new_base}_summary.md")
    stats_path = os.path.join(new_dir, f"{new_base}_stats.json")

    markdown = result["summary_markdown"]

    # Write summary as both .txt and .md (same markdown content)
    for path in (summary_txt, summary_md):
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown)

    # Write stats JSON (if any)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(result.get("machine_stats", {}), f, indent=2)

    print(f"[LLM] Wrote summary (txt): {summary_txt}")
    print(f"[LLM] Wrote summary (md):  {summary_md}")
    print(f"[LLM] Wrote stats json:    {stats_path}")


def run_streamlit(app_path: str) -> None:
    """
    Launch the Streamlit frontend server in a separate process.

    This is non-blocking: it spawns the process and returns.
    """
    app_full = PROJECT_ROOT / app_path
    if not app_full.is_file():
        print(f"[LLM] Streamlit app not found at {app_full}. Skipping launch.")
        return

    try:
        subprocess.Popen(
            ["streamlit", "run", str(app_full)],
            shell=False,
        )
        print(f"[LLM] Launched Streamlit app: {app_full}")
    except FileNotFoundError:
        print("[LLM] Could not start Streamlit: 'streamlit' command not found.")


# ----------------- CLI ENTRYPOINT ----------------- #

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run LLM diff + summary on the two most recent ETABS exports "
            "in a target directory."
        )
    )
    parser.add_argument(
        "target_dir",
        help="Directory containing ETABS model exports (e.g. ./data).",
    )
    parser.add_argument(
        "--project",
        "-p",
        help="Optional project name to include in the prompt.",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_LLM_MODEL,
        help=f"OpenAI model name (default: {DEFAULT_LLM_MODEL})",
    )
    parser.add_argument(
        "--ext",
        default=".$et,.et,.txt",
        help="Comma-separated list of allowed file extensions "
             "(default: '.$et,.et,.txt').",
    )
    parser.add_argument(
        "--streamlit-app",
        default="frontend/app.py",
        help="Relative path to Streamlit app to launch after run.",
    )
    parser.add_argument(
        "--no-streamlit",
        action="store_true",
        help="If set, do not launch Streamlit after generating summary.",
    )

    args = parser.parse_args()

    allowed_exts = [e.strip() for e in args.ext.split(",") if e.strip()]
    old_path, new_path = find_two_most_recent_files(args.target_dir, allowed_exts)

    print(f"[LLM] Old model: {old_path}")
    print(f"[LLM] New model: {new_path}")

    result = analyze_models(
        old_model_path=old_path,
        new_model_path=new_path,
        project_name=args.project,
        model=args.model,
    )

    print("\n========== LLM SUMMARY (markdown) ==========\n")
    print(result["summary_markdown"])
    print("\n============================================\n")

    write_outputs(result)

    if not args.no_streamlit:
        run_streamlit(args.streamlit_app)


if __name__ == "__main__":
    main()
