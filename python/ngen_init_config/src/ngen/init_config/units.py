from __future__ import annotations

import typing
import enum
import pydantic
import pydantic.fields

if typing.TYPE_CHECKING:
    from typing import Any
    from pydantic.typing import AbstractSetIntStr, MappingIntStrAny, NoArgAnyCallable


class CommonUnits(str, enum.Enum):
    """Use as `units` argument to `Field` function."""

    Dimensionless = "dimensionless"

    Percent = "percent"
    FractionalPercent = "hectopercent"

    Second = "second"
    Meter = "meter"
    Kilogram = "kilogram"
    Kelvin = "kelvin"


def Field(
    default: Any = pydantic.fields.Undefined,
    *,
    units: str | CommonUnits | None = None,
    default_factory: NoArgAnyCallable | None = None,
    alias: str | None = None,
    title: str | None = None,
    description: str | None = None,
    exclude: AbstractSetIntStr | MappingIntStrAny | Any | None = None,
    include: AbstractSetIntStr | MappingIntStrAny | Any | None = None,
    const: bool | None = None,
    gt: float | None = None,
    ge: float | None = None,
    lt: float | None = None,
    le: float | None = None,
    multiple_of: float | None = None,
    allow_inf_nan: bool | None = None,
    max_digits: int | None = None,
    decimal_places: int | None = None,
    min_items: int | None = None,
    max_items: int | None = None,
    unique_items: bool | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    allow_mutation: bool = True,
    regex: str | None = None,
    discriminator: str | None = None,
    repr: bool = True,
    **extra: Any,
) -> Any:
    """
    Add unit awareness to a `pydantic.fields.FieldInfo`.
    `units` must be parseable by the `pint` package.
    Use like `pydantic.fields.Field` function (similar function signature).

    Example:
        class Model(pydantic.BaseModel):
            height: float = Field(units=CommonUnits.Meter)
            width:  float = Field(units="meter") # equivalent
    """
    return pydantic.Field(
        default=default,
        default_factory=default_factory,
        alias=alias,
        title=title,
        description=description,
        exclude=exclude,
        include=include,
        const=const,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        allow_inf_nan=allow_inf_nan,
        max_digits=max_digits,
        decimal_places=decimal_places,
        min_items=min_items,
        max_items=max_items,
        unique_items=unique_items,
        min_length=min_length,
        max_length=max_length,
        allow_mutation=allow_mutation,
        regex=regex,
        discriminator=discriminator,
        repr=repr,
        units=units,
        **extra,
    )
