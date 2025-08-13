from __future__ import annotations

from ngen.config.model_vars import (
    Inputs,
    InputsBuilder,
    ModelMeta,
    Outputs,
    OutputsBuilder,
    Var,
    resolve_inputs_mapping,
    resolve_outputs_mapping,
)
from dataclasses import dataclass
from enum import Enum, auto
from collections.abc import Iterable
import typing

if typing.TYPE_CHECKING:
    from typing import Self


def main() -> None:
    forcing = aorc_forcing()
    s = sloth()
    n = nom()
    add_aliases(n, nom_remaps)

    tm = topmodel()
    add_aliases(tm, topmodel_remaps)

    c = cfe()
    add_aliases(c, cfe_remaps)

    # model_stack = [forcing, s.build(), n.build(), c.build()]
    model_stack = [forcing, n.build(), tm.build()]

    # returns set of invalid output variables; if its empty, its valid.
    assert not resolve_outputs_mapping(model_stack)
    chart_text = into_mermaid_flowchart(model_stack)
    print(chart_text)


def aorc_forcing() -> Model:
    output_builder = OutputsBuilder()
    # TODO: add unit support
    for name, (aliases, unit) in _aorc_forcing.items():
        var = Var(name=name)
        output_builder.add_output(var, *aliases)
    outputs = output_builder.build()
    inputs = Inputs()
    return Model(name="aorc_forcing", inputs=inputs, outputs=outputs)


def sloth() -> ModelTemplate:
    _sloth_vars: list[ModelVarDict] = [
        {
            "name": "sloth_ice_fraction_schaake",
            "unit": "m",
            "dtype": "double",
            "type": "output",
        },
        {
            "name": "sloth_ice_fraction_xinanjiang",
            "unit": "-",
            "dtype": "double",
            "type": "output",
        },
        {
            "name": "sloth_smp",
            "unit": "-",
            "dtype": "double",
            "type": "output",
        },
    ]
    vars = create_model_vars(_sloth_vars)
    return into_model_template("sloth", vars)


def cfe() -> ModelTemplate:
    vars = create_model_vars(_cfe_vars)
    return into_model_template("cfe", vars)


def nom() -> ModelTemplate:
    vars = create_model_vars(_nom_vars)
    return into_model_template("nom", vars)


def topmodel() -> ModelTemplate:
    vars = create_model_vars(_topmodel_vars)
    return into_model_template("topmodel", vars)


# TODO: optionally, pull these from a realization config

nom_remaps = {
    "LWDN": "land_surface_radiation~incoming~longwave__energy_flux",
    "PRCPNONC": "atmosphere_water__liquid_equivalent_precipitation_rate",
    "Q2": "atmosphere_air_water~vapor__relative_saturation",
    "SFCPRS": "land_surface_air__pressure",
    "SFCTMP": "land_surface_air__temperature",
    "SOLDN": "land_surface_radiation~incoming~shortwave__energy_flux",
    "UU": "land_surface_wind__x_component_of_velocity",
    "VV": "land_surface_wind__y_component_of_velocity",
}

cfe_remaps = {
    "atmosphere_water__liquid_equivalent_precipitation_rate": "QINSUR",
    "ice_fraction_schaake": "sloth_ice_fraction_schaake",
    "ice_fraction_xinanjiang": "sloth_ice_fraction_xinanjiang",
    "soil_moisture_profile": "sloth_smp",
    "water_potential_evaporation_flux": "EVAPOTRANS",
}

topmodel_remaps = {
    "atmosphere_water__liquid_equivalent_precipitation_rate": "QINSUR",
    "water_potential_evaporation_flux": "EVAPOTRANS",
}


class IODirection(Enum):
    input = auto()
    output = auto()


@dataclass
class BmiVar:
    name: str
    unit: str
    dtype: str
    direction: IODirection

    def as_var(self) -> Var:
        return Var(name=self.name)


class Model(ModelMeta):
    def __init__(self, name: str, inputs: Inputs, outputs: Outputs):
        self._name: str = name
        self._inputs: Inputs = inputs
        self._outputs: Outputs = outputs

    def name(self) -> str:
        return self._name

    def inputs(self) -> Inputs:
        return self._inputs

    def outputs(self) -> Outputs:
        return self._outputs

    def __repr__(self) -> str:
        return f"Model(name={self._name}, inputs={str(self._inputs)}, outputs={str(self._outputs)})"


class ModelTemplate:
    def __init__(
        self, name: str, inputs_builder: InputsBuilder, outputs_builder: OutputsBuilder
    ):
        self._name: str = name
        self._inputs_builder: InputsBuilder = inputs_builder
        self._outputs_builder: OutputsBuilder = outputs_builder

    def name(self) -> str:
        return self._name

    def add_alias(self, name: str, alias: str) -> Self:
        try:
            self._inputs_builder.add_alias(name, alias)
        except KeyError:
            self._outputs_builder.add_alias(name, alias)
        return self

    def build(self) -> Model:
        return Model(
            name=self.name(),
            inputs=self._inputs_builder.build(),
            outputs=self._outputs_builder.build(),
        )

    def __repr__(self) -> str:
        return f"ModelTemplate(name={self._name}, inputs={str(self._inputs_builder)}, outputs={str(self._outputs_builder)})"


def add_alias(model: ModelTemplate, name: str, alias: str) -> None:
    """add alias to existing ModelTemplate"""
    inputs = model._inputs_builder._inputs._inputs
    outputs = model._outputs_builder._outputs._outputs
    if name in inputs or name in outputs:
        model.add_alias(name, alias)
    elif alias in inputs or alias in outputs:
        model.add_alias(alias, name)
    else:
        assert "unreachable"


def add_aliases(model: ModelTemplate, mapping: dict[str, str]) -> None:
    """add aliases to existing ModelTemplate"""
    for name, alias in mapping.items():
        add_alias(model, name, alias)


class ModelVarDict(typing.TypedDict):
    name: str
    unit: str
    dtype: str
    type: typing.Literal["input", "output"]


def create_model_vars(vars: list[ModelVarDict]) -> Iterable[BmiVar]:
    # {"name": "SFCPRS", "unit": "Pa", "dtype": "double", "type": "input"},
    for var in vars:
        ty = var["type"]
        if ty == "input":
            direction = IODirection.input
        elif ty == "output":
            direction = IODirection.output
        else:
            assert False, "unreachable"
        name = var["name"]
        unit = var["unit"]
        dtype = var["dtype"]
        yield BmiVar(name=name, unit=unit, dtype=dtype, direction=direction)


def into_model_template(model_name: str, vars: Iterable[BmiVar]) -> ModelTemplate:
    inputs_builder = InputsBuilder()
    outputs_builder = OutputsBuilder()
    for var in vars:
        if var.direction == IODirection.input:
            inputs_builder.add_input(var.as_var())
        elif var.direction == IODirection.output:
            outputs_builder.add_output(var.as_var())
        else:
            assert "unreachable"
    return ModelTemplate(
        name=model_name, inputs_builder=inputs_builder, outputs_builder=outputs_builder
    )


# mermaid chart generation code


def _mermaid_str(s: str) -> str:
    _mermaid_escape_translations = str.maketrans(
        {
            "~": "\\~",
        }
    )
    return s.translate(_mermaid_escape_translations)


def into_mermaid_flowchart(model_stack: Iterable[Model]) -> str:
    valid_mapping, _ = resolve_inputs_mapping(*model_stack)

    mapped_output = set()
    for model, vars in valid_mapping.items():
        for var in vars:
            name = _mermaid_str(f"{var.src.model}_{var.src.var.name}")
            mapped_output.add(name)

    chart = ["flowchart LR"]
    for model in model_stack:
        model_name = model.name()
        subgraph_start = _mermaid_str(f"\tsubgraph {model_name}")
        chart.append(subgraph_start)
        for var in model.inputs().inputs():
            subgraph_input_var = _mermaid_str(
                f'\t{model_name}_{var.name}["{var.name}"]'
            )
            chart.append(subgraph_input_var)
        for var in model.outputs().outputs():
            name = f"{model_name}_{var.name}"
            # TODO: I think if I pull out subgraph creation that might help things?
            #       it just needs to be more composable
            # if name not in mapped_output and model_name != model_stack[-1].name():
            #    continue
            subgraph_output_var = _mermaid_str(f'\t{name}>"{var.name}"]')
            chart.append(subgraph_output_var)
        subgraph_end = _mermaid_str("\tend")
        chart.append(subgraph_end)

    for vars in valid_mapping.values():
        for var in vars:
            if var.is_src_alias() or var.is_dest_alias():
                connection = _mermaid_str(
                    f'\t{var.src.model}_{var.src.var.name} -- "{var.via}" --> {var.dest.model}_{var.dest.var.name}'
                )
            else:
                connection = _mermaid_str(
                    f"\t{var.src.model}_{var.src.var.name} --> {var.dest.model}_{var.dest.var.name}"
                )
            chart.append(connection)

    return "\n".join(chart)


# NOTE: bmi module variable metadata is hard coded for now.
#       in the future this should come from a bmi introspection tool / config
#       files.

CSDMS_STD_NAME_RAIN_VOLUME_FLUX = "atmosphere_water__rainfall_volume_flux"
CSDMS_STD_NAME_PRECIP_MASS_FLUX = "atmosphere_water__precipitation_mass_flux"
CSDMS_STD_NAME_SOLAR_LONGWAVE = "land_surface_radiation~incoming~longwave__energy_flux"
CSDMS_STD_NAME_SOLAR_SHORTWAVE = (
    "land_surface_radiation~incoming~shortwave__energy_flux"
)
CSDMS_STD_NAME_SURFACE_AIR_PRESSURE = "land_surface_air__pressure"
CSDMS_STD_NAME_HUMIDITY = "atmosphere_air_water~vapor__relative_saturation"
CSDMS_STD_NAME_LIQUID_EQ_PRECIP_RATE = (
    "atmosphere_water__liquid_equivalent_precipitation_rate"
)
CSDMS_STD_NAME_SURFACE_TEMP = "land_surface_air__temperature"
CSDMS_STD_NAME_WIND_U_X = "land_surface_wind__x_component_of_velocity"
CSDMS_STD_NAME_WIND_V_Y = "land_surface_wind__y_component_of_velocity"
NGEN_STD_NAME_SPECIFIC_HUMIDITY = "atmosphere_air_water~vapor__relative_saturation"

AORC_FIELD_NAME_PRECIP_RATE = "precip_rate"
AORC_FIELD_NAME_SOLAR_SHORTWAVE = "DSWRF_surface"
AORC_FIELD_NAME_SOLAR_LONGWAVE = "DLWRF_surface"
AORC_FIELD_NAME_PRESSURE_SURFACE = "PRES_surface"
AORC_FIELD_NAME_TEMP_2M_AG = "TMP_2maboveground"
AORC_FIELD_NAME_APCP_SURFACE = "APCP_surface"
AORC_FIELD_NAME_WIND_U_10M_AG = "UGRD_10maboveground"
AORC_FIELD_NAME_WIND_V_10M_AG = "VGRD_10maboveground"
AORC_FIELD_NAME_SPEC_HUMID_2M_AG = "SPFH_2maboveground"

# name: (aliases, unit)
_aorc_forcing = {
    "precip_rate": (("RAINRATE", CSDMS_STD_NAME_LIQUID_EQ_PRECIP_RATE), "mm s^-1"),
    "APCP_surface": ((CSDMS_STD_NAME_RAIN_VOLUME_FLUX,), "kg m^-2"),
    "DLWRF_surface": (("LWDOWN", CSDMS_STD_NAME_SOLAR_LONGWAVE), "W m-2"),
    "DSWRF_surface": (("SWDOWN", CSDMS_STD_NAME_SOLAR_SHORTWAVE), "W m-2"),
    "PRES_surface": (("PSFC", CSDMS_STD_NAME_SURFACE_AIR_PRESSURE), "Pa"),
    "SPFH_2maboveground": (("Q2D", NGEN_STD_NAME_SPECIFIC_HUMIDITY), "kg kg-1"),
    "TMP_2maboveground": (("T2D", CSDMS_STD_NAME_SURFACE_TEMP), "K"),
    "UGRD_10maboveground": (("U2D", CSDMS_STD_NAME_WIND_U_X), "m s-1"),
    "VGRD_10maboveground": (("V2D", CSDMS_STD_NAME_WIND_V_Y), "m s-1"),
}

_cfe_vars: list[ModelVarDict] = [
    {
        "name": "atmosphere_water__liquid_equivalent_precipitation_rate",
        "unit": "mm h-1",
        "dtype": "double",
        "type": "input",
    },
    {
        "name": "water_potential_evaporation_flux",
        "unit": "m s-1",
        "dtype": "double",
        "type": "input",
    },
    {"name": "ice_fraction_schaake", "unit": "m", "dtype": "double", "type": "input"},
    {
        "name": "ice_fraction_xinanjiang",
        "unit": "none",
        "dtype": "double",
        "type": "input",
    },
    {
        "name": "soil_moisture_profile",
        "unit": "none",
        "dtype": "double",
        "type": "input",
    },
    {"name": "RAIN_RATE", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "GIUH_RUNOFF", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "INFILTRATION_EXCESS", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "DIRECT_RUNOFF", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "NASH_LATERAL_RUNOFF", "unit": "m", "dtype": "double", "type": "output"},
    {
        "name": "DEEP_GW_TO_CHANNEL_FLUX",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {"name": "SOIL_TO_GW_FLUX", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "Q_OUT", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "POTENTIAL_ET", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "ACTUAL_ET", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "GW_STORAGE", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "SOIL_STORAGE", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "SOIL_STORAGE_CHANGE", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "SURF_RUNOFF_SCHEME", "unit": "none", "dtype": "int", "type": "output"},
    {"name": "NWM_PONDED_DEPTH", "unit": "m", "dtype": "double", "type": "output"},
]

_topmodel_vars: list[ModelVarDict] = [
    {
        "name": "atmosphere_water__liquid_equivalent_precipitation_rate",
        "unit": "m h-1",
        "dtype": "double",
        "type": "input",
    },
    {
        "name": "water_potential_evaporation_flux",
        "unit": "m h-1",
        "dtype": "double",
        "type": "input",
    },
    {"name": "Qout", "unit": "m h-1", "dtype": "double", "type": "output"},
    {
        "name": "atmosphere_water__liquid_equivalent_precipitation_rate_out",
        "unit": "m h-1",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "water_potential_evaporation_flux_out",
        "unit": "m h-1",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__runoff_mass_flux",
        "unit": "m h-1",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "soil_water_root-zone_unsat-zone_top__recharge_volume_flux",
        "unit": "m h-1",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__baseflow_volume_flux",
        "unit": "m h-1",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "soil_water__domain_volume_deficit",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__domain_time_integral_of_overland_flow_volume_flux",
        "unit": "m h-1",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__domain_time_integral_of_precipitation_volume_flux",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__domain_time_integral_of_evaporation_volume_flux",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__domain_time_integral_of_runoff_volume_flux",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "soil_water__domain_root-zone_volume_deficit",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "soil_water__domain_unsaturated-zone_volume",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
    {
        "name": "land_surface_water__water_balance_volume",
        "unit": "m",
        "dtype": "double",
        "type": "output",
    },
]

_nom_vars: list[ModelVarDict] = [
    {"name": "SFCPRS", "unit": "Pa", "dtype": "double", "type": "input"},
    {"name": "SFCTMP", "unit": "K", "dtype": "double", "type": "input"},
    {"name": "SOLDN", "unit": "W/m2", "dtype": "double", "type": "input"},
    {"name": "LWDN", "unit": "W/m2", "dtype": "double", "type": "input"},
    {"name": "UU", "unit": "m/s", "dtype": "double", "type": "input"},
    {"name": "VV", "unit": "m/s", "dtype": "double", "type": "input"},
    {"name": "Q2", "unit": "kg/kg", "dtype": "double", "type": "input"},
    {"name": "PRCPNONC", "unit": "mm/s", "dtype": "double", "type": "input"},
    {"name": "QINSUR", "unit": "m/s", "dtype": "double", "type": "output"},
    {"name": "ETRAN", "unit": "mm", "dtype": "double", "type": "output"},
    {"name": "QSEVA", "unit": "mm/s", "dtype": "double", "type": "output"},
    {"name": "EVAPOTRANS", "unit": "m/s", "dtype": "double", "type": "output"},
    {"name": "TG", "unit": "K", "dtype": "double", "type": "output"},
    {"name": "SNEQV", "unit": "mm", "dtype": "double", "type": "output"},
    {"name": "TGS", "unit": "K", "dtype": "double", "type": "output"},
    {"name": "ACSNOM", "unit": "mm", "dtype": "double", "type": "output"},
    {"name": "SNOWT_AVG", "unit": "K", "dtype": "double", "type": "output"},
    {"name": "ISNOW", "unit": "unitless", "dtype": "int", "type": "output"},
    {"name": "QRAIN", "unit": "mm/s", "dtype": "double", "type": "output"},
    {"name": "FSNO", "unit": "unitless", "dtype": "double", "type": "output"},
    {"name": "SNOWH", "unit": "m", "dtype": "double", "type": "output"},
    {"name": "SNLIQ", "unit": "mm", "dtype": "double", "type": "output"},
    {"name": "QSNOW", "unit": "mm/s", "dtype": "double", "type": "output"},
    {"name": "ECAN", "unit": "mm", "dtype": "double", "type": "output"},
    {"name": "GH", "unit": "W/m-2", "dtype": "double", "type": "output"},
    {"name": "TRAD", "unit": "K", "dtype": "double", "type": "output"},
    {"name": "FSA", "unit": "W/m-2", "dtype": "double", "type": "output"},
    {"name": "CMC", "unit": "mm", "dtype": "double", "type": "output"},
    {"name": "LH", "unit": "W/m-2", "dtype": "double", "type": "output"},
    {"name": "FIRA", "unit": "W/m-2", "dtype": "double", "type": "output"},
    {"name": "FSH", "unit": "W/m-2", "dtype": "double", "type": "output"},
]

if __name__ == "__main__":
    main()
