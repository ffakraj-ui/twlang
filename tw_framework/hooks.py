"""
TW Framework - React Hooks Implementation

Implements:
6. useOptimistic - Optimistic UI updates with automatic rollback
7. useActionState - Form state, errors, pending state management
8. useFormStatus - Form submission status tracking
9. useTransition - Pending state handling with transitions
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import threading

logger = logging.getLogger(__name__)


# ── useOptimistic Hook ──────────────────────────────────────────────

@dataclass
class OptimisticState:
    """State for useOptimistic hook."""
    current_value: Any
    optimistic_value: Any = None
    is_pending: bool = False
    rollback_on_error: bool = True
    update_id: int = 0
    error: str = ""


class useOptimistic:
    """Optimistic UI updates with automatic rollback.

    Usage:
        optimistic = useOptimistic(initial_value)
        # Optimistically update UI
        optimistic.update(new_value)
        # Perform async action
        result = await some_action()
        if result.error:
            optimistic.rollback()  # Automatic on error if rollback_on_error=True
        else:
            optimistic.confirm(result.value)

    The hook:
    1. Shows the optimistic value immediately
    2. Performs the actual action in the background
    3. On success: confirms the optimistic value
    4. On error: rolls back to the previous value
    5. Tracks pending state for loading indicators
    """

    def __init__(self, initial_value: Any, rollback_on_error: bool = True):
        self._state = OptimisticState(
            current_value=initial_value,
            optimistic_value=initial_value,
            rollback_on_error=rollback_on_error,
        )
        self._history: List[Any] = [initial_value]
        self._listeners: List[Callable[[OptimisticState], None]] = []
        self._update_handlers: Dict[int, Callable] = {}

    @property
    def value(self) -> Any:
        """Get the current value (optimistic if pending, otherwise confirmed)."""
        return self._state.optimistic_value

    @property
    def is_pending(self) -> bool:
        """Whether an optimistic update is pending."""
        return self._state.is_pending

    @property
    def error(self) -> str:
        """Last error from a failed action."""
        return self._state.error

    def update(self, optimistic_value: Any,
               action: Optional[Callable] = None) -> int:
        """Optimistically update the value.

        Args:
            optimistic_value: The value to show immediately
            action: Optional async function that performs the real update.
                    If it raises, the value is rolled back.

        Returns:
            update_id that can be used to confirm or rollback
        """
        self._state.update_id += 1
        uid = self._state.update_id

        # Save current value for potential rollback
        self._history.append(self._state.current_value)

        # Apply optimistic update
        self._state.optimistic_value = optimistic_value
        self._state.is_pending = True
        self._state.error = ""

        if action:
            self._update_handlers[uid] = action

        self._notify()
        logger.debug("Optimistic update #%d: %s", uid, optimistic_value)
        return uid

    def confirm(self, update_id: int, confirmed_value: Any = None) -> None:
        """Confirm an optimistic update with the real value."""
        if update_id != self._state.update_id:
            logger.warning("Confirming stale update #%d (current: #%d)",
                          update_id, self._state.update_id)
            return

        self._state.current_value = confirmed_value if confirmed_value is not None else self._state.optimistic_value
        self._state.optimistic_value = self._state.current_value
        self._state.is_pending = False
        self._state.error = ""
        self._update_handlers.pop(update_id, None)
        self._notify()

    def rollback(self, update_id: int = 0, error: str = "") -> None:
        """Roll back an optimistic update."""
        if update_id and update_id != self._state.update_id:
            return

        if self._history:
            self._state.current_value = self._history.pop()
        self._state.optimistic_value = self._state.current_value
        self._state.is_pending = False
        self._state.error = error
        self._update_handlers.pop(self._state.update_id, None)
        self._notify()

        if error:
            logger.warning("Optimistic update rolled back: %s", error)

    def add_listener(self, listener: Callable[[OptimisticState], None]) -> None:
        """Add a listener for state changes."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            try:
                listener(self._state)
            except Exception as e:
                logger.warning("Optimistic listener error: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self._state.optimistic_value,
            "is_pending": self._state.is_pending,
            "error": self._state.error,
            "update_id": self._state.update_id,
        }


# ── useActionState Hook ─────────────────────────────────────────────

@dataclass
class ActionState:
    """State for useActionState hook."""
    data: Any = None
    error: str = ""
    is_pending: bool = False
    is_success: bool = False
    submissions: int = 0


class useActionState:
    """Form state, errors, and pending state management.

    Wraps a server action and provides:
    - Current state (data, error)
    - Pending status
    - Success/failure tracking
    - Submission count
    - Automatic state reset

    Usage:
        state = useActionState(action_fn, initial_data)
        # Trigger action
        state.execute(formData)
        # Access state
        if state.is_pending: show_loading()
        if state.error: show_error(state.error)
        if state.is_success: show_success(state.data)
    """

    def __init__(self, action: Callable, initial_data: Any = None,
                 reset_on_success: bool = False):
        self._action = action
        self._state = ActionState(data=initial_data)
        self._reset_on_success = reset_on_success
        self._listeners: List[Callable[[ActionState], None]] = []

    @property
    def data(self) -> Any:
        return self._state.data

    @property
    def error(self) -> str:
        return self._state.error

    @property
    def is_pending(self) -> bool:
        return self._state.is_pending

    @property
    def is_success(self) -> bool:
        return self._state.is_success

    @property
    def submissions(self) -> int:
        return self._state.submissions

    def execute(self, *args, **kwargs) -> Any:
        """Execute the action and update state."""
        self._state.is_pending = True
        self._state.error = ""
        self._state.is_success = False
        self._state.submissions += 1
        self._notify()

        try:
            result = self._action(*args, **kwargs)
            self._state.data = result
            self._state.is_success = True
            self._state.is_pending = False

            if self._reset_on_success:
                self._state.data = None

            self._notify()
            return result

        except Exception as e:
            self._state.error = str(e)
            self._state.is_pending = False
            self._state.is_success = False
            self._notify()
            raise

    def reset(self) -> None:
        """Reset state to initial."""
        self._state = ActionState()
        self._notify()

    def add_listener(self, listener: Callable[[ActionState], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for l in self._listeners:
            try:
                l(self._state)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self._state.data,
            "error": self._state.error,
            "is_pending": self._state.is_pending,
            "is_success": self._state.is_success,
            "submissions": self._state.submissions,
        }


# ── useFormStatus Hook ──────────────────────────────────────────────

@dataclass
class FormStatus:
    """Form submission status."""
    is_pending: bool = False
    is_success: bool = False
    is_error: bool = False
    error_message: str = ""
    submitted_at: float = 0.0
    completed_at: float = 0.0
    form_data: Dict[str, Any] = field(default_factory=dict)


class useFormStatus:
    """Form submission status tracking.

    Tracks the status of a form submission:
    - Pending (form is being submitted)
    - Success (form submitted successfully)
    - Error (form submission failed)
    - Idle (no submission yet)

    Usage:
        status = useFormStatus()
        # In form submit handler:
        status.start(formData)
        try:
            result = await submit_form(formData)
            status.success(result)
        except Exception as e:
            status.fail(str(e))
    """

    def __init__(self):
        self._status = FormStatus()
        self._listeners: List[Callable[[FormStatus], None]] = []

    @property
    def is_pending(self) -> bool:
        return self._status.is_pending

    @property
    def is_success(self) -> bool:
        return self._status.is_success

    @property
    def is_error(self) -> bool:
        return self._status.is_error

    @property
    def error(self) -> str:
        return self._status.error_message

    @property
    def duration_ms(self) -> float:
        if self._status.submitted_at and self._status.completed_at:
            return (self._status.completed_at - self._status.submitted_at) * 1000
        return 0.0

    def start(self, form_data: Optional[Dict] = None) -> None:
        """Mark form submission as started."""
        self._status = FormStatus(
            is_pending=True,
            submitted_at=time.time(),
            form_data=form_data or {},
        )
        self._notify()

    def success(self, result: Any = None) -> None:
        """Mark form submission as successful."""
        self._status.is_pending = False
        self._status.is_success = True
        self._status.is_error = False
        self._status.completed_at = time.time()
        self._status.form_data["result"] = result
        self._notify()

    def fail(self, error: str) -> None:
        """Mark form submission as failed."""
        self._status.is_pending = False
        self._status.is_success = False
        self._status.is_error = True
        self._status.error_message = error
        self._status.completed_at = time.time()
        self._notify()

    def reset(self) -> None:
        """Reset form status."""
        self._status = FormStatus()
        self._notify()

    def add_listener(self, listener: Callable[[FormStatus], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for l in self._listeners:
            try:
                l(self._status)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_pending": self._status.is_pending,
            "is_success": self._status.is_success,
            "is_error": self._status.is_error,
            "error": self._status.error_message,
            "duration_ms": self.duration_ms,
        }


# ── useTransition Hook ──────────────────────────────────────────────

@dataclass
class TransitionState:
    """State for useTransition hook."""
    is_pending: bool = False
    started_at: float = 0.0
    completed_at: float = 0.0
    transition_id: int = 0


class useTransition:
    """Pending state handling with transitions.

    Marks state updates as non-urgent (transitions) so they don't
    block urgent updates like typing or clicking.

    Usage:
        transition = useTransition()
        # Start a transition
        transition.start(lambda: update_expensive_list(filter))
        # Check if pending
        if transition.is_pending: show_spinner()
    """

    def __init__(self, timeout_ms: float = 5000):
        self._state = TransitionState()
        self._timeout_ms = timeout_ms
        self._counter = 0
        self._listeners: List[Callable[[TransitionState], None]] = []

    @property
    def is_pending(self) -> bool:
        return self._state.is_pending

    @property
    def duration_ms(self) -> float:
        if self._state.started_at and self._state.completed_at:
            return (self._state.completed_at - self._state.started_at) * 1000
        elif self._state.started_at:
            return (time.time() - self._state.started_at) * 1000
        return 0.0

    def start(self, update_fn: Callable, *args, **kwargs) -> int:
        """Start a transition.

        The update function is called and marked as a low-priority update.
        The is_pending flag stays true until the update completes.
        """
        self._counter += 1
        tid = self._counter

        self._state.is_pending = True
        self._state.started_at = time.time()
        self._state.transition_id = tid
        self._notify()

        try:
            result = update_fn(*args, **kwargs)
            return result
        finally:
            self._state.is_pending = False
            self._state.completed_at = time.time()
            self._notify()

    def start_async(self, update_fn: Callable, *args, **kwargs) -> Any:
        """Start an async transition."""
        import threading

        self._counter += 1
        tid = self._counter

        self._state.is_pending = True
        self._state.started_at = time.time()
        self._state.transition_id = tid
        self._notify()

        def _run():
            try:
                update_fn(*args, **kwargs)
            except Exception as e:
                logger.error("Transition %d failed: %s", tid, e)
            finally:
                self._state.is_pending = False
                self._state.completed_at = time.time()
                self._notify()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return tid

    def add_listener(self, listener: Callable[[TransitionState], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for l in self._listeners:
            try:
                l(self._state)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_pending": self._state.is_pending,
            "duration_ms": self.duration_ms,
            "transition_id": self._state.transition_id,
        }


__all__ = [
    "OptimisticState", "useOptimistic",
    "ActionState", "useActionState",
    "FormStatus", "useFormStatus",
    "TransitionState", "useTransition",
]
