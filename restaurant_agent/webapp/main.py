import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Add project root to sys.path to allow importing restaurant_agent.agent
# This assumes 'main.py' is in 'restaurant_agent/webapp/'
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# Ensure this path is correct for your project structure
# If restaurant_agent is the root of the package, then path should be one level up from 'restaurant_agent' directory
# Or if the 'restaurant_agent' directory itself is what should be in sys.path (e.g. for `from restaurant_agent.agent...`)
# then PROJECT_ROOT should point to the directory *containing* the `restaurant_agent` package.
# For the current structure, assuming `restaurant_agent` is the main package directory:
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # To import from 'agent'
# Let's adjust to allow `from restaurant_agent.agent...`
# This means the directory *containing* `restaurant_agent` must be in sys.path.
# If running `uvicorn restaurant_agent.webapp.main:app` from the directory containing `restaurant_agent`,
# Python will often handle this. But for `python restaurant_agent/webapp/main.py`, sys.path manipulation is key.
# The instruction was: `from ..agent.restaurant_agent import RestaurantAgent`
# This implies that `webapp` is a module inside `restaurant_agent`.
# Let's try to make that work by adding the parent of `restaurant_agent` if this file is run directly.
# However, the problem states: `from restaurant_agent.agent.restaurant_agent import RestaurantAgent`
# which implies `restaurant_agent` (the top-level folder) is already expected to be in PYTHONPATH.
# Let's use the provided snippet:
sys.path.append(PROJECT_ROOT) # PROJECT_ROOT is the dir containing the `restaurant_agent` package.

try:
    from restaurant_agent.agent.restaurant_agent import RestaurantAgent
except ModuleNotFoundError:
    # Fallback if the above path logic isn't perfect for all execution contexts
    # This might happen if PROJECT_ROOT is actually 'restaurant_agent' itself.
    # Let's try adding one level up from this file's parent.
    # This is 'restaurant_agent' directory if main.py is in restaurant_agent/webapp
    PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if PARENT_DIR not in sys.path:
        sys.path.append(PARENT_DIR)
    from agent.restaurant_agent import RestaurantAgent


app = FastAPI(title="Restaurant Agent API", version="1.0.0")

# Mount static files: CSS, JS, etc.
# The path "static" here is relative to the directory where main.py is located.
# So, it points to restaurant_agent/webapp/static
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Initialize RestaurantAgent
print("Initializing RestaurantAgent for FastAPI app...")
agent = RestaurantAgent()

if not agent.gemma_service or not agent.gemma_service.initialized:
    print("WARNING: RestaurantAgent's GemmaService failed to initialize during FastAPI app setup.")
    # The API will still start, but /chat endpoint will return an error.

# Request/Response Models
class UserMessage(BaseModel):
    message: str

class AgentResponse(BaseModel):
    response: str
    error: bool = False
    error_message: str | None = None

# Store the path to index.html to avoid recalculating it on every request
INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

@app.get("/", response_class=HTMLResponse, summary="Serves the chat interface")
async def read_root():
    """
    Serves the main HTML page for the chat interface.
    """
    try:
        with open(INDEX_HTML_PATH) as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        # This should ideally not happen if paths are correct
        raise HTTPException(status_code=404, detail="index.html not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading index.html: {e}")


@app.post("/chat", response_model=AgentResponse, summary="Chat with the Restaurant Agent")
async def chat(user_message: UserMessage):
    """
    Handles a user's message and returns the agent's response.
    """
    if not agent.gemma_service or not agent.gemma_service.initialized:
        # This check is important if Gemma failed to load
        raise HTTPException(
            status_code=503, 
            detail="NLU service (Gemma) is not initialized. The agent cannot process requests."
        )
    
    try:
        print(f"API /chat received: {user_message.message}")
        agent_reply = agent.handle_message(user_message.message)
        print(f"API /chat sending reply: {agent_reply}")
        return AgentResponse(response=agent_reply)
    except Exception as e:
        print(f"Error in /chat endpoint: {e}")
        # Log the full exception details here in a real application
        raise HTTPException(
            status_code=500, 
            detail=f"An internal error occurred: {str(e)}"
        )

if __name__ == "__main__":
    print("Attempting to run Uvicorn server...")
    if not agent.gemma_service or not agent.gemma_service.initialized:
        print("ERROR: RestaurantAgent's GemmaService failed to initialize. API cannot start.")
        print("Please check Gemma model loading and configuration.")
    else:
        print("RestaurantAgent initialized. Starting API with Uvicorn...")
        # Uvicorn expects the app string as 'module:instance'
        # When running this script directly, app is already an instance.
        # So, we pass the app instance directly.
        uvicorn.run(app, host="0.0.0.0", port=8000)
