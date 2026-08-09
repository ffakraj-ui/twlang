"""
tw/state — Global Reactive State Management for TW Framework.

Provides first-class reactive stores with:
- Global stores (store())
- Reactive subscriptions
- Derived state
- Component subscriptions
- Actions/mutations
- State updates (set, update)
- Server/client state separation
- Optional persistence
- Cleanup/unsubscription

Pages that don't use tw/state receive zero state runtime JS.
"""

from .store import Store, derived, create_store
from .runtime import get_state_runtime_js, generate_state_init_script

__all__ = ["Store", "derived", "create_store", "get_state_runtime_js", "generate_state_init_script"]
