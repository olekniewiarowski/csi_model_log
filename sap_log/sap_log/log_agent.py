from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm # For multi-model support
from google.adk.tools import MCPToolset
import numpy as np 
import pathlib
import shutil
import sys
import os
from typing import Optional
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


# More supported models can be referenced here: https://ai.google.dev/gemini-api/docs/models#model-variations
MODEL_GEMINI_2_0_FLASH = "gemini-2.5-flash"

# Use one of the model constants defined earlier
AGENT_MODEL = MODEL_GEMINI_2_0_FLASH # Starting with Gemini

def process_text_file(file_path: str) -> dict:
    """Reads and processes a text file, returning its content as a dictionary."""
    from text_parser import parse_et_file
    parsed_content = parse_et_file(file_path)
    return parsed_content

etabs_agent = Agent(
    name="etabs_logger_agent",
    model=AGENT_MODEL,
    description="An agent that will help log etabs models from their $et files ",
    instruction="""
                1. You are an expert in parsing ETABS model files and extracting relevant information.
                2. You will analyze the provided $et file content and identify the differences between two versions of the model.
                3. Summarize the changes in a clear and concise manner, focusing on key modifications such as additions, deletions, and updates to model elements.
                4. You should only look at the differences in the two file dictionaries that have been parsed. Do not make assumptions beyond the provided data.
                """,
                tools=[process_text_file, #MCPToolset(
            # connection_params=StdioConnectionParams(
            #     server_params = StdioServerParameters(
            #         command='npx',
            #         args=[process_text_file
                        # "-y",  # Argument for npx to auto-confirm install
                        # "@modelcontextprotocol/server-filesystem",
                        # # IMPORTANT: This MUST be an ABSOLUTE path to a folder the
                        # # npx process can access.
                        # # Replace with a valid absolute path on your system.
                        # # For example: "/Users/youruser/accessible_mcp_files"
                        # # or use a dynamically constructed absolute path:
                        # os.path.abspath(os.getcwd()),
            #         ],
            #     ),
            # ),
            # Optional: Filter which tools from the MCP server are exposed
            # tool_filter=['list_directory', 'read_file']
                ]
        )
