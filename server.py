import os
import json
import requests
import csv
from io import StringIO
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

# ─────────────────────────────────────────────
# Configurable URLs and Directories
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
# FastAPI app for Render deployment
# ─────────────────────────────────────────────
app = FastAPI(title="Shopfloor MCP Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Initialize MCP server
# ─────────────────────────────────────────────
mcp = FastMCP("research")


# ─────────────────────────────────────────────
# GitHub sync helpers
# ─────────────────────────────────────────────
def sync_tool_contract() -> str:
    os.makedirs(TOOL_DIR, exist_ok=True)
    try:
        response = requests.get(RAW_JSON_URL)
        response.raise_for_status()
        with open(TOOL_FILE, "w", encoding="utf-8") as f:
            f.write(response.text)
        return f"[SYNC] Tool contract synced from GitHub ({len(response.text)} bytes)"
    except Exception as e:
        return f"[SYNC ERROR] Could not fetch tool contract: {e}"


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
# MCP tools
# ─────────────────────────────────────────────
@mcp.tool()
def list_operations() -> List[str]:
    """List all operation IDs from tool contract."""
    if not os.path.exists(TOOL_FILE):
        return ["Tool contract not found."]
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("operations", {}).keys())


@mcp.tool()
def extract_info(operation_id: str) -> str:
    """Extract details of a given operation."""
    if not os.path.exists(TOOL_FILE):
        return "Tool contract missing."
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    ops = data.get("operations", {})
    return json.dumps(ops.get(operation_id, f"No data for {operation_id}"), indent=2)


@mcp.tool()
def simulate_operation(operation_id: str) -> str:
    """Simulate an operation with mock input/output."""
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
        "mock_inputs": {k: f"<{v.get('type', 'unknown')}>" for k, v in op.get("inputs", {}).items()},
        "mock_outputs": {o["name"]: f"<{o['type']}>" for o in op.get("outputs", [])}
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def list_facility_zones() -> List[dict]:
    """Load facility zones from GitHub CSV."""
    return fetch_csv("nodes_facilityzones.csv")


# ─────────────────────────────────────────────
# Startup Hook
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print(sync_tool_contract())
    print("[READY] MCP server initialized.")


# ─────────────────────────────────────────────
# MCP Transport (Render-safe)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(sync_tool_contract())
    mcp.run()  # Start the MCP JSON-RPC server


