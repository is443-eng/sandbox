# 02_inches_to_mm_function_calling.py
# Function Calling Example: inches to millimeters
# Companion to 02_function_calling.py (add-two-numbers); does not replace it.

# This script demonstrates how to use function calling with an LLM in Python.
# Students will learn how to define functions as tools and execute tool calls.

# Further reading: https://docs.ollama.com/function-calling

# 0. SETUP ###################################

## 0.1 Load Packages #################################

import requests  # for HTTP requests
import json      # for working with JSON

# If you haven't already, install the requests package...
# pip install requests

## 0.2 Configuration #################################

# Select model of interest
# Note: Function calling requires a model that supports tools (e.g., smollm2:1.7b)
MODEL = "smollm2:1.7b"

# Set the port where Ollama is running
PORT = 11434
OLLAMA_HOST = f"http://localhost:{PORT}"
CHAT_URL = f"{OLLAMA_HOST}/api/chat"

# 1. DEFINE A FUNCTION TO BE USED AS A TOOL ###################################

# Define a function to be used as a tool
# This function must be defined in the global scope so it can be called
def inches_to_mm(inches):
    """
    Convert a length in inches to millimeters (1 inch = 25.4 mm).

    Parameters:
    -----------
    inches : float
        Length in inches

    Returns:
    --------
    float
        Equivalent length in millimeters
    """
    return inches * 25.4


# 2. DEFINE TOOL METADATA ###################################

# Define the tool metadata as a dictionary
# This tells the LLM what the function does and what parameters it needs
tool_inches_to_mm = {
    "type": "function",
    "function": {
        "name": "inches_to_mm",
        "description": "Convert a length in inches to millimeters",
        "parameters": {
            "type": "object",
            "required": ["inches"],
            "properties": {
                "inches": {
                    "type": "number",
                    "description": "length in inches",
                }
            },
        },
    },
}

# 3. CREATE CHAT REQUEST WITH TOOLS ###################################

# Create a simple chat history with a user question that will require the tool
messages = [
    {"role": "user", "content": "Convert 4 inches to millimeters"},
]

# Build the request body with tools
body = {
    "model": MODEL,
    "messages": messages,
    "tools": [tool_inches_to_mm],
    "stream": False,
}

# Send the request
response = requests.post(CHAT_URL, json=body)
response.raise_for_status()
result = response.json()

# 4. EXECUTE THE TOOL CALL ###################################

# Receive back the tool call
# The LLM will return a tool_calls array with the function name and arguments
if "tool_calls" in result.get("message", {}):
    tool_calls = result["message"]["tool_calls"]

    # Execute each tool call
    for tool_call in tool_calls:
        func_name = tool_call["function"]["name"]
        raw_args = tool_call["function"].get("arguments", {})
        # Ollama may return tool arguments either as a JSON string or as an already-parsed dict.
        # The R version uses native structured objects, so we mirror that behavior here.
        func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

        # Get the function from globals and execute it
        func = globals().get(func_name)
        if func:
            output = func(**func_args)
            print(f"Tool call result: {output}")
            tool_call["output"] = output
else:
    print("No tool calls in response")
