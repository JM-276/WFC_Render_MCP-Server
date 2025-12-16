import os
import json
import requests
import csv
from io import StringIO
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from contextlib import asynccontextmanager

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
TOOL_DIR = "tools"
TOOL_FILE = os.path.join(TOOL_DIR, "shopfloor_tool_contract.json")

RAW_JSON_URL = os.getenv(
    "TOOL_CONTRACT_URL",
    "https://raw.githubusercontent.com/JM-276/WFC_AI_Integration/main/shopfloor_tool_contract.json"
)

DATA_BASE_URL = os.getenv(
    "DATA_BASE_URL",
    "https://raw.githubusercontent.com/JM-276/WFC_AI_Integration/main/data/"
)

# ─────────────────────────────────────────────
# FastAPI + MCP
# ─────────────────────────────────────────────
app = FastAPI(title="Water Plant MCP Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp = FastMCP("waterplant")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def sync_tool_contract() -> str:
    os.makedirs(TOOL_DIR, exist_ok=True)
    try:
        response = requests.get(RAW_JSON_URL)
        response.raise_for_status()
        with open(TOOL_FILE, "w", encoding="utf-8") as f:
            f.write(response.text)
        return f"[SYNC] Water plant tool contract synced ({len(response.text)} bytes)"
    except Exception as e:
        return f"[SYNC ERROR] Failed to fetch tool contract: {e}"

def fetch_csv(file_name: str) -> List[dict]:
    url = DATA_BASE_URL + file_name
    try:
        response = requests.get(url)
        response.raise_for_status()
        reader = csv.DictReader(StringIO(response.text))
        return [row for row in reader]
    except Exception as e:
        print(f"[CSV ERROR] {file_name}: {e}")
        return []

# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────
@mcp.tool()
def list_operations() -> List[str]:
    if not os.path.exists(TOOL_FILE):
        return ["Tool contract not found."]
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("operations", {}).keys())

@mcp.tool()
def extract_info(operation_id: str) -> str:
    if not os.path.exists(TOOL_FILE):
        return "Tool contract missing."
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    ops = data.get("operations", {})
    return json.dumps(ops.get(operation_id, f"No data for {operation_id}"), indent=2)

@mcp.tool()
def simulate_operation(operation_id: str) -> str:
    if not os.path.exists(TOOL_FILE):
        return "Tool contract not found."
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    ops = data.get("operations", {})
    if operation_id not in ops:
        return f"No such operation: {operation_id}"

    op = ops[operation_id]
    result = {
        "operation_id": operation_id,
        "description": op.get("description", ""),
        "cypher": op.get("cypher", ""),
        "mock_inputs": {
            k: f"<{v.get('type', 'unknown')}>"
            for k, v in op.get("inputs", {}).items()
        },
        "mock_outputs": {
            o["name"]: f"<{o['type']}>"
            for o in op.get("outputs", [])
        }
    }
    return json.dumps(result, indent=2)

@mcp.tool()
def list_plant_zones() -> List[dict]:
    return fetch_csv("nodes_plantzones.csv")

# ─────────────────────────────────────────────
# OpenAI-compatible function schema
# ─────────────────────────────────────────────
OPENAI_FUNCTIONS = [
    {
        "name": "list_operations",
        "description": "List all water plant graph operation IDs",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "extract_info",
        "description": "Extract details of a water plant graph operation",
        "parameters": {
            "type": "object",
            "properties": {
                "operation_id": {"type": "string"}
            }
        },
    },
    {
        "name": "simulate_operation",
        "description": "Simulate a water plant operation with mock input/output",
        "parameters": {
            "type": "object",
            "properties": {
                "operation_id": {"type": "string"}
            }
        },
    },
    {
        "name": "list_plant_zones",
        "description": "List all water plant zones from CSV",
        "parameters": {"type": "object", "properties": {}},
    }
]

@app.get("/openai_functions")
def get_openai_functions():
    return OPENAI_FUNCTIONS

# ─────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(sync_tool_contract())
    print("[READY] Water Plant MCP server initialized.")
    yield
    print("[SHUTDOWN] Water Plant MCP server stopped.")

app.router.lifespan_context = lifespan

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(sync_tool_contract())
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
