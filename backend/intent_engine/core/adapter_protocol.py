"""Protocol definition for domain adapters."""

from typing import Any, Dict, Protocol, runtime_checkable

from intent_engine.schemas import Domain, Item, MultiplierSet


@runtime_checkable
class DomainAdapter(Protocol):
    """Interface that every domain adapter must implement.

    Each adapter translates domain-specific vocabulary into the shared
    multiplier-based scoring model used by DomainRankingEngine.
    """

    @property
    def domain(self) -> Domain:
        """The domain this adapter handles."""
        ...

    def resolve_intent(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw intent signals into a canonical intent dict.

        Args:
            raw_input: Domain-specific intent signals from the request.

        Returns:
            Canonical intent dict consumed by compute_multipliers.
        """
        ...

    def compute_multipliers(
        self, item: Item, intent: Dict[str, Any]
    ) -> MultiplierSet:
        """Compute per-signal multipliers for a single item.

        Args:
            item: The candidate item (attributes carry domain metadata).
            intent: Canonical intent dict from resolve_intent.

        Returns:
            MultiplierSet with context, profile, urgency, cost, prophecy.
        """
        ...

    def apply_hard_constraints(
        self, item: Item, constraints: Dict[str, Any]
    ) -> bool:
        """Check whether a hard constraint blocks this item.

        Args:
            item: The candidate item.
            constraints: Hard constraint dict from the request.

        Returns:
            True if the item is **blocked**, False if it passes.
        """
        ...

    def explain(self, item: Item, multipliers: MultiplierSet) -> str:
        """Generate a human-readable explanation for the item's score.

        Args:
            item: The candidate item.
            multipliers: The computed multipliers.

        Returns:
            Single-sentence explanation string.
        """
        ...

    def diversity_key(self, item: Item) -> str:
        """Return the grouping key used for diversity penalties.

        Items sharing the same key receive incremental penalties when
        they appear consecutively in the ranked list.

        Args:
            item: The candidate item.

        Returns:
            Grouping key string (e.g. genre, ride_type, cuisine_type).
        """
        ...
