#!/usr/bin/env python3
# =========================================================
# Edwards Tech Innovation
# ---------------------------------------------------------
# Business Unit : TCCT
# Project       : TCCT Core v1.0.0
# File          : router.py
# Author        : Andrew 'Dru' Edwards
# Description   : Hybrid intelligent request router with local/cloud model selection
# ---------------------------------------------------------
# Notice        : (c) 2025 Edwards Tech Innovation.
#                 Unauthorized copying, distribution, or use
#                 is prohibited unless explicitly authorized.
# Signature     : ETI-TCCT-3066B98FF896
# =========================================================

"""
TCCT Hybrid Router
Smart routing between local (llama.cpp) and cloud (Claude) models
"""

import os
import re
import json
import time
import asyncio
import subprocess
import httpx
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime

# Configuration
CONFIG_DIR = Path.home() / "tcct" / "config"
MODELS_DIR = Path.home() / "models"
LLAMA_CLI = Path.home() / "llama.cpp" / "build" / "bin" / "llama-cli"

class ModelTier(Enum):
    LOCAL = "local"        # Free, private, offline
    HAIKU = "haiku"        # Cheap, fast
    SONNET = "sonnet"      # Balanced
    OPUS = "opus"          # Best quality

class Complexity(Enum):
    SIMPLE = "simple"      # Route to local
    MEDIUM = "medium"      # Route based on context
    COMPLEX = "complex"    # Route to cloud

class RouteReason(Enum):
    OFFLINE = "offline"
    LOW_BATTERY = "low_battery"
    PRIVACY = "privacy"
    SIMPLE_QUERY = "simple_query"
    COMPLEX_QUERY = "complex_query"
    USER_OVERRIDE = "user_override"
    COST_OPTIMIZATION = "cost_optimization"

@dataclass
class RoutingDecision:
    """Result of routing decision"""
    model_tier: ModelTier
    reason: RouteReason
    confidence: float
    estimated_tokens: int
    estimated_cost: float
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeviceContext:
    """Current device state for routing decisions"""
    is_online: bool = True
    battery_level: int = 100
    is_charging: bool = False
    location: Optional[str] = None
    time_of_day: str = "day"
    wifi_connected: bool = True

class HybridRouter:
    """Smart router for local/cloud model selection"""

    def __init__(self):
        self.local_available = self._check_local_available()
        self.cloud_available = self._check_cloud_available()
        self.device_context = DeviceContext()

        # Model configurations
        self.models = {
            ModelTier.LOCAL: {
                "name": "qwen2.5-3b-instruct",
                "path": MODELS_DIR / "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
                "cost_per_1k": 0.0,
                "speed_tok_s": 4,
                "max_context": 32000,
            },
            ModelTier.HAIKU: {
                "name": "claude-3-5-haiku-20241022",
                "cost_per_1k_input": 0.00025,
                "cost_per_1k_output": 0.00125,
                "speed_tok_s": 100,
                "max_context": 200000,
            },
            ModelTier.SONNET: {
                "name": "claude-sonnet-4-20250514",
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "speed_tok_s": 80,
                "max_context": 200000,
            },
            ModelTier.OPUS: {
                "name": "claude-opus-4-20250514",
                "cost_per_1k_input": 0.015,
                "cost_per_1k_output": 0.075,
                "speed_tok_s": 40,
                "max_context": 200000,
            },
        }

        # PII patterns for privacy detection
        self.pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{16}\b',              # Credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone
            r'\bpassword\s*(?:[:=]|is)\s*\S+',  # Passwords
            r'\b(api[_-]?key|secret|token)\s*[:=]\s*\S+',  # API keys
        ]

        # Complexity indicators
        self.complex_indicators = [
            "debug", "fix", "refactor", "architect", "design",
            "multi-file", "project", "codebase", "analyze",
            "implement", "create a", "build a", "develop",
            "error", "exception", "stack trace", "failing",
        ]

        self.simple_indicators = [
            "what is", "define", "explain", "syntax",
            "how to", "example of", "difference between",
            "yes or no", "true or false", "list",
        ]

    def _check_local_available(self) -> bool:
        """Check if local model is available"""
        model_path = MODELS_DIR / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
        return LLAMA_CLI.exists() and model_path.exists()

    def _check_cloud_available(self) -> bool:
        """Check if cloud API is available"""
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    async def update_device_context(self) -> DeviceContext:
        """Update device context from Termux APIs"""
        ctx = DeviceContext()

        # Check connectivity
        try:
            proc = await asyncio.create_subprocess_shell(
                "ping -c 1 -W 2 api.anthropic.com",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            ctx.is_online = proc.returncode == 0
        except:
            ctx.is_online = False

        # Check battery (if termux-api available)
        try:
            proc = await asyncio.create_subprocess_shell(
                "termux-battery-status 2>/dev/null",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await proc.communicate()
            if stdout:
                battery = json.loads(stdout.decode())
                ctx.battery_level = battery.get("percentage", 100)
                ctx.is_charging = battery.get("status") == "CHARGING"
        except:
            pass

        # Time of day
        hour = datetime.now().hour
        if 6 <= hour < 12:
            ctx.time_of_day = "morning"
        elif 12 <= hour < 18:
            ctx.time_of_day = "afternoon"
        elif 18 <= hour < 22:
            ctx.time_of_day = "evening"
        else:
            ctx.time_of_day = "night"

        self.device_context = ctx
        return ctx

    def detect_pii(self, text: str) -> bool:
        """Detect if text contains PII that shouldn't be sent to cloud"""
        for pattern in self.pii_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def classify_complexity(self, query: str) -> Tuple[Complexity, float]:
        """Classify query complexity"""
        query_lower = query.lower()

        # Count indicators
        complex_count = sum(1 for ind in self.complex_indicators if ind in query_lower)
        simple_count = sum(1 for ind in self.simple_indicators if ind in query_lower)

        # Length factor
        word_count = len(query.split())

        # Code presence
        has_code = "```" in query or "def " in query or "function " in query

        # Calculate score
        score = 0.5  # Start neutral

        # Indicator weights
        score += complex_count * 0.15
        score -= simple_count * 0.15

        # Length weight
        if word_count > 100:
            score += 0.2
        elif word_count < 20:
            score -= 0.1

        # Code weight
        if has_code:
            score += 0.1

        # Clamp and classify
        score = max(0.0, min(1.0, score))

        if score < 0.35:
            return Complexity.SIMPLE, 1.0 - score
        elif score < 0.65:
            return Complexity.MEDIUM, 0.5
        else:
            return Complexity.COMPLEX, score

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token average)"""
        return len(text) // 4 + 100  # Add buffer for response

    def estimate_cost(self, tier: ModelTier, input_tokens: int, output_tokens: int = 500) -> float:
        """Estimate API cost"""
        if tier == ModelTier.LOCAL:
            return 0.0

        model = self.models[tier]
        input_cost = (input_tokens / 1000) * model.get("cost_per_1k_input", 0)
        output_cost = (output_tokens / 1000) * model.get("cost_per_1k_output", 0)
        return input_cost + output_cost

    async def route(
        self,
        query: str,
        force_local: bool = False,
        force_cloud: bool = False,
        prefer_quality: bool = False,
        prefer_speed: bool = False,
    ) -> RoutingDecision:
        """Make routing decision for a query"""

        # Update device context
        await self.update_device_context()
        ctx = self.device_context

        # Force overrides
        if force_local:
            return RoutingDecision(
                model_tier=ModelTier.LOCAL,
                reason=RouteReason.USER_OVERRIDE,
                confidence=1.0,
                estimated_tokens=self.estimate_tokens(query),
                estimated_cost=0.0,
                context={"forced": "local"}
            )

        if force_cloud:
            tier = ModelTier.OPUS if prefer_quality else ModelTier.SONNET
            tokens = self.estimate_tokens(query)
            return RoutingDecision(
                model_tier=tier,
                reason=RouteReason.USER_OVERRIDE,
                confidence=1.0,
                estimated_tokens=tokens,
                estimated_cost=self.estimate_cost(tier, tokens),
                context={"forced": "cloud"}
            )

        # Check privacy (PII detection)
        if self.detect_pii(query):
            return RoutingDecision(
                model_tier=ModelTier.LOCAL,
                reason=RouteReason.PRIVACY,
                confidence=0.95,
                estimated_tokens=self.estimate_tokens(query),
                estimated_cost=0.0,
                context={"pii_detected": True}
            )

        # Check connectivity
        if not ctx.is_online or not self.cloud_available:
            return RoutingDecision(
                model_tier=ModelTier.LOCAL,
                reason=RouteReason.OFFLINE,
                confidence=1.0,
                estimated_tokens=self.estimate_tokens(query),
                estimated_cost=0.0,
                context={"online": ctx.is_online, "cloud_available": self.cloud_available}
            )

        # Check battery
        if ctx.battery_level < 20 and not ctx.is_charging:
            return RoutingDecision(
                model_tier=ModelTier.LOCAL,
                reason=RouteReason.LOW_BATTERY,
                confidence=0.9,
                estimated_tokens=self.estimate_tokens(query),
                estimated_cost=0.0,
                context={"battery": ctx.battery_level}
            )

        # Classify complexity
        complexity, confidence = self.classify_complexity(query)
        tokens = self.estimate_tokens(query)

        if complexity == Complexity.SIMPLE:
            return RoutingDecision(
                model_tier=ModelTier.LOCAL,
                reason=RouteReason.SIMPLE_QUERY,
                confidence=confidence,
                estimated_tokens=tokens,
                estimated_cost=0.0,
                context={"complexity": "simple"}
            )

        if complexity == Complexity.COMPLEX:
            tier = ModelTier.SONNET
            if prefer_quality:
                tier = ModelTier.OPUS
            elif prefer_speed:
                tier = ModelTier.HAIKU

            return RoutingDecision(
                model_tier=tier,
                reason=RouteReason.COMPLEX_QUERY,
                confidence=confidence,
                estimated_tokens=tokens,
                estimated_cost=self.estimate_cost(tier, tokens),
                context={"complexity": "complex"}
            )

        # Medium complexity - use cost optimization
        # Default to Haiku for balance of speed/cost/quality
        tier = ModelTier.HAIKU
        if prefer_quality:
            tier = ModelTier.SONNET

        return RoutingDecision(
            model_tier=tier,
            reason=RouteReason.COST_OPTIMIZATION,
            confidence=confidence,
            estimated_tokens=tokens,
            estimated_cost=self.estimate_cost(tier, tokens),
            context={"complexity": "medium", "optimized_for": "cost"}
        )

    async def call_local(self, query: str, system_prompt: str = "") -> Tuple[str, int]:
        """Call local model via llama.cpp"""
        if not self.local_available:
            raise RuntimeError("Local model not available")

        model_path = self.models[ModelTier.LOCAL]["path"]

        # Build prompt (ChatML format for Qwen)
        if system_prompt:
            prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n"
        else:
            prompt = f"<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n"

        cmd = [
            str(LLAMA_CLI),
            "-m", str(model_path),
            "-p", prompt,
            "-n", "512",
            "--temp", "0.7",
            "-ngl", "0",
            "--no-display-prompt",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            response = stdout.decode().strip()
            # Clean up response
            if "<|im_end|>" in response:
                response = response.split("<|im_end|>")[0]

            tokens = len(response) // 4
            return response, tokens

        except asyncio.TimeoutError:
            raise RuntimeError("Local model timed out")
        except Exception as e:
            raise RuntimeError(f"Local model error: {e}")

    async def call_cloud(
        self,
        query: str,
        system_prompt: str = "",
        tier: ModelTier = ModelTier.SONNET
    ) -> Tuple[str, int]:
        """Call Claude API"""
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)
        model = self.models[tier]["name"]

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt if system_prompt else "You are a helpful assistant.",
            messages=[{"role": "user", "content": query}]
        )

        text = response.content[0].text if response.content else ""
        tokens = response.usage.input_tokens + response.usage.output_tokens

        return text, tokens

    async def execute(
        self,
        query: str,
        system_prompt: str = "",
        **routing_kwargs
    ) -> Dict[str, Any]:
        """Route and execute query"""

        # Make routing decision
        decision = await self.route(query, **routing_kwargs)

        # Execute
        start_time = time.time()

        try:
            if decision.model_tier == ModelTier.LOCAL:
                response, tokens = await self.call_local(query, system_prompt)
            else:
                response, tokens = await self.call_cloud(query, system_prompt, decision.model_tier)

            elapsed = time.time() - start_time

            return {
                "status": "success",
                "response": response,
                "tokens": tokens,
                "model": decision.model_tier.value,
                "reason": decision.reason.value,
                "confidence": decision.confidence,
                "elapsed_seconds": elapsed,
                "estimated_cost": decision.estimated_cost,
                "context": decision.context,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": decision.model_tier.value,
                "reason": decision.reason.value,
            }


# CLI interface
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="TCCT Hybrid Router")
    parser.add_argument("query", nargs="?", help="Query to process")
    parser.add_argument("--local", action="store_true", help="Force local model")
    parser.add_argument("--cloud", action="store_true", help="Force cloud model")
    parser.add_argument("--quality", action="store_true", help="Prefer quality over speed")
    parser.add_argument("--speed", action="store_true", help="Prefer speed over quality")
    parser.add_argument("--system", "-s", default="", help="System prompt")
    parser.add_argument("--analyze", action="store_true", help="Only show routing decision, don't execute")

    args = parser.parse_args()

    if not args.query:
        print("Usage: python router.py 'your query here'")
        print("       python router.py --analyze 'query'  # Show routing decision only")
        return

    router = HybridRouter()

    if args.analyze:
        decision = await router.route(
            args.query,
            force_local=args.local,
            force_cloud=args.cloud,
            prefer_quality=args.quality,
            prefer_speed=args.speed,
        )
        print(f"Model: {decision.model_tier.value}")
        print(f"Reason: {decision.reason.value}")
        print(f"Confidence: {decision.confidence:.2f}")
        print(f"Est. Tokens: {decision.estimated_tokens}")
        print(f"Est. Cost: ${decision.estimated_cost:.4f}")
        print(f"Context: {json.dumps(decision.context, indent=2)}")
    else:
        result = await router.execute(
            args.query,
            system_prompt=args.system,
            force_local=args.local,
            force_cloud=args.cloud,
            prefer_quality=args.quality,
            prefer_speed=args.speed,
        )

        if result["status"] == "success":
            print(result["response"])
            print(f"\n---")
            print(f"Model: {result['model']} | Reason: {result['reason']} | Tokens: {result['tokens']} | Time: {result['elapsed_seconds']:.1f}s")
        else:
            print(f"Error: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())
