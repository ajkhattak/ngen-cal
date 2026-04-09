from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional, Union

from ngen.init_config import serializer_deserializer as serde
from pydantic import validator

from ngen.init_config.units import CommonUnits, Field

if TYPE_CHECKING:
    from pydantic.typing import AbstractSetIntStr, DictStrAny, MappingIntStrAny


class CFEBase(serde.IniSerializerDeserializer):
    forcing_file: Literal["BMI"] = "BMI"
    # soil depth
    soil_params_depth: float = Field(units=CommonUnits.Meter)
    # beta exponent on Clapp-Hornberger (1978) soil water relations
    soil_params_b: float = Field(units=CommonUnits.Dimensionless)
    # saturated hydraulic conductivity
    soil_params_satdk: float = Field(units="m/s")
    # saturated capillary head
    soil_params_satpsi: float = Field(units=CommonUnits.Meter)
    # this factor (0-1) modifies the gradient of the hydraulic head at the soil bottom. 0=no-flow.
    soil_params_slop: float = Field(units=CommonUnits.Dimensionless)
    # saturated soil moisture content
    soil_params_smcmax: float = Field(units=CommonUnits.Dimensionless)
    # wilting point soil moisture content
    soil_params_wltsmc: float = Field(units=CommonUnits.Dimensionless)
    refkdt: Optional[float] = 3.0
    soil_params_expon: float = Field(default=1.0, units=CommonUnits.Dimensionless)
    soil_params_expon_secondary: float = Field(default=1.0, units=CommonUnits.Dimensionless)
    # maximum storage in the conceptual reservoir
    max_gw_storage: float = Field(units=CommonUnits.Meter)
    # the primary outlet coefficient
    cgw: float = Field(units="m/h")
    # exponent parameter (1.0 for linear reservoir)
    expon: float = Field(units=CommonUnits.Dimensionless)
    # initial condition for groundwater reservoir - it is the ground water as a decimal fraction of
    # the maximum groundwater storage (max_gw_storage) for the initial timestep
    gw_storage: float = Field(units=CommonUnits.Dimensionless)  # 50%
    # field capacity
    alpha_fc: float = Field(units=CommonUnits.Dimensionless)
    # initial condition for soil reservoir - it is the water in the soil as a decimal fraction of
    # maximum soil water storage (smcmax * depth) for the initial timestep
    soil_storage: float = Field(units=CommonUnits.Dimensionless)  # 66.7%
    # number of Nash lf reservoirs (optional, defaults to 2, ignored if storage values present)
    k_nash: float = Field(units=CommonUnits.Dimensionless)
    # Nash Config param - primary reservoir
    k_lf: float = Field(units=CommonUnits.Dimensionless)
    # Nash Config param - secondary reservoir
    nash_storage: List[float]
    # Giuh ordinates in dt time steps
    giuh_ordinates: List[float]
    # set to `1` if `forcing_file=BMI`
    num_timesteps: int = Field(1, gte=0)

    # prints various debug and bmi info
    verbosity: int = Field(0, gte=0, lte=3)

    # direct runoff
    surface_partitioning_scheme: Literal["Schaake", "Xinanjiang"]

    @validator("nash_storage", "giuh_ordinates", pre=True)
    def _coerce_lists(cls, value):
        if isinstance(value, list):
            return value
        return [x.strip() for x in value.split(",")]

    class Config(serde.IniSerializerDeserializer.Config):
        def _serialize_list(l: list[float]) -> str:
            return ",".join(map(lambda x: str(x), l))

        field_serializers = {
            "nash_storage": _serialize_list,
            "giuh_ordinates": _serialize_list,
        }

        fields = {
            "cgw": {"alias": "Cgw"},
            "k_lf": {"alias": "K_lf"},
            "k_nash": {"alias": "K_nash"},
            "soil_params_depth": {"alias": "soil_params.depth"},
            "soil_params_b": {"alias": "soil_params.b"},
            "soil_params_mult": {"alias": "soil_params.mult"},
            "soil_params_satdk": {"alias": "soil_params.satdk"},
            "soil_params_satpsi": {"alias": "soil_params.satpsi"},
            "soil_params_slop": {"alias": "soil_params.slop"},
            "soil_params_smcmax": {"alias": "soil_params.smcmax"},
            "soil_params_wltsmc": {"alias": "soil_params.wltsmc"},
            "soil_params_expon": {"alias": "soil_params.expon"},
            "soil_params_expon_secondary": {"alias": "soil_params.expon_secondary"},
        }


class CFESchaake(CFEBase):
    surface_partitioning_scheme: Literal["Schaake"] = "Schaake"


class CFEXinanjiang(CFEBase):
    # direct runoff
    surface_partitioning_scheme: Literal["Xinanjiang"] = "Xinanjiang"
    a_xinanjiang_inflection_point_parameter: float
    b_xinanjiang_shape_parameter: float
    x_xinanjiang_shape_parameter: float
    urban_decimal_fraction: float

    class Config(CFEBase.Config):
        fields = {
            "a_xinanjiang_inflection_point_parameter": {
                "alias": "a_Xinanjiang_inflection_point_parameter"
            },
            "b_xinanjiang_shape_parameter": {"alias": "b_Xinanjiang_shape_parameter"},
            "x_xinanjiang_shape_parameter": {"alias": "x_Xinanjiang_shape_parameter"},
        }


class CFESchaakeCoupledSoilMoisture(CFESchaake):
    aet_rootzone: bool  # True, true, 1
    # layer of the soil that is the maximum root zone depth. That is, the depth of the layer where the AET is drawn from
    max_root_zone_layer: float = Field(units=CommonUnits.Meter)
    # an array of depths from the surface. Example, soil_layer_depths=0.1,0.4,1.0,2.0
    soil_layer_depths: List[float]
    # `ice-fraction based runoff` | when `CFE coupled to SoilFreezeThaw`
    sft_coupled: bool  # True, true, 1


class CFEXinanjiangCoupledSoilMoisture(CFEXinanjiang):
    aet_rootzone: bool  # True, true, 1
    # layer of the soil that is the maximum root zone depth. That is, the depth of the layer where the AET is drawn from
    max_root_zone_layer: float = Field(units=CommonUnits.Meter)
    # an array of depths from the surface. Example, soil_layer_depths=0.1,0.4,1.0,2.0
    soil_layer_depths: List[float]
    # `ice-fraction based runoff` | when `CFE coupled to SoilFreezeThaw`
    sft_coupled: bool  # True, true, 1


class CFE(serde.IniSerializerDeserializer):
    __root__: Union[
        CFESchaakeCoupledSoilMoisture,
        CFEXinanjiangCoupledSoilMoisture,
        CFESchaake,
        CFEXinanjiang,
    ]

    class Config(serde.IniSerializerDeserializer.Config):
        space_around_delimiters = False
        no_section_headers = True
        allow_population_by_field_name = True
        preserve_key_case = True

    def dict(
        self,
        *,
        include: AbstractSetIntStr | MappingIntStrAny | None = None,
        exclude: AbstractSetIntStr | MappingIntStrAny | None = None,
        by_alias: bool = False,
        skip_defaults: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> DictStrAny:
        serial = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        return serial["__root__"]
