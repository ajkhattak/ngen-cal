from __future__ import annotations

import pathlib
import typing
from datetime import datetime

import typing_extensions
from pydantic import validator

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
class SacSma(serde.NamelistSerializerDeserializer):
    if typing.TYPE_CHECKING:
        sac_param_file: PathPair[SacSmaParams]
    else:
        sac_param_file: path_pair(
            SacSmaParams,
            serializer=lambda o: o.to_str().encode(),
            deserializer=SacSmaParams.parse_obj,
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
            "sac_param_file": lambda f: str(f),
            "start_datehr": lambda d: int(d.strftime("%Y%m%d%H")),
            "end_datehr": lambda d: int(d.strftime("%Y%m%d%H")),
        }

    @typing_extensions.override
    def to_namelist_str(self) -> str:
        o = _SacSmaWrapper(sac_control=_SacSmaNgenDefaults.parse_obj(self))
        d = o.dict(by_alias=True)
        return format_serializers.to_namelist_str(d)

    @typing_extensions.override
    @classmethod
    def from_namelist(cls, p: pathlib.Path) -> Self:
        o = from_namelist_str(p.read_text(), _SacSmaWrapper)
        return cls.parse_obj(o)

    @typing_extensions.override
    @classmethod
    def from_namelist_str(cls, s: str) -> Self:
        o = from_namelist_str(s, _SacSmaWrapper)
        return cls.parse_obj(o.sac_control)


# NOTE: update_forward_refs() call at bottom of file
# NOTE: these are required by sac-sma, but obsolete for ngen users.
#       when `SacSma` is (de)serialized from/to the namelist format it is done
#       via `_SacSmaWrapper` which embeds a `_SacSmaNgenDefaults`.
#       the trade off is use experience vs maintenance burden.
#       in this case I prefer the user experience.
class _SacSmaNgenDefaults(SacSma):
    main_id: str = "ngen.config_gen"
    n_hrus: int = 1  # 1 for ngen
    forcing_root: pathlib.Path = pathlib.Path("/dev/null")
    output_root: pathlib.Path = pathlib.Path("/dev/null")
    sac_state_out_root: pathlib.Path = pathlib.Path("/dev/null")
    sac_state_in_root: pathlib.Path = pathlib.Path("/dev/null")
    output_hrus: bool = False
    warm_start_run: bool = False
    write_states: bool = False

    class Config(SacSma.Config):
        field_serializers = {
            "forcing_root": lambda f: str(f),
            "output_root": lambda f: str(f),
            "sac_state_out_root": lambda f: str(f),
            "sac_state_in_root": lambda f: str(f),
            "output_hrus": lambda b: int(b),
            "warm_start_run": lambda b: int(b),
            "write_states": lambda b: int(b),
        }


class _SacSmaWrapper(serde.NamelistSerializerDeserializer):
    sac_control: _SacSmaNgenDefaults


# NOTE: this is not a general sac-sma config file parser.
#       it only parses sac-sma config files usable in ngen
class SacSmaParams(serde.GenericSerializerDeserializer):
    hru_area: float  # sq-km, needed for combination & routing conv.
    uztwm: float
    uzfwm: float
    lztwm: float
    lzfpm: float
    lzfsm: float
    adimp: float
    uzk: float
    lzpk: float
    lzsk: float
    zperc: float
    rexp: float
    pctim: float
    pfree: float
    riva: float
    side: float
    rserv: float

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
            "uztwm",
            "uzfwm",
            "lztwm",
            "lzfpm",
            "lzfsm",
            "adimp",
            "uzk",
            "lzpk",
            "lzsk",
            "zperc",
            "rexp",
            "pctim",
            "pfree",
            "riva",
            "side",
            "rserv",
        }
        count = 0
        while (line := reader.readline()) != "":
            field, value = line.split(" ")
            if field in fields:
                value = parse_float(field, value)
                data[field] = value
                count += 1

        if count != len(fields):
            missing = ",".join(fields.difference(data.keys()))
            raise RuntimeError(f"missing fields: {missing}")
        return cls(**data)

    @typing_extensions.override
    def to_str(self, *_) -> str:
        s = f"""hru_id ngen.config_gen
hru_area {self.hru_area}
uztwm {self.uztwm}
uzfwm {self.uzfwm}
lztwm {self.lztwm}
lzfpm {self.lzfpm}
lzfsm {self.lzfsm}
adimp {self.adimp}
uzk {self.uzk}
lzpk {self.lzpk}
lzsk {self.lzsk}
zperc {self.zperc}
rexp {self.rexp}
pctim {self.pctim}
pfree {self.pfree}
riva {self.riva}
side {self.side}
rserv {self.rserv}"""
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


SacSma.update_forward_refs()
_SacSmaNgenDefaults.update_forward_refs()
