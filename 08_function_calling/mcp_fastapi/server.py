# server.py
# Stateless MCP Server — FastAPI (Python)
# Pairs with mcp_plumber/plumber.R
# Tim Fraser

# What this file is:
#   A FastAPI app that speaks the Model Context Protocol (MCP) over HTTP.
#   It mirrors plumber.R: same tools, same JSON-RPC methods, Streamable HTTP behavior.
#   Stateless: each POST /mcp is one JSON-RPC request → one JSON response (or 202 for notifications).
#
# How to run locally:
#   uvicorn server:app --port 8000 --reload
#   or: python runme.py
#
# How to deploy:
#   See deployme.py
#
# Packages:
#   pip install -r requirements.txt
#   (Uses requests+certifi for HTTPS CSV fetch so SSL works when the system cert store is incomplete.)

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import io
import json

import certifi
import pandas as pd
import requests

app = FastAPI()

# ── Tool definitions (what the LLM sees) ────────────────────

TOOLS = [
    {
        "name": "summarize_dataset",
        "description": "Returns mean, sd, min, and max for each numeric column in a dataset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_name": {
                    "type": "string",
                    "description": "Dataset to summarize. Options: 'mtcars' or 'iris'.",
                }
            },
            "required": ["dataset_name"],
        },
    },
    {
        "name": "filter_mtcars_by_mpg",
        "description": "Return rows from the mtcars dataset where mpg is between min_mpg and max_mpg (inclusive).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_mpg": {
                    "type": "number",
                    "description": "Minimum mpg (inclusive).",
                },
                "max_mpg": {
                    "type": "number",
                    "description": "Maximum mpg (inclusive). Omit for no upper bound.",
                },
            },
            "required": ["min_mpg"],
        },
    },
]

# ── Tool logic (same datasets as R: mtcars, iris via Rdatasets CSV) ──

_DATASET_URLS = {
    "mtcars": "https://vincentarelbundock.github.io/Rdatasets/csv/datasets/mtcars.csv",
    "iris": "https://vincentarelbundock.github.io/Rdatasets/csv/datasets/iris.csv",
}


def _load_datasets() -> dict:
    """Fetch CSVs over HTTPS using certifi (avoids SSL errors from urllib/pandas on some macOS Python installs)."""
    out = {}
    for name, url in _DATASET_URLS.items():
        r = requests.get(url, timeout=60, verify=certifi.where())
        r.raise_for_status()
        out[name] = pd.read_csv(io.StringIO(r.text))
    return out


DATASETS = _load_datasets()


def run_tool(name: str, args: dict) -> str:
    if name == "summarize_dataset":
        nm = args.get("dataset_name")
        if nm not in DATASETS:
            raise ValueError(f"Unknown dataset: '{nm}' — choose 'mtcars' or 'iris'")

        df = DATASETS[nm].select_dtypes(include="number")
        summary = df.agg(["mean", "std", "min", "max"]).round(2).T
        summary.index.name = "variable"
        summary.columns = ["mean", "sd", "min", "max"]
        return summary.reset_index().to_json(orient="records", indent=2)

    if name == "filter_mtcars_by_mpg":
        df = DATASETS["mtcars"]
        min_mpg = float(args["min_mpg"])
        mask = df["mpg"] >= min_mpg
        if args.get("max_mpg") is not None:
            mask &= df["mpg"] <= float(args["max_mpg"])
        out = df.loc[mask]
        n = len(out)
        preview = out.head(50)
        payload = {
            "row_count": n,
            "rows_preview": json.loads(preview.to_json(orient="records")),
        }
        return json.dumps(payload, indent=2)

    raise ValueError(f"Unknown tool: {name}")


# ── MCP JSON-RPC router ──────────────────────────────────────


@app.post("/mcp")
async def mcp_post(request: Request):
    body = await request.json()

    method = body.get("method")
    id_ = body.get("id")

    if isinstance(method, str) and method.startswith("notifications/"):
        return Response(status_code=202)

    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "py-summarizer", "version": "0.1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            tool_result = run_tool(
                body["params"]["name"],
                body["params"]["arguments"],
            )
            result = {
                "content": [{"type": "text", "text": tool_result}],
                "isError": False,
            }
        else:
            raise ValueError(f"Method not found: {method}")

    except Exception as e:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": str(e)}}
        )

    return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": result})


@app.options("/mcp")
async def mcp_options():
    return Response(
        status_code=204,
        headers={"Allow": "GET, POST, OPTIONS"},
    )


@app.get("/mcp")
async def mcp_get():
    return Response(
        content=json.dumps(
            {"error": "This MCP server uses stateless HTTP. Use POST."}
        ),
        status_code=405,
        headers={"Allow": "GET, POST, OPTIONS"},
        media_type="application/json",
    )
