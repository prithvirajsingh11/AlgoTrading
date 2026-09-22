"""
Static AST architectural scanner verifying zero live brokerage execution imports.
Guarantees strict paper-only execution invariant across all backend application modules.
"""

from backend.tests.test_paper_only_invariant import (
    test_no_prohibited_live_trading_imports_in_source,
    test_broker_instantiation_is_strictly_simulated,
    test_order_routing_path_invariant,
)

__all__ = [
    "test_no_prohibited_live_trading_imports_in_source",
    "test_broker_instantiation_is_strictly_simulated",
    "test_order_routing_path_invariant",
]
