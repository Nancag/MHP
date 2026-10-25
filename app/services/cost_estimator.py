"""Seller-entered estimates in CNY; no exchange rates or statutory tax defaults."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CostInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    purchase: Decimal = Field(ge=0, le=10**9, max_digits=16, decimal_places=6)
    package_weight_g: Decimal = Field(gt=0, le=10**8, max_digits=16, decimal_places=6)
    freight_per_g: Decimal = Field(ge=0, le=10**6, max_digits=16, decimal_places=6)
    customs_percent: Decimal = Field(ge=0, le=1000, max_digits=10, decimal_places=6)
    commission_percent: Decimal = Field(ge=0, lt=50, max_digits=10, decimal_places=6)
    loss_percent: Decimal = Field(ge=0, lt=100, max_digits=10, decimal_places=6)
    customs_base: Literal['purchase', 'purchase_freight']


def estimate(value: CostInput):
    with localcontext() as ctx:
        ctx.prec = 48
        freight = value.package_weight_g * value.freight_per_g
        tax_base = value.purchase + (freight if value.customs_base == 'purchase_freight' else 0)
        tax = tax_base * value.customs_percent / 100
        base = value.purchase + freight + tax
        loss_base = base / (1 - value.loss_percent / 100)
        cost = loss_base / (1 - 2 * value.commission_percent / 100)
        # Round cost first, so the displayed sale price is exactly twice displayed cost.
        money = lambda x: str(x.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        rounded_cost = cost.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        return {'currency': 'CNY', 'inputs': value.model_dump(mode='json'),
                'freight': money(freight), 'customs': money(tax), 'base_cost': money(base),
                'loss_allocation': money(loss_base-base), 'commission': money(2*cost*value.commission_percent/100),
                'cost': money(rounded_cost), 'selling_price': money(rounded_cost*2),
                'formula': 'C=(purchase+weight_g*freight_per_g+customs)/((1-loss_rate)*(1-2*commission_rate)); P=2*C',
                'notice': '人民币经营测算；关税和费率由用户填写，不自动换汇。货损按损耗率摊销，佣金按售价计。成本先四舍五入至分，售价为其两倍；分项相加可能有分币误差。不含未录入费用。'}
