from pathlib import Path
from typing import Literal, Optional, Union

from ngen.init_config import serializer_deserializer
from pydantic import Field
from typing_extensions import override

from .utils import CSList, FloatUnitPair
from .value_unit_pair import ListUnitPair


class Casam(serializer_deserializer.IniSerializerDeserializer):
    forcing_file: Optional[Path]
    """
    provides precipitation and PET inputs

    only required if you are running in standalone mode (outside of NextGen).

    units: -
    """

    soil_params_file: Path
    """
    provides soil types with van Genuchton parameters

    units: -
    """

    layer_thickness: Union[ListUnitPair[float, Literal["cm"]], CSList[float]]
    """
    individual layer thickness (not absolute)

    units: cm
    """

    initial_psi: Union[float, FloatUnitPair[Literal["cm"]]]
    """
    >=0	cm	capillary head
    used to initialize layers with a constant head

    units: cm
    bounds: >= 0
    """

    ponded_depth_max: Union[float, FloatUnitPair[Literal["cm"]]]
    """
    >=0	cm	maximum surface ponding
    the maximum amount of water unavailable for surface drainage, default is set to zero

    units: cm
    bounds: >= 0
    """

    timestep: FloatUnitPair[Literal["s", "sec", "min", "minute", "h", "hr"]]
    """
    >0	sec/min/hr	temporal resolution
    timestep of the model

    units: "s", "sec", "min", "minute", "h", "hr"
    bounds: > 0
    """

    forcing_resolution: FloatUnitPair[Literal["s", "sec", "min", "minute", "h", "hr"]]
    """
    sec/min/hr temporal resolution
    timestep of the forcing data

    units: "s", "sec", "min", "minute", "h", "hr"
    """

    endtime: FloatUnitPair[Literal["s", "sec", "min", "minute", "h", "hr", "d", "day"]]
    """
    >0 sec, min, hr, d	simulation duration
    time at which model simulation ends

    units: "s", "sec", "min", "minute", "h", "hr", "d", "day"
    """

    layer_soil_type: CSList[int]
    """
    layer soil type (read from the database file soil_params_file)

    units: -
    """

    max_valid_soil_types: int = Field(15, gt=1)
    """
    maximum number of soil types read from the file soil_params_file (default is set to 15)

    units: -
    """

    wilting_point_psi: Union[float, FloatUnitPair[Literal["cm"]]]
    """
    wilting point (the amount of water not available for plants) used in computing AET

    units: cm
    bounds: > 0
    """

    field_capacity_psi: Union[float, FloatUnitPair[Literal["cm"]]]
    """
    capillary head corresponding to volumetric water content at which gravity drainage becomes slower, used in computing AET.
    suggested value is 340.9 cm for most soils, corresponding to 1/3 atm, and 103.3 cm for sands, corresponding to 1/10 atm.

    units: cm
    bounds: >0 and < wilting_point_psi
    """

    use_closed_form_g: bool = Field(False, alias="use_closed_form_G")
    """
    determines whether the numeric integral or closed form for G is used; a value of true will use the closed form.
    default is false.

    units:-
    """

    giuh_ordinates: CSList[float]
    """
    GIUH ordinates (for giuh based surface runoff)

    units: -
    """

    verbosity: Literal["high", "low", "none"] = "none"
    """
    controls IO (screen outputs and writing to disk)

    units: -
    """

    sft_coupled: bool = False
    """
    model coupling impacts hydraulic conductivity couples LASAM to SFT.
    Coupling to SFT reduces hydraulic conducitivity, and hence infiltration, when soil is frozen.
    default is false.

    units: -
    """

    soil_z: Union[ListUnitPair[float, Literal["cm"]], CSList[float]]
    """
    vertical resolution of the soil column (computational domain of the SFT model)

    units: cm
    """

    calib_params: bool = False
    """
    calibratable params flag
    impacts soil properties	If set to true, soil smcmax, smcmin, vg_m, and vg_alpha are calibrated.
    defualt is false.
    vg = van Genuchten, SMC= soil moisture content

    units: -
    """

    adaptive_timestep: bool = True
    """
    If set to true, LGAR will use an internal adaptive timestep, and the above timestep is used as a minimum timestep (recommended value of 300 seconds).
    the adaptive timestep will never be larger than the forcing resolution.
    if set to false, LGAR will use the above specified timestep as a fixed timestep.
    testing indicates that setting this value to true substantially decreases runtime while negligibly changing the simulation.
    we recommend this to be set to true.
    defaults to true.

    units: -
    """

    free_drainage_enabled: bool = False
    """
    if free_drainage_enabled is true, then free drainage will be enabled as the lower boundary condition, where fluxes from the vadose zone to groundwater are controlled by the hydraulic conductivity at the bottom of the model domain.
    if free_drainage_enabled is set to false, then the lower boundary condition will be no flow.
    if lgar is used in an area with substantially more pet than precipitation, the choice of no flow vs free drainage should be less impactful, because the majority of water that leaves the vadose zone will do so as aet.
    defaults to false.

    units: -
    """

    free_drainage_to_cr: bool = Field(default=False, alias="free_drainage_to_CR")
    """
    if this is set to true, then free drainage water will contribute to the conceptual reservoir.
    defaults to false.

    units: -
    """

    mbal_tol: float = Field(default=10.0, gt=0)
    """
    mass balance error resulting from a substep that will trigger a model crash

    units: cm
    bounds: > 0

    if the mass balance error is greater than this number in a single substep, then the model will abort.
    global mass balance errors over the course of year long simulations (i.e. the sum of all mass balance errors over the course of a long simulation) tend to be small, where a value greater than 1e-4 cm tends to be rare, occuring less than 1 in 10000 prameter sets.
    lgar in theory should both be mass conservative, however the presence of unlikely but possible edge cases can cause mass balance errors.
    flux caching can also cause small mass balance errors.
    while the model will usually converge with a small mbal_tol value, if general convergence is desired across a large number of parameter sets / forcing datasets, then we recommend that this value is not specified and therefore the default value of 1e1cm will be used.
    """

    pet_affects_precip: bool = Field(default=False, alias="PET_affects_precip")
    """
    specifies whether PET is subtracted from precip

    units: -
    bounds: bool

    if enabled, then pet will be subtracted from precipitation.
    defaults to false.
    """

    a: float = Field(default=0.0, gt=1e-8, lt=1e-1)
    """
    parameter for nonlinear reservoir

    units: cm^(1-b) h^-1
    bounds: 1E-8 < a < 1E-1

    casam fundamentally has two different types of water storage: water stored in the vadose zone that does not contribute to streamflow, and water stored in a nonlinear reservoir that does contribute to streamflow.
    the nonlinear reservoir has an input of simple bypass through the vadose zone (controlled by frac_to_cr and spf_factor), and free drainage if desired.
    the nonlinear reservoir releases water to the stream at a rate of a*s^b, where s is the water stored in the reserovir in cm, and a and b are nonlinear reservoir parameters.
    note that the units of a depend on the value of b.
    defaults to 0.
    """

    b: float = Field(default=0.0, gt=0.01, lt=5)
    """
    parameter for nonlinear reservoir

    units: -
    bounds: 0.01 < b < 5

    casam fundamentally has two different types of water storage: water stored in the vadose zone that does not contribute to streamflow, and water stored in a nonlinear reservoir that does contribute to streamflow.
    the nonlinear reservoir has an input of simple bypass through the vadose zone (controlled by frac_to_cr and spf_factor), and free drainage if desired.
    the nonlinear reservoir releases water to the stream at a rate of a*s^b, where s is the water stored in the reserovir in cm, and a and b are nonlinear reservoir parameters.
    defaults to 0.
    """

    frac_to_cr: float = Field(default=0.0, ge=0, le=1, alias="frac_to_CR")
    """
    parameter for nonlinear reservoir

    units: -
    bounds: 0.0 <= frac_to_CR <= 1

    simple bypass of water at the soil surface to the nonlinear conceptual reservoir will occur when the most superficial surface wetting front achieves the theta_e value of its layer times spf_factor.
    when this occurs, the amount of water sent to the nonlinear reservoir is equal to the precipitation plus any ponded water times frac_to_cr.
    this is a rather simple representation of preferential flow that intends to simulate the episodic nature of streamflow events in arid or semi arid environments.
    note that either all or none of a, b, and frac_to_cr must be specified.
    if none are specified then the model will not simulate a nonlinear reservoir.
    defaults to 0.
    """

    spf_factor: float = Field(default=0.98, ge=0.1, le=1)
    """
    parameter for fluxes to nonlinear reservoir

    units: -
    bounds: 0.1 <= spf_factor <= 1

    simple bypass of surface water to the nonlinear reservoir will occur when the most superficial wetting front achieves the theta_e value of its layer times spf_factor.
    when this occurs, the amount of water sent to the nonlinear reservoir is equal to the precipitation plus any ponded water times frac_to_cr.
    this is a rather simple representation of preferential flow that intends to simulate the episodic nature of streamflow events in arid or semi arid environments.
    defaults to 0.98.
    """

    allow_flux_caching: bool = False
    """
    flux caching -- trades a small amount of accuracy for a lot of speed

    units: -
    bounds: bool

    during dry periods, it is often the case that wetting fronts will move very slowly and aet will be significantly less than pet.
    in these cases, in the context of streamflow simulation, it is not efficient to recompute fluxes and soil moisture dynamics for each time step.
    if this is set to true, then fluxes and wetting front movement will only be recomputed once every 24 hours, or when the conditions resulting in dry and slow wetting fronts and low aet cease.
    during the times for which fluxes are not recomputed, instead they are stored in a cache and fluxes for subsequent time steps are set using this cache.
    sligtly different strategies are used for fluxes through the lower boundary and aet.
    also note that because nextgen models should ideally provide output for each hour, simply setting an adaptive time step to be larger than one hour is not a preferred runtime reduction method here.
    note that this can cause small mass balance errors when the lower boundary condition is set to free drainage.
    defaults to false.
    """

    log_mode: bool = False
    """
    log transform of parameters -- helps calibration search space exploration

    units: -
    bounds: bool

    when this is set to true, then all inputs for the van genuchten parameter alpha, saturated hydraulic conductivity, and the nonlinear reservoir parameter a must be input as their log values rather than the normal values.
    for example, if an saturated hydraulic conductivity of 0.
    1 cm/h is desired, then the input value must be -1 because 10^-1 = 0.1.
    the reasoning for this is that these parameters are not distributed normally in nature but rather are distributed log normally, such that simply sampling the parameter space normally during calibration will vastly undersample a big region of the parameter space in which we expect useful parameter sets to be.
    defaults to false.
    """

    a_slow: float = Field(default=0.0, gt=1e-8, lt=1e-1)
    """
    parameter for second nonlinear reservoir

    units: cm^(1-b) h^-1
    bounds: 1E-8 < a_slow < 1E-1

    this is exactly like the parameter a, except it corresponds to a second nonlinear reservoir, which was added to simulate cases where receding limbs have behaviors that can not easily be captured by one reservoir.
    defaults to 0.
    """

    b_slow: float = Field(default=0.0, gt=1e-2, lt=5)
    """
    parameter for second nonlinear reservoir

    units: -
    bounds: 0.01 < b_slow < 5

    this is exactly like the parameter b, except it corresponds to a second nonlinear reservoir, which was added to simulate cases where receding limbs have behaviors that can not easily be captured by one reservoir.
    defaults to 0.
    """

    frac_slow: float = Field(default=0.0, gte=0, le=1)
    """
    parameter for second nonlinear reservoir

    units: -
    bounds: 0.0 < frac_slow <= 1

    this describes the partitioning of water to the two reservoris, where the the input to the slow reservoir is equal to the total input for the nonlinear reservoirs times frac_slow.
    note that either all or none of a_slow, b_slow, and frac_slow must be specified.
    if none are specified then the model will not simulate a second nonlinear reservoir.
    defaults to 0.
    """

    @override
    def to_ini_str(self) -> str:
        data = self.dict(by_alias=True, exclude_none=True, exclude_unset=True)
        return self._to_ini_str(data)

    class Config(serializer_deserializer.IniSerializerDeserializer.Config):
        no_section_headers: bool = True
        # extra space is not accounted for
        # https://github.com/NOAA-OWP/LGAR-C/blob/5aad0f501faba8cb53c6692787c96cba04489eaa/src/lgar.cxx#L190
        space_around_delimiters: bool = False
        field_type_serializers = {bool: lambda b: str(b).lower()}
        preserve_key_case: bool = True
