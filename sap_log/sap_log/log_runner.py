import os
import asyncio
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from requests import session
from google.genai import types # For creating message Content/Parts

import warnings
# Ignore all warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=ResourceWarning)

import logging
logging.basicConfig(level=logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)