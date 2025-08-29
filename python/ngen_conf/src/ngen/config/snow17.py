from __future__ import annotations

from typing import Literal, Optional, Mapping
from pydantic import Field

from .bmi_formulation import BMIFortran


class Snow17(BMIFortran):
    """A BMIFortran implementation for a snow-17 module"""

    model_params: Optional[
        Mapping[str, str]
    ]  # TODO: add a model w/ the actual parameters
    main_output_variable: str = "raim"
    # NOTE aliases don't propagate to subclasses, so we have to repeat the alias
    model_name: Literal["Snow17"] = Field("Snow17", const=True, alias="model_type_name")
