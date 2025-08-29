from __future__ import annotations

from typing import Literal, Optional, Mapping
from pydantic import Field

from .bmi_formulation import BMIFortran


class SacSMA(BMIFortran):
    """A BMIFortran implementation for a sac-SMA module"""

    model_params: Optional[
        Mapping[str, str]
    ]  # TODO: add a model w/ the actual parameters
    main_output_variable: str = "tci"
    # NOTE aliases don't propagate to subclasses, so we have to repeat the alias
    model_name: Literal["SacSMA"] = Field("SacSMA", const=True, alias="model_type_name")
