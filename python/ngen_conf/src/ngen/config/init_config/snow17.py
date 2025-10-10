from __future__ import annotations

import pathlib
import typing
from datetime import datetime

import typing_extensions
from pydantic import validator, Field

from ngen.config.path_pair.path_pair import PathPair, path_pair
from ngen.init_config import serializer_deserializer as serde
from ngen.init_config.deserializer import from_namelist_str
from ngen.init_config.serializer import format_serializers

# TODO: refactor into independent module
from .topmodel import _maybe_into_readliner, _Readliner

if typing.TYPE_CHECKING:
    from typing import Any, Self


# NOTE: this is not a general snow17 config file parser.
#       it only parses snow17 config files usable in ngen
# NOTE: update_forward_refs() call at bottom of file
class Snow17(serde.NamelistSerializerDeserializer):
    if typing.TYPE_CHECKING:
        snow17_param_file: PathPair[Snow17Params]
    else:
        snow17_param_file: path_pair(
            Snow17Params,
            serializer=lambda o: o.to_str().encode(),
            deserializer=Snow17Params.parse_obj,
        )

    start_datehr: datetime
    end_datehr: datetime
    model_timestep: int = 3600  # 1 hr in seconds for ngen

    @validator("start_datehr", "end_datehr", pre=True)
    def _validate_datetime(cls, value: datetime | str | int) -> datetime:
        if isinstance(value, int):
            value = str(value)

        if isinstance(value, datetime):
            return value
        elif isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y%m%d%H")
            except ValueError as e1:
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    raise ValueError(
                        f"expected string datetime in format YYYYMMDDHH (%Y%m%d%H) or ISO8601, got: {value!r}"
                    ) from e1
        else:
            raise ValueError(
                f"expected datetime or string in format YYYYMMDDHH (%Y%m%d%H) or ISO8601, got: {value!r}"
            )

    class Config(serde.NamelistSerializerDeserializer.Config):
        field_serializers = {
            "snow17_param_file": lambda f: str(f),
            "start_datehr": lambda d: int(d.strftime("%Y%m%d%H")),
            "end_datehr": lambda d: int(d.strftime("%Y%m%d%H")),
        }

    @typing_extensions.override
    def to_namelist_str(self) -> str:
        o = _Snow17Wrapper(snow17_control=_Snow17NgenDefaults.parse_obj(self))
        d = o.dict(by_alias=True)
        return format_serializers.to_namelist_str(d)

    @typing_extensions.override
    @classmethod
    def from_namelist(cls, p: pathlib.Path) -> Self:
        o = from_namelist_str(p.read_text(), _Snow17Wrapper)
        return cls.parse_obj(o)

    @typing_extensions.override
    @classmethod
    def from_namelist_str(cls, s: str) -> Self:
        o = from_namelist_str(s, _Snow17Wrapper)
        return cls.parse_obj(o.snow17_control)


# NOTE: update_forward_refs() call at bottom of file
# NOTE: these are required by snow17, but obsolete for ngen users.
#       when `Snow17` is (de)serialized from/to the namelist format it is done
#       via `_Snow17Wrapper` which embeds a `_Snow17NgenDefaults`.
#       the trade off is use experience vs maintenance burden.
#       in this case I prefer the user experience.
class _Snow17NgenDefaults(Snow17):
    main_id: str = "ngen.config_gen"
    n_hrus: int = 1  # 1 for ngen
    forcing_root: pathlib.Path = pathlib.Path("/dev/null")
    output_root: pathlib.Path = pathlib.Path("/dev/null")
    snow_state_out_root: pathlib.Path = pathlib.Path("/dev/null")
    snow_state_in_root: pathlib.Path = pathlib.Path("/dev/null")
    output_hrus: bool = False
    warm_start_run: bool = False
    write_states: bool = False

    class Config(Snow17.Config):
        field_serializers = {
            "forcing_root": lambda f: str(f),
            "output_root": lambda f: str(f),
            "snow_state_out_root": lambda f: str(f),
            "snow_state_in_root": lambda f: str(f),
            "output_hrus": lambda b: int(b),
            "warm_start_run": lambda b: int(b),
            "write_states": lambda b: int(b),
        }


class _Snow17Wrapper(serde.NamelistSerializerDeserializer):
    snow17_control: _Snow17NgenDefaults


# NOTE: this is not a general snow17 config file parser.
#       it only parses snow17 config files usable in ngen
class Snow17Params(serde.GenericSerializerDeserializer):
    hru_area: float  # sq-km, needed for combination & routing conv.
    latitude: float  # centroid latitude of hru (decimal degrees)
    elev: float  # mean elevation of hru (m)
    scf: float
    mfmax: float
    mfmin: float
    uadj: float
    si: float
    pxtemp: float
    nmf: float
    tipm: float
    mbase: float
    plwhc: float
    daygm: float
    adc: list[float] = Field(min_items=11, max_items=11)

    @typing_extensions.override
    @classmethod
    def parse_obj(cls: type[Self], obj: Any) -> Self:
        if (r := _maybe_into_readliner(obj)) is not None:
            return cls._parse(r)
        return super().parse_obj(obj)

    @classmethod
    def _parse(cls, reader: _Readliner) -> Self:
        def parse_float(field: str, value: str) -> float:
            try:
                return float(value)
            except BaseException as e:
                raise ValueError(
                    f"could not parse field: {field!r}, got {value}"
                ) from e

        data = {}
        fields = {
            "hru_area",
            "latitude",
            "elev",
            "scf",
            "mfmax",
            "mfmin",
            "uadj",
            "si",
            "pxtemp",
            "nmf",
            "tipm",
            "mbase",
            "plwhc",
            "daygm",
            # "adc{1..=11}", # NOTE: handled separately
        }
        count = 0
        adc: list[float] = [0.0] * 11
        while (line := reader.readline()) != "":
            field, value = line.split(" ")

            if field.startswith("adc"):
                value = parse_float(field, value)
                # NOTE: account for fortran indexing
                idx = int(field[len("adc") :]) - 1
                adc[idx] = value
            elif field in fields:
                value = parse_float(field, value)
                data[field] = value
            else:
                continue
            count += 1

        # NOTE: expected 11 adc values
        if count != len(fields) + 11:
            missing = ",".join(fields.difference(data.keys()))
            raise RuntimeError(f"missing fields: {missing}")
        data["adc"] = adc
        return cls(**data)

    @typing_extensions.override
    def to_str(self, *_) -> str:
        # NOTE: account for fortran indexing
        adc_values = "\n".join(
            f"adc{i + 1} {value}" for i, value in enumerate(self.adc)
        )
        s = f"""hru_id ngen.config_gen
hru_area {self.hru_area}
latitude {self.latitude}
elev {self.elev}
scf {self.scf}
mfmax {self.mfmax}
mfmin {self.mfmin}
uadj {self.uadj}
si {self.si}
pxtemp {self.pxtemp}
nmf {self.nmf}
tipm {self.tipm}
mbase {self.mbase}
plwhc {self.plwhc}
daygm {self.daygm}
{adc_values}"""
        return s

    @typing_extensions.override
    def to_file(self, p: pathlib.Path, *_) -> None:
        p.write_text(self.to_str())

    @typing_extensions.override
    @classmethod
    def from_str(cls, s: str, *_) -> Self:
        return cls.parse_obj(s)

    @typing_extensions.override
    @classmethod
    def from_file(cls, p: pathlib.Path, *_) -> Self:
        return cls.parse_file(p)


Snow17.update_forward_refs()
_Snow17NgenDefaults.update_forward_refs()
