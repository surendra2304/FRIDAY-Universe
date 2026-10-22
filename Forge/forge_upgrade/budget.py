from __future__ import annotations

from dataclasses import dataclass

from .models import BudgetLedger, TaskBudget


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class BudgetController:
    budget: TaskBudget
    ledger: BudgetLedger = BudgetLedger()

    def reserve_model_call(self, estimated_cost: float = 0.0) -> None:
        next_ledger = BudgetLedger(
            usd_spent=self.ledger.usd_spent + max(0.0, estimated_cost),
            model_calls=self.ledger.model_calls + 1,
            commands=self.ledger.commands,
            runtime_seconds=self.ledger.runtime_seconds,
        )
        if not next_ledger.within(self.budget):
            raise BudgetExceeded("model budget exceeded")
        self.ledger = next_ledger

    def record_command(self, runtime_seconds: float) -> None:
        next_ledger = BudgetLedger(
            usd_spent=self.ledger.usd_spent,
            model_calls=self.ledger.model_calls,
            commands=self.ledger.commands + 1,
            runtime_seconds=self.ledger.runtime_seconds + max(0.0, runtime_seconds),
        )
        if not next_ledger.within(self.budget):
            raise BudgetExceeded("execution budget exceeded")
        self.ledger = next_ledger
