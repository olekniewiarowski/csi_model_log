import difflib
import html
import json
import os
import re
from datetime import datetime
import sys
from tkinter import Tk, filedialog
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

DEFAULT_FOLDER_PATH = "."
if len(sys.argv) > 1:
    DEFAULT_FOLDER_PATH = sys.argv[1]

# Set page config to use wide layout
st.set_page_config(page_title="CSI MODEL LOG UI", layout="wide")


def get_card_color(key: Any, value: Any) -> Optional[str]:
    """Determine card background color based on content keywords"""
    # Convert key to lowercase for checking
    key_str = str(key).lower()

    # Check if key ends with specific keywords
    if key_str.endswith("modified"):
        return "#8dbeff"  # Blue
    elif key_str.endswith("added"):
        return "#9ffa9f"  # Green
    elif key_str.endswith("removed"):
        return "#ff9191"  # Red

    # Check the value format if it's a dict
    if isinstance(value, dict) and len(value) == 1:
        # Handle {text: number} format
        text_key = next(iter(value.keys()))
        value_str = str(text_key).lower()
        if value_str.endswith("modified"):
            return "#8dbeff"  # Blue
        elif value_str.endswith("added"):
            return "#9ffa9f"  # Green
        elif value_str.endswith("removed"):
            return "#ff9191"  # Red

    return None


def create_card_html(key: str, value: Any, bg_color: Optional[str] = None) -> str:
    """Generate HTML for a display card with optional background color"""
    if bg_color:
        return f"""
        <div style="
            background-color: {bg_color};
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #444;
            margin-bottom: 10px;
            text-align: center;
        ">
            <h3 style="margin: 0 0 15px 0; color: white;">📋 {html.escape(key)}</h3>
            <p style="font-size: 48px; font-weight: bold; margin: 0; color: white;">{value}</p>
        </div>
        """
    else:
        return f"""
        <div style="
            background-color: #2b2b2b;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #444;
            margin-bottom: 10px;
            text-align: center;
        ">
            <h3 style="margin: 0 0 15px 0;">📋 {html.escape(key)}</h3>
            <p style="font-size: 48px; font-weight: bold; margin: 0;">{value}</p>
        </div>
        """


def display_model_log_json(data: Any) -> None:
    """Display ModelLog.json in a card-based layout with 4 cards per row"""
    if isinstance(data, dict):
        # Get all items as a list
        items = list(data.items())

        # Display items in rows of 4
        for row_idx in range(0, len(items), 4):
            cols = st.columns(4)
            row_items = items[row_idx : row_idx + 4]

            for col_idx, (key, value) in enumerate(row_items):
                with cols[col_idx]:
                    # Get background color based on content
                    bg_color = get_card_color(key, value)
                    card_html = create_card_html(key, value, bg_color)
                    st.markdown(card_html, unsafe_allow_html=True)

    elif isinstance(data, list):
        # Handle top-level array - display in rows of 4
        for row_idx in range(0, len(data), 4):
            cols = st.columns(4)
            row_items = data[row_idx : row_idx + 4]

            for col_idx, item in enumerate(row_items):
                with cols[col_idx]:
                    item_name = f"Item {row_idx + col_idx + 1}"
                    bg_color = get_card_color(item_name, item)

                    if bg_color:
                        # Custom styled container with color
                        st.markdown(
                            f"""
                            <div style="
                                background-color: {bg_color};
                                padding: 15px;
                                border-radius: 8px;
                                border: 1px solid #444;
                                margin-bottom: 10px;
                            ">
                                <h3 style="margin-top: 0;">📋 {item_name}</h3>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"### 📋 {item_name}")

                    with st.container(border=True):
                        if isinstance(item, dict):
                            for key, value in item.items():
                                st.markdown(f"**{key}:**")
                                if isinstance(value, (list, dict)):
                                    st.json(value)
                                else:
                                    st.write(value)
                        else:
                            st.write(item)


def display_compared_model_cards(content: str) -> None:
    """Display content split by ## and ### headers as cards"""
    # Find the position of "### Detailed Changes"
    detailed_changes_match = re.search(
        r"^### Detailed Changes", content, flags=re.MULTILINE
    )

    if detailed_changes_match:
        # Split content into before and after "### Detailed Changes"
        before_detailed = content[: detailed_changes_match.start()]
        after_detailed_full = content[detailed_changes_match.start() :]

        # Render the part before "### Detailed Changes" normally
        if before_detailed.strip():
            st.markdown(before_detailed.strip())

        # Find the first ## section after "### Detailed Changes"
        first_h2_match = re.search(r"^## ", after_detailed_full, flags=re.MULTILINE)

        if first_h2_match:
            # Split into "### Detailed Changes" part and the ## sections
            detailed_changes_header = after_detailed_full[: first_h2_match.start()]
            sections_content = after_detailed_full[first_h2_match.start() :]

            # Render "### Detailed Changes" as normal markdown
            if detailed_changes_header.strip():
                st.markdown(detailed_changes_header.strip())

            # Split the ## sections into expandable cards
            sections = re.split(r"^###? ", sections_content, flags=re.MULTILINE)

            # Skip the first empty section and process the rest
            for section in sections[1:]:
                if section.strip():
                    lines = section.split("\n", 1)
                    header = lines[0].strip()
                    body = lines[1] if len(lines) > 1 else ""

                    # Make header bold
                    bold_header = f"**{header}**"

                    with st.expander(bold_header):
                        with st.container(border=True):
                            if body.strip():
                                st.markdown(body)
                            else:
                                st.info("Nothing to display")
        else:
            # No ## sections found, render everything normally
            st.markdown(after_detailed_full.strip())
    else:
        # If "### Detailed Changes" is not found, render everything normally
        st.markdown(content)


def read_and_display_json_file(file_path: str) -> None:
    """Read and display JSON file (specifically ModelLog.json)"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        display_model_log_json(data)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON format: {str(e)}")
        # Fallback to regular text display
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                st.code(content, language="json", line_numbers=True)
        except Exception as ex:
            st.error(f"File reading error: {str(ex)}")
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")


def read_and_display_markdown_file(file_path: str) -> None:
    """Read and display Markdown file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Check if file starts with "## Compared Model:"
            if content.strip().startswith("## Compared Model:"):
                display_compared_model_cards(content)
            else:
                st.markdown(content)
    except Exception as e:
        st.error(f"File reading error: {str(e)}")


def read_and_display_text_file(file_path: str) -> None:
    """Read and display generic text file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Check if file starts with "## Compared Model:" for any text file
            if content.strip().startswith("## Compared Model:"):
                display_compared_model_cards(content)
            else:
                st.code(content, language=None, line_numbers=True)
    except UnicodeDecodeError:
        st.warning("Cannot display as text because it is a binary file")
    except Exception as e:
        st.error(f"File reading error: {str(e)}")


def display_file_metadata(selected_file: Dict[str, Any]) -> None:
    """Display file metadata information"""
    st.write(f"**File:** {selected_file['File Name']}")
    st.write(f"**Size:** {selected_file['Size (bytes)']} bytes")
    modified_datetime = datetime.fromtimestamp(selected_file["Modified"])
    st.write(f"**Modified:** {modified_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    st.divider()


def display_single_file_view(selected_file: Dict[str, Any]) -> None:
    """Display content preview for a single file"""
    st.subheader("Content Preview")
    file_path = selected_file["Path"]
    file_name = selected_file["File Name"]

    display_file_metadata(selected_file)

    # Check if it's a ModelLog.json file
    if file_name == "ModelLog.json" or file_name.endswith("ModelLog.json"):
        read_and_display_json_file(file_path)
    elif file_name.endswith(".md"):
        read_and_display_markdown_file(file_path)
    else:
        read_and_display_text_file(file_path)


def generate_diff_html_lines(diff_lines: List[str]) -> List[str]:
    """Generate HTML lines from diff output"""
    html_lines = []
    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            html_lines.append(f'<div class="line-header">{html.escape(line)}</div>')
        elif line.startswith("@@"):
            html_lines.append(f'<div class="line-info">{html.escape(line)}</div>')
        elif line.startswith("-"):
            html_lines.append(f'<div class="line-delete">{html.escape(line)}</div>')
        elif line.startswith("+"):
            html_lines.append(f'<div class="line-insert">{html.escape(line)}</div>')
        else:
            html_lines.append(f'<div class="line-context">{html.escape(line)}</div>')
    return html_lines


def create_diff_html(html_lines: List[str]) -> str:
    """Create CSS and HTML for diff rendering"""
    return f"""
    <style>
        .diff-container {{
            font-family: 'Courier New', monospace;
            font-size: 12px;
            background-color: #1e1e1e;
            border: 1px solid #444;
            border-radius: 4px;
            overflow-x: auto;
        }}
        .line-header {{
            background-color: #333;
            color: #aaa;
            padding: 2px 8px;
            font-weight: bold;
        }}
        .line-info {{
            background-color: #2d2d2d;
            color: #6ea5d8;
            padding: 2px 8px;
        }}
        .line-delete {{
            background-color: #4b1818;
            color: #ff9999;
            padding: 2px 8px;
        }}
        .line-insert {{
            background-color: #1a4b1a;
            color: #99ff99;
            padding: 2px 8px;
        }}
        .line-context {{
            background-color: #1e1e1e;
            color: #d4d4d4;
            padding: 2px 8px;
        }}
    </style>
    <div class="diff-container">
        {"".join(html_lines)}
    </div>
    """


def calculate_diff_statistics(
    diff_lines: List[str], lines1: List[str], lines2: List[str]
) -> Tuple[int, int, int, int]:
    """Calculate and return diff statistics"""
    additions = sum(
        1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    deletions = sum(
        1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
    )
    return len(lines1), len(lines2), additions, deletions


def display_diff_statistics(
    lines1_count: int, lines2_count: int, additions: int, deletions: int
) -> None:
    """Display diff statistics using Streamlit metrics"""
    st.divider()
    st.write("**Diff Statistics:**")
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("Lines in File 1", lines1_count)
    with col_stat2:
        st.metric("Lines in File 2", lines2_count)
    with col_stat3:
        st.metric("Changed Lines", f"+{additions} -{deletions}")


def display_diff_view(file1: Dict[str, Any], file2: Dict[str, Any]) -> None:
    """Display diff comparison for two files"""
    st.subheader("Diff Comparison")

    try:
        # Read both files
        with open(file1["Path"], "r", encoding="utf-8") as f:
            content1 = f.read()
            lines1 = content1.splitlines()
        with open(file2["Path"], "r", encoding="utf-8") as f:
            content2 = f.read()
            lines2 = content2.splitlines()

        # Check if files are identical
        if content1 == content2:
            st.info("Files are identical")
            st.code(content1, language=None, line_numbers=True)
        else:
            # Generate unified diff
            differ = difflib.unified_diff(
                lines1,
                lines2,
                fromfile=file1["File Name"],
                tofile=file2["File Name"],
                lineterm="",
            )
            diff_lines = list(differ)

            # Build and display HTML for unified diff
            html_lines = generate_diff_html_lines(diff_lines)
            diff_html = create_diff_html(html_lines)
            st.markdown(diff_html, unsafe_allow_html=True)

            # Calculate and display statistics
            lines1_count, lines2_count, additions, deletions = (
                calculate_diff_statistics(diff_lines, lines1, lines2)
            )
            display_diff_statistics(lines1_count, lines2_count, additions, deletions)

    except UnicodeDecodeError:
        st.warning("Cannot compare binary files")
    except Exception as e:
        st.error(f"Error comparing files: {str(e)}")


def display_multiple_files_view(
    files: List[Dict[str, Any]], selected_indices: List[int]
) -> None:
    """Display view when multiple files are selected"""
    st.subheader("Multiple Files Selected")
    selected_count = len(selected_indices)
    st.info(
        f"{selected_count} files selected. Diff comparison only works with 2 files."
    )
    st.write("**Selected files:**")
    for idx in selected_indices:
        st.write(f"- {files[idx]['File Name']}")


def get_files_from_folder(folder_path: str) -> List[Dict[str, Any]]:
    """Get list of files from the specified folder"""
    files = []
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            file_size = os.path.getsize(item_path)
            modified_time = os.path.getmtime(item_path)
            files.append(
                {
                    "File Name": item,
                    "Size (bytes)": file_size,
                    "Path": item_path,
                    "Modified": modified_time,
                }
            )
    # Sort files by modification time
    files.sort(key=lambda x: x["Modified"])
    return files


def handle_file_selection(idx: int) -> None:
    """Handle file selection logic based on multi-select mode"""
    if st.session_state.multi_select_mode:
        # Multi-select mode: toggle selection
        if idx in st.session_state.selected_file_indices:
            st.session_state.selected_file_indices.remove(idx)
            # Ensure at least one file is selected
            if not st.session_state.selected_file_indices:
                st.session_state.selected_file_indices = [idx]
        else:
            st.session_state.selected_file_indices.append(idx)
    else:
        # Single-select mode: replace selection
        st.session_state.selected_file_indices = [idx]


def render_file_list(files: List[Dict[str, Any]]) -> None:
    """Render the file list sidebar with clickable buttons"""
    st.subheader("Files")

    # Multi-select toggle
    if "multi_select_mode" not in st.session_state:
        st.session_state.multi_select_mode = False

    multi_select = st.toggle(
        "Multi-select",
        value=st.session_state.multi_select_mode,
        key="multi_select_toggle",
        help="Enable to select multiple files",
    )
    st.session_state.multi_select_mode = multi_select

    st.divider()

    # Display file list as clickable buttons
    for idx, file_info in enumerate(files):
        file_name = file_info["File Name"]
        is_selected = idx in st.session_state.selected_file_indices
        button_type = "primary" if is_selected else "secondary"

        if st.button(
            f"📄 {file_name}",
            key=f"file_{idx}",
            type=button_type,
            use_container_width=True,
        ):
            handle_file_selection(idx)
            st.rerun()


def render_file_content(files: List[Dict[str, Any]]) -> None:
    """Render the file content area based on selected files"""
    # Ensure we have at least one file selected
    if not st.session_state.selected_file_indices:
        st.session_state.selected_file_indices = [0]

    selected_count = len(st.session_state.selected_file_indices)

    if selected_count == 1:
        # Single file view
        selected_file = files[st.session_state.selected_file_indices[0]]
        display_single_file_view(selected_file)
    elif selected_count == 2:
        # Diff view for two files
        file1 = files[st.session_state.selected_file_indices[0]]
        file2 = files[st.session_state.selected_file_indices[1]]
        display_diff_view(file1, file2)
    else:
        # Multiple files selected (more than 2)
        display_multiple_files_view(files, st.session_state.selected_file_indices)


def render_folder_selector() -> str:
    """Render folder selection UI and return the selected folder path"""
    # Initialize session state for folder path
    if "folder_path" not in st.session_state:
        st.session_state.folder_path = DEFAULT_FOLDER_PATH

    # Create button to open folder dialog
    col1, col2 = st.columns([1, 7])
    with col1:
        if st.button("📁 Browse Folder"):
            # Create a Tkinter root window (hidden)
            root = Tk()
            root.withdraw()
            root.wm_attributes("-topmost", 1)

            # Open folder selection dialog
            selected_folder = filedialog.askdirectory(master=root)
            root.destroy()

            if selected_folder:
                st.session_state.folder_path = selected_folder

    with col2:
        # Input folder path
        folder_path = st.text_input(
            "Enter folder path:",
            value=st.session_state.folder_path,
            key="folder_input",
        )
        if folder_path != st.session_state.folder_path:
            st.session_state.folder_path = folder_path

    return st.session_state.folder_path


def render_file_browser(folder_path: str) -> None:
    """Render the main file browser interface"""
    # Check if path exists
    if not (os.path.exists(folder_path) and os.path.isdir(folder_path)):
        st.error("The specified path does not exist or is not a folder")
        return

    st.success(f"Folder: {folder_path}")

    # Get list of files in folder
    try:
        files = get_files_from_folder(folder_path)

        if not files:
            st.info("No files in this folder")
            return

        st.write(f"**Number of files: {len(files)}**")

        # Initialize session state for selected files
        if "selected_file_indices" not in st.session_state:
            st.session_state.selected_file_indices = [0]

        # Create two columns for file list and content
        left_col, right_col = st.columns([1, 6])

        with left_col:
            render_file_list(files)

        with right_col:
            render_file_content(files)

    except PermissionError:
        st.error("No permission to access this folder")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")


def main() -> None:
    """Main application entry point"""
    st.title("CSI MODEL LOG UI")
    folder_path = render_folder_selector()

    if folder_path:
        render_file_browser(folder_path)


if __name__ == "__main__":
    main()
