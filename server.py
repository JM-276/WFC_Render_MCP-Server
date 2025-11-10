from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from typing import Any, Dict
import random

app = FastAPI(title="Shopfloor MCP Server")

# Allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load tool contract (safe relative path)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_FILE = os.path.join(BASE_DIR, "shopfloor_tool_contract.json")

TOOL_CONTRACT = {}
OPERATIONS = {}

if os.path.exists(TOOLS_FILE):
    try:
        with open(TOOLS_FILE, "r", encoding="utf-8") as f:
            TOOL_CONTRACT = json.load(f)
        OPERATIONS = TOOL_CONTRACT.get("operations", {})
    except Exception as e:
        print(f"[WARN] Could not load tool contract: {e}")
else:
    print(f"[WARN] {TOOLS_FILE} not found — using empty operations list.")


@app.get("/")
def root():
    return {"message": "Shopfloor MCP Server running 🚀", "operations_count": len(OPERATIONS)}


@app.get("/tools/list_operations")
def list_operations():
    """Return a list of available operation names"""
    return {"operations": list(OPERATIONS.keys())}


class ToolRequest(BaseModel):
    operation: str
    inputs: Dict[str, Any] = {}


def cast_input_value(value: Any, type_name: str):
    try:
        if type_name == "number":
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str) and "." in value:
                return float(value)
            return int(value)
        elif type_name == "string":
            return str(value)
        else:
            return value
    except Exception:
        raise ValueError(f"Cannot cast value '{value}' to type '{type_name}'")


def validate_and_cast_inputs(op_schema: Dict, inputs: Dict[str, Any]) -> Dict[str, Any]:
    validated = {}
    for key, val_schema in op_schema.get("inputs", {}).items():
        if val_schema.get("required", False) and key not in inputs:
            raise HTTPException(status_code=400, detail=f"Missing required input: '{key}'")
        if key in inputs:
            try:
                validated[key] = cast_input_value(inputs[key], val_schema["type"])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    return validated


def generate_mock_output(operation: Dict, inputs: Dict[str, Any]) -> Dict:
    outputs_schema = operation.get("outputs", [])
    examples = operation.get("examples", [])

    if examples:
        example = random.choice(examples)
        example_inputs = example.get("inputs", {})
        mock_output = {}
        for out in outputs_schema:
            mock_output[out["name"]] = example_inputs.get(out["name"], f"<{out['type']}>")
        return mock_output
    else:
        return {out["name"]: f"<{out['type']}>" for out in outputs_schema}


@app.post("/tools/run")
def run_tool(request: ToolRequest):
    op = OPERATIONS.get(request.operation)
    if not op:
        raise HTTPException(status_code=404, detail=f"Operation '{request.operation}' not found")

    validated_inputs = validate_and_cast_inputs(op, request.inputs)
    mock_outputs = generate_mock_output(op, validated_inputs)

    return {
        "operation": request.operation,
        "description": op.get("description"),
        "inputs_received": validated_inputs,
        "outputs": mock_outputs
    }


# ✅ Render requires listening on dynamic PORT from environment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[START] Shopfloor MCP Server running on 0.0.0.0:{port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port)
