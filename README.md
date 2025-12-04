# TCCT Community

**AI agents in your pocket. Free. Works offline.**

The AI dev companion that works when your laptop doesn't.

---

## Why TCCT?

You already have a full setup at your desk. TCCT isn't here to replace it.

TCCT is for **everywhere else**:
- Think through problems on your commute
- Quick code review before a meeting
- Capture ideas before they disappear
- Works offline - no internet required

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/ETPDEV/tcct-community.git
cd tcct-community
pip install -r requirements.txt

# First run (downloads local model)
./scripts/tcct setup

# Start using
tcct ask "Explain this error"
tcct agent run writer "Draft release notes for v2.0"
tcct agent run debugger "Why would this cause a memory leak?"
```

---

## What You Get (Free)

| Feature | Description |
|---------|-------------|
| **5 AI Agents** | writer, reasoner, planner, debugger, support |
| **Offline AI** | Local Qwen2.5-3B, zero cloud costs |
| **Hybrid Routing** | Auto-switches local/cloud based on task |
| **Persistent Memory** | Remembers context across sessions |
| **CLI Interface** | Fast, scriptable, Unix-friendly |

---

## Available Agents

```bash
tcct agent run writer    "Write a technical blog post"
tcct agent run reasoner  "Analyze this architecture"
tcct agent run planner   "Break this project into tasks"
tcct agent run debugger  "Find the bug in this code"
tcct agent run support   "Help me with this error"
```

---

## Upgrade to Pro

Need more? **TCCT Pro** adds:

- All 24 agents (DevOps, Security, ML, Business, etc.)
- Voice mode (hands-free coding)
- Vision (whiteboard -> notes)
- Hardware bridge (MQTT, BLE, Serial)

| Option | Price |
|--------|-------|
| **Lifetime** | $49 (one-time) |
| **Monthly** | $4.99/mo |
| **Yearly** | $39/yr |

**Early adopter pricing. Get it before it goes up.**

https://etpdev.gumroad.com/tcct-pro

---

## Community

- Issues: https://github.com/ETPDEV/tcct-community/issues
- Discord: https://discord.gg/tcct
- Docs: https://tcct.dev/docs

---

## License

MIT License - Use it however you want.

(c) 2025 Edwards Tech Innovation
