"""
DataSource — the most important abstraction in the codebase.

Defined in Phase 1, implemented in Phase 2 (SyntheticSource) and Phase 6
(EtherscanSource). The graph, risk, dilution, timeline and report engines must
NEVER know which implementation is active. That is what lets a judge hand us a
real mainnet address mid-demo without a single engine changing.

Owner: BE1
"""

from abc import ABC, abstractmethod

from ..models import Edge, Label


class DataSource(ABC):
    """A provider of transaction data for one case."""

    @abstractmethod
    def get_transactions(self, address: str, limit: int = 100) -> list[Edge]:
        """Inbound and outbound transfers for `address`.

        CRITICAL — the live implementation MUST merge BOTH Etherscan endpoints:

            account/txlist    native ETH transfers
            account/tokentx   ERC-20 transfers

        Indian crypto-fraud proceeds move as USDT, not native ETH. An
        implementation that queries only `txlist` returns almost nothing on a
        real scam wallet, and live mode will appear broken on stage. This single
        detail decides whether live tracing works.
        """

    @abstractmethod
    def get_balance(self, address: str) -> float:
        """Current holdings. Feeds `prior_balance` in the dilution haircut."""

    @abstractmethod
    def get_label(self, address: str) -> Label | None:
        """Resolve an attribution label.

        Consult the curated known_addresses.json first, then the provider.
        Return None when unknown — never guess. Address attribution at scale is
        a commercial product we are not reproducing, and an invented label in a
        court dossier is far worse than an absent one.
        """

    @abstractmethod
    def source_name(self) -> str:
        """Reported in GraphStats.source and printed in the dossier."""

    @abstractmethod
    def is_live(self) -> bool:
        """True for real-network sources. Drives the UI mode banner."""
