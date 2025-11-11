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
# FastAPI + MCP
# ─────────────────────────────────────────────
app = FastAPI(title="Shopfloor MCP Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp = FastMCP("research")

# Keep track of registered tools
REGISTERED_TOOLS = []

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
# Tools
# ─────────────────────────────────────────────
@mcp.tool()
def list_operations() -> List[str]:
    REGISTERED_TOOLS.append("list_operations")
    if not os.path.exists(TOOL_FILE):
        return ["Tool contract not found."]
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("operations", {}).keys())


@mcp.tool()
def extract_info(operation_id: str) -> str:
    REGISTERED_TOOLS.append("extract_info")
    if not os.path.exists(TOOL_FILE):
        return "Tool contract missing."
    with open(TOOL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    ops = data.get("operations", {})
    return json.dumps(ops.get(operation_id, f"No data for {operation_id}"), indent=2)


@mcp.tool()
def simulate_operation(operation_id: str) -> str:
    REGISTERED_TOOLS.append("simulate_operation")
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
    REGISTERED_TOOLS.append("list_facility_zones")
    return fetch_csv("nodes_facilityzones.csv")


# ─────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(sync_tool_contract())
    print("[READY] MCP server initialized.")
    print(f"[TOOLS REGISTERED] {REGISTERED_TOOLS}")
    yield
    print("[SHUTDOWN] MCP server stopped.")

app.router.lifespan_context = lifespan


# ─────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(sync_tool_contract())
    print(f"[TOOLS REGISTERED] {REGISTERED_TOOLS}")

    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
    else:
        mcp.run()
