"""
bujji — Python port of bujji (https://github.com/sipeed/bujji)
Ultra-lightweight AI assistant. Runs on any system with Python 3.7+ and pip.
"""

__version__ = "0.1.0-python"
__author__  = "bujji Contributors"

LOGO = "========================================================"

# Convenience imports so callers can do:
#   from bujji import load_config, AgentLoop
# instead of digging into submodules.
from bujji.config import load_config, save_config, get_active_provider, workspace_path
from bujji.agent  import AgentLoop, HeartbeatService, CronService

__all__ = [
    "LOGO",
    "__version__",
    "load_config",
    "save_config",
    "get_active_provider",
    "workspace_path",
    "AgentLoop",
    "HeartbeatService",
    "CronService",
]