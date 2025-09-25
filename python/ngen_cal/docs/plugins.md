# What is a plugin?

`ngen.cal` plugins enable running code at specific points during a calibration experiment without modifying `ngen.cal`'s source code.

A plugin is a python class or module that _implements_ one or more of `ngen.cal`'s hook specifications.
`ngen.cal` hook specifications are function or method "specifications" that `ngen.cal` will call at certain life-cycle events during its execution.
For example, a plugin that implements the `ngen_cal_start() -> None` hook specification will have its `ngen_cal_start()` _implementation_ called when `ngen.cal` first enters the calibration loop.

`ngen.cal` has 2 types of plugins: General plugins and Model Plugins.
The differences between the two are:
- The set of hook specifications they expose.
- Where they are configured in an `ngen.cal`'s configuration file.
- Model Plugins must be implemented as classes. General plugins can be either implemented as a module of functions or classes.

## Plugin Configuration

`ngen.cal` loads plugins during its startup process.
For `ngen.cal` to load a plugin, the plugin must be specified in the appropriate `ngen.cal` configuration section and importable by `ngen.cal`.
Both general and model plugin types are registered in an `ngen.cal` config using the plugin's fully qualified python `importlib` string path to the module or class.
General plugins are registered under the `general.plugins` section and model plugins are registered under the `model.plugins` section.

For example:
```yaml
general:
  plugins:
    - "ngen_cal_time_fn"
    - "ngen_cal_time_class.NgenCalTimer"
  plugin_settings:
    ngen_cal_time_fn:
        # any valid yaml
model:
  plugins:
    - "plugins.NgenCalLocalObs"
  plugin_settings:
    NgenCalLocalObs:
      # any valid yaml
      observation_file: "/var/data/usgs_obs.parquet"
```

Plugins that require additional configuration should utilize the `general.plugin_settings` or `model.plugin_settings` fields respectively.
See the plugin's documentation for required configuration settings.

> [!IMPORTANT]
> The fully qualified python `importlib` string path to the module / class must be given.
> If you are having issues with `ngen.cal` importing a plugin, you may need to add the plugin to Python's module search path.
> See Python's docs regarding the `PYTHONPATH` env variable for more information.


### Plugin Development

`ngen.cal`'s uses [`pluggy`](https://pluggy.readthedocs.io/en/stable/) behind the scenes to power plugins functionality.
It is **highly recommended** to see [`pluggy`'s](https://pluggy.readthedocs.io/en/stable/) documentation before you begin developing your plugin and to use as a reference during development.
In particular, plugin developers may be interested in these `pluggy` features:
- [call time ordering](https://pluggy.readthedocs.io/en/stable/#call-time-order)
- [wrappers](https://pluggy.readthedocs.io/en/stable/#wrappers)
- [first result only](https://pluggy.readthedocs.io/en/stable/#first-result-only)
- [exception handling](https://pluggy.readthedocs.io/en/stable/#exception-handling)
- [opt-in-arguments](https://pluggy.readthedocs.io/en/stable/#opt-in-arguments)

Additionally, many `ngen.cal` features are implemented using the plugin system.
Plugin developers may find internal plugin implementations useful as additional examples.

By convention, the name of plugin module's should start with `ngen_cal` or `ngen_cal_model` depending on the type of plugin.
Class plugins are encouraged to use the prefix `NgenCal` or `NgenCalModel` but this is not strictly required.
Similarly, plugins that required additional settings should use their class or module name as the as top level key in the `plugin_settings` dictionary.

> [!NOTE]
> All plugin functions and methods must be decorated with `ngen.cal.hookimpl` for `ngen.cal` to register them.
> See [`pluggy`](https://pluggy.readthedocs.io/en/stable/) docs for more information.


#### Class vs Module plugins

The most important difference between class and module plugins is how they are initialized.
Class based plugin instances are instantiated **without any arguments**.
Plugins that require extra setup or configuration should implement `ngen_cal_configure` or `ngen_cal_model_configure` accordingly.


#### General Hooks

<details>
<summary>hook specifications</summary>

```python
@hookspec
def ngen_cal_configure(config: General) -> None:
    """
    Called before calibration begins.
    This allow plugins to perform initial configuration.

    Plugins' configuration data should be provided using the
    `plugins_settings` field in the `ngen.cal` configuration file.
    By convention, the name of the plugin should be used as top level key in
    the `plugin_settings` dictionary.
    """
```


```python
@hookspec
def ngen_cal_start() -> None:
    """Called when first entering the calibration loop."""
```


```python
@hookspec
def ngen_cal_finish(exception: Exception | None) -> None:
    """
    Called after exiting the calibration loop.
    Plugin implementations are guaranteed to be called even if an exception is
    raised during the calibration loop.
    `exception` will be non-none if an exception was raised during calibration.
    """
```

</details>


#### Model Hooks

As noted above, model plugins **must be** implemented as class based plugins.

<details>
<summary>hook specifications</summary>

```python
@hookspec
def ngen_cal_model_configure(self, config: ModelExec) -> None:
    """
    Called before calibration begins.
    This allow plugins to perform initial configuration.

    Plugins' configuration data should be provided using the
    `plugins_settings` field in the `model` section of an `ngen.cal`
    configuration file.
    By convention, the name of the plugin should be used as top level key in
    the `plugin_settings` dictionary.
    """
```

```python
@hookspec(firstresult=True)
def ngen_cal_model_observations(
    self,
    nexus: Nexus,
    start_time: datetime,
    end_time: datetime,
    simulation_interval: pd.Timedelta,
) -> pd.Series:
    """
    Called during each calibration iteration to provide truth / observation
    values in the form of a pandas Series, indexed by time with a record
    every `simulation_interval`.
    The returned pandas Series should be in units of cubic meters per
    second.

    `nexus`: HY_Features Nexus
    `start_time`, `end_time`: inclusive simulation time range
    `simulation_interval`: time (distance) between simulation values
    """
```

```python
@hookspec(firstresult=True)
def ngen_cal_model_output(self, nexus: Nexus) -> pd.Series:
    """
    Called during each calibration iteration to provide the model output in
    the form of a pandas Series, indexed by time.
    Output series should be in units of cubic meters per second.
    """
```

```python
@hookspec
def ngen_cal_model_iteration_finish(self, iteration: int, info: JobMeta) -> None:
    """
    Called after each model iteration is completed and evaluated.
    And before the next iteration is configured and started.
    Currently called at the end of an Adjustable's check_point function
    which writes out calibration/parameter state data each iteration.

    Raise `ngen.cal.errors.StopEarly` to cancel further calibration iterations.
    Post-calibration validation will be conducted if configured.
    """
```

```python
@hookspec(firstresult=True)
def ngen_cal_model_validation_cmd(self, binary: str, args: str) -> tuple[str, str]:
    """
    Called before validation to override the command used for validation.
    A plugin should return a tuple of [binary: str, args: str].

    `binary` and `args` contain the values used for calibration.
    """
```

</details>


#### Example General Plugin

This example plugin tracks and reports the total execution time of an `ngen.cal` calibration experiment.
The same concepts shown here are directly translatable to an `ngen.cal` `model` plugin.

```python
# file: ngen_cal_time.py
from __future__ import annotations

from time import perf_counter
from ngen.cal import hookimpl

class Timer:
    @hookimpl
    def ngen_cal_start(self) -> None:
        """Called when first entering the calibration loop."""
        self.start = perf_counter()

    @hookimpl
    def ngen_cal_finish(self, exception: Exception | None) -> None:
        """Called after exiting the calibration loop."""
        if exception is not None:
            print(f"Exception: {exception} was raised during calibration")
        print(f"Calibration took: {perf_counter() - self.start}s")
```

Add the following section to an existing `ngen.cal` config to enable and register the plugin.
It may be required to add the directory containing the plugin to the `PYTHONPATH` env variable before running `ngen.cal` so Python can locate the plugin.

```yaml
general:
  plugins:
    - "ngen_cal_time.Timer"
```
