"""
LLM backend for ETABS model diff summarization.

- Takes paths to two ETABS model text exports:
    * old_model_path  (previous version, can be None/empty on first run)
    * new_model_path  (current version)

- Sends both to an LLM with a structured prompt asking for:
    * A clear, human-readable change log
    * Organized by categories (materials, sections, loads, etc.)
    * No hallucinated changes

- Writes:
    * <new_model_basename>_summary.txt
    * <new_model_basename>_stats.json

Requirements:
    pip install openai python-dotenv   # if using .env for the key

Environment:
    OPENAI_API_KEY must be set.

Example CLI usage:
    python -m backend.llm data/Model1.$et data/Model2.$et --project "DemoBuilding"
"""

import argparse
import json
import os
import textwrap
from typing import Optional, Dict, Any

from openai import OpenAI  # pip install openai
from dotenv import load_dotenv  # pip install python-dotenv

# Load .env file if present
load_dotenv()

# ------------ LLM CONFIG ------------ #

# You can change the model name here (e.g. "gpt-4.1", "gpt-4o-mini", etc.)
DEFAULT_LLM_MODEL = "gpt-5.1"


def get_client() -> OpenAI:
    """
    Create an OpenAI client using the OPENAI_API_KEY environment variable.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Set it in your environment or .env file."
        )
    return OpenAI(api_key=api_key)


# ------------ CORE LOGIC ------------ #

def read_text_file(path: str) -> str:
    """
    Read a text file with safe defaults.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def build_prompt(
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
        "actually present between the two versions."
    )

    # Keep user prompt as instructions + raw texts
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

        2. Produce a human-readable summary in MARKDOWN with this structure:

           ## Key Changes (high-level)
           - Short bullet list summarizing the main types of changes.

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


def call_llm(
    client: OpenAI,
    model: str,
    system_message: str,
    user_message: str,
) -> str:
    """
    Call the LLM and return the raw markdown response text.
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
    # Simple heuristic: find the first ```json ... ``` block and parse it
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

    prompt = build_prompt(old_text, new_text, project_name=project_name)

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


# ------------ OUTPUT HELPERS ------------ #

def write_outputs(result: Dict[str, Any]) -> None:
    """
    Given the result from analyze_models, write summary + stats
    next to the new model file.
    """
    new_model_path = result["new_model_path"]
    new_dir = os.path.dirname(new_model_path)
    new_base = os.path.splitext(os.path.basename(new_model_path))[0]

    summary_path = os.path.join(new_dir, f"{new_base}_summary.txt")
    stats_path = os.path.join(new_dir, f"{new_base}_stats.json")

    # Write summary markdown as plain text
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(result["summary_markdown"])

    # Write stats JSON (if any)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(result.get("machine_stats", {}), f, indent=2)

    print(f"[LLM] Wrote summary to: {summary_path}")
    print(f"[LLM] Wrote stats to:   {stats_path}")


# ------------ CLI ENTRYPOINT ------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Run LLM diff + summary on two ETABS model text exports."
    )
    parser.add_argument(
        "old_model",
        nargs="?",
        help="Path to OLD model file (can be omitted for first version).",
    )
    parser.add_argument(
        "new_model",
        help="Path to NEW model file.",
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
        help=f"LLM model name (default: {DEFAULT_LLM_MODEL})",
    )

    args = parser.parse_args()

    result = analyze_models(
        old_model_path=args.old_model,
        new_model_path=args.new_model,
        project_name=args.project,
        model=args.model,
    )

    # Print to console for quick debugging
    print("\n========== LLM SUMMARY (markdown) ==========\n")
    print(result["summary_markdown"])
    print("\n============================================\n")

    # And persist to disk
    write_outputs(result)


if __name__ == "__main__":
    main()
