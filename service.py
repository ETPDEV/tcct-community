#!/usr/bin/env python3
"""
TCCT Community Edition - Local-Only Agent Service
(c) 2025 Edwards Tech Innovation
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.getenv("TCCT_PORT", "8080"))
AGENTS_DIR = Path(__file__).parent / "agents"
MODEL_PATH = Path.home() / "models" / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
LLAMA_CLI = Path.home() / "llama.cpp" / "build" / "bin" / "llama-cli"

def load_agents():
    """Load available agents."""
    agents = {}
    for f in AGENTS_DIR.glob("*.agent.yaml"):
        name = f.stem.replace(".agent", "")
        agents[name] = {"name": name, "file": str(f)}
    return agents

AGENTS = load_agents()

class TCCTHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_json({"status": "ok", "edition": "community", "agents": len(AGENTS)})
        elif self.path == "/agents":
            self.send_json({"agents": list(AGENTS.keys()), "count": len(AGENTS)})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/invoke":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            agent = data.get("agent")
            message = data.get("message", "")

            if agent not in AGENTS:
                self.send_json({"error": f"Agent {agent} not found"}, 404)
                return

            # Call local model
            response = call_local(agent, message)
            self.send_json({"response": response, "agent": agent, "model": "local"})
        else:
            self.send_error(404)

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass  # Suppress logging

def call_local(agent: str, message: str) -> str:
    """Call local LLM."""
    if not MODEL_PATH.exists():
        return "Error: Local model not found. Run: tcct setup"
    if not LLAMA_CLI.exists():
        return "Error: llama.cpp not found. Run: tcct setup"

    prompt = f"You are a helpful AI assistant. {message}"

    cmd = [
        str(LLAMA_CLI),
        "-m", str(MODEL_PATH),
        "-p", prompt,
        "-n", "512",
        "--temp", "0.7",
        "-ngl", "0"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    print(f"TCCT Community Edition v{VERSION}")
    print(f"Starting on port {PORT}...")
    print(f"Agents: {len(AGENTS)}")

    server = HTTPServer(("0.0.0.0", PORT), TCCTHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")

VERSION = "1.0.0"

if __name__ == "__main__":
    main()
