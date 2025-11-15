import os
import asyncio
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from requests import session
from google.genai import types # For creating message Content/Parts
from log_agent import etabs_agent as log_agent

import warnings
# Ignore all warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=ResourceWarning)

import logging
logging.basicConfig(level=logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

APP_NAME = "etabs_logger_app"
USER_ID = "user_1"
SESSION_ID = "session_001" # Using a fixed ID for simplicity

# Gemini API Key (Get from Google AI Studio: https://aistudio.google.com/app/apikey)
os.environ["GOOGLE_API_KEY"] = os.environ.get("GEMINI_API_KEY")

async def create_session_service(initial_state):
    session_service = InMemorySessionService()
    session = await session_service.create_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID,
    state=initial_state
    )

    return session, session_service

async def delete_session_service(session_service):
    # Clean up (optional for this example)
    temp_service = await session_service.delete_session(app_name=APP_NAME,
                                user_id=USER_ID, session_id=SESSION_ID)
    print("The final status of temp_service - ", temp_service)
    # Ensure runtime registry is cleaned for this session
    try:
        log_agent.delete_runtime(SESSION_ID)
    except Exception:
        pass


async def call_agent_async(query: str, runner, user_id, session_id):
  """Sends a query to the agent and prints the final response."""
    #print(f"\n>>> User Query: {query}")
#   async with aiohttp.ClientSession() as client_session:
    # Prepare the user's message in ADK format
  content = types.Content(role='user', parts=[types.Part(text=query)])

  final_response_text = "Agent did not produce a final response." # Default

    # Iterate through events to find the final answer.
    
  async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
    # You can uncomment the line below to see *all* events during execution
    # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

    # Key Concept: is_final_response() marks the concluding message for the turn.
    if event.is_final_response():
        if event.content and event.content.parts:
            # Assuming text response in the first part
            final_response_text = event.content.parts[0].text
        elif event.actions and event.actions.escalate: # Handle potential errors/escalations
            final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
        # Add more checks here if needed (e.g., specific error codes)
        break # Stop processing events once the final response is found
  print(f"<<< Agent Response: {final_response_text}")


  
  # @title Run the Initial Conversation

# We need an async function to await our interaction helper
async def run_conversation(runner):
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        await call_agent_async(user_input,
                               runner=runner,
                               user_id=USER_ID,
                               session_id=SESSION_ID)
    
async def main():
    print("Welcome to the etabs logging agent!")
    initial_state = {
    }
    # Ensure the session id is available in tool_context.state for registry lookup
    initial_state['_session_id'] = SESSION_ID

    # InMemorySessionService is simple, non-persistent storage for this tutorial.
    session, session_service = await create_session_service(initial_state)   
    runner = Runner(
        agent=log_agent, # The agent we want to run
        app_name=APP_NAME,   # Associates runs with our app
        session_service=session_service # Uses our session manager
    )
    try:
        await run_conversation(runner)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # await session.close()
        await delete_session_service(session_service)
        runner.close()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    print('done')
    