import pytest

from forge_upgrade.budget import BudgetController, BudgetExceeded
from forge_upgrade.models import TaskBudget


def test_budget():
    b = BudgetController(TaskBudget(max_usd=1, max_model_calls=1))
    b.reserve_model_call(0.5)
    with pytest.raises(BudgetExceeded):
        b.reserve_model_call(0.6)
