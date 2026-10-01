from __future__ import annotations

import pathlib
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest
import xarray as xr
from ngen.cal.ngen import NgenBase
from ngen.cal.ngen_hooks.ngen_output import (
    TrouteOutput,
    _stream_output_netcdf_v1,
)
from ngen.config.realization import NgenRealization

data_dir = pathlib.Path(__file__).parent / "data/troute_output/"


@pytest.fixture
def ngen_cal_model_config() -> NgenBase:
    # NOTE: validation skipped and only fields required for
    # `TrouteOutput.ngen_cal_model_configure` are implemented
    realization = NgenRealization.parse_file(
        data_dir / "example_realization_config.json"
    )
    base = NgenBase.construct()
    base.ngen_realization = realization
    return base


troute_output_variants = (
    data_dir / "flowveldepth.csv",
    data_dir / "flowveldepth.parquet",
    data_dir / "troute_output.csv",
    data_dir / "troute_output.nc",
)


@pytest.mark.parametrize("file", troute_output_variants)
def test_ngen_cal_model_output(file: pathlib.Path, ngen_cal_model_config: NgenBase):
    output = TrouteOutput(file)

    # setup plugin
    output.ngen_cal_model_configure(config=ngen_cal_model_config)

    nexus = SimpleNamespace(
        id="nex-2420800",
        contributing_catchments=[SimpleNamespace(id="cat-2420800")],
    )
    df = output.get_output(nexus=nexus)
    assert df is not None, "expect to receive pd.Series"

    dt = datetime.fromisoformat("2023-04-02 01:00:00")
    assert df[dt] == 0.0

    # testing data is for a single day
    assert len(df) == 24


def test_single_file_netcdf_output_schema(tmp_path: pathlib.Path):
    output_file = tmp_path / "troute_output.nc"
    times = np.array(
        ["2023-04-02T00:00:00", "2023-04-02T01:00:00"],
        dtype="datetime64[ns]",
    )
    xr.Dataset(
        data_vars={
            "streamflow": (
                ("time", "flowpath_id"),
                np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
            ),
            "nex_streamflow": (
                ("time", "nexus_id"),
                np.array([[3.0], [7.0]], dtype=np.float32),
            ),
        },
        coords={
            "time": times,
            "flowpath_id": [11, 12],
            "nexus_id": [21],
        },
    ).to_netcdf(output_file)

    get_output = _stream_output_netcdf_v1(output_file)

    assert get_output(11).tolist() == [1.0, 3.0]
    assert get_output(12).tolist() == [2.0, 4.0]
    assert get_output(21).tolist() == [3.0, 7.0]
