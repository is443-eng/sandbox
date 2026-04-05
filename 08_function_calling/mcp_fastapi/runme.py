# runme.py
# Run the MCP FastAPI app locally (pairs with mcp_plumber/runme.R)
# Tim Fraser

# From repo root or this folder:
#   python 08_function_calling/mcp_fastapi/runme.py
#   python runme.py
# If port 8000 is busy: PORT=8001 python runme.py  (then MCP_SERVER_URL=http://127.0.0.1:8001/mcp for testme.py)

import os
import sys

import uvicorn

if __name__ == "__main__":
    _here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(_here)
    sys.path.insert(0, _here)
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=True)
