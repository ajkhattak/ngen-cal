from __future__ import annotations

import subprocess
import pandas as pd # type: ignore
import json
import shutil
from math import log
import numpy as np # type: ignore
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from functools import partial
from multiprocessing import pool
from ngen.cal.utils import pushd
if TYPE_CHECKING:
    from ngen.cal import Adjustable, Evaluatable
    from ngen.cal.agent import Agent
    from datetime import datetime


def _objective_func(simulated_hydrograph, observed_hydrograph, objective, eval_range: tuple[datetime, datetime] | None = None):
    df = pd.merge(simulated_hydrograph, observed_hydrograph, left_index=True, right_index=True)
    if eval_range:
        df = df.loc[eval_range[0]:eval_range[1]]
    if df.empty:
        print("WARNING: Cannot compute objective function, do time indicies align?")
        if eval_range:
            print(f"\teval range: [{eval_range[0]!s} : {eval_range[1]!s}]")
        print(f"\tsim interval: [{simulated_hydrograph.index.min()!s} : {simulated_hydrograph.index.max()!s}]")
        print(f"\tobs interval: [{observed_hydrograph.index.min()!s} : {observed_hydrograph.index.max()!s}]")
    #Evaluate custom objective function providing simulated, observed series
    return objective(df['obs_flow'], df['sim_flow'])

def _execute(meta: Agent):
    """
        Execute a model run defined by the calibration meta cmd
    """
    if meta.job.log_file is None:
        subprocess.check_call(meta.cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True, cwd=meta.job.workdir)
    else:
        with open(meta.job.log_file, 'a+') as log_file:
            subprocess.check_call(meta.cmd, stdout=log_file, stderr=log_file, shell=True, cwd=meta.job.workdir)

def _evaluate(i: int, calibration_object: Evaluatable, info=False) -> float:
    """
        Performs the evaluation logic of a calibration step
    """

    #read output and calculate objective_func
    score =  _objective_func(calibration_object.output, calibration_object.observed, calibration_object.objective, calibration_object.evaluation_range)
    #update meta info based on latest score and write some log files
    calibration_object.update(i, score, log=True)
    if info:
        print(f"Current score {score}\nBest score {calibration_object.best_score}")
        print(f"Best parameters at iteration {calibration_object.best_params}")
    return score

def dds_update(iteration: int, inclusion_probability: float, calibration_object: Adjustable, agent: Agent):
    """_summary_

    Args:
        iteration (int): _description_
    """

    print( f"inclusion probability: {inclusion_probability}" )
    #select a random subset of variables to modify
    # see Figure 1 in https://doi.org/10.1029/2005WR004723
    # Figure 1. Step 3.2
    dv_mask = np.random.binomial(1, inclusion_probability, len(calibration_object.variables)).astype("bool")
    neighborhood = calibration_object.variables[dv_mask]
    # Figure 1. Step 3.3
    if neighborhood.empty:
        neighborhood = calibration_object.variables.sample(n=1)
    print( f"neighborhood: {neighborhood}" )
    #Copy the best parameter values so far into the next iterations parameter list
    calibration_object.df[str(iteration)] = calibration_object.df[agent.best_params]
    #print( data.calibration_df )
    for n in neighborhood:
        #permute the variables in neighborhood
        #using a random normal sample * sigma, sigma = 0.2*(max-min)
        #print(n, meta.best_params)
        # Figure 1. Step 4.1
        new = calibration_object.df.loc[n, agent.best_params] + calibration_object.df.loc[n, 'sigma']*np.random.normal(0,1)
        lower =  calibration_object.df.loc[n, 'min']
        upper = calibration_object.df.loc[n, 'max']
        #print( new )
        #print( lower )
        #print( upper )
        # Figure 1. Step 4.2
        if new < lower:
            new = lower + (lower - new)
            if new > upper:
                new = lower
        # Figure 1. Step 4.3
        elif new > upper:
            new = upper - (new - upper)
            if new < lower:
                new = upper
        calibration_object.df.loc[n, str(iteration)] = new
    """
        At this point, we need to re-run cmd with the new parameters assigned correctly and evaluate the objective function
    """
    #Update the meta info and prepare for next iteration
    #Pass the parameter and interation columns of the object we are calibrating to the update function
    agent.update_config(
        iteration,
        calibration_object.parameters_for_iteration(iteration),
        calibration_object.id,
    )


def dds(start_iteration: int, iterations: int,  calibration_object: Evaluatable, agent: Agent):
    """
    """
    if iterations < 2:
        raise(ValueError("iterations must be >= 2"))
    if start_iteration > iterations:
        raise(ValueError("start_iteration must be <= iterations"))

    init = start_iteration - 1 if start_iteration > 0 else start_iteration
    # Figure 1. Step 1.1
    neighborhood_size = agent.parameters.get('neighborhood', 0.2)

    # Figure 1. Step 4.1
    #precompute sigma for each variable based on neighborhood_size and bounds
    calibration_object.df['sigma'] = neighborhood_size*(calibration_object.df['max'] - calibration_object.df['min'])
    agent.update_config(
        init,
        calibration_object.parameters_for_iteration(init),
        calibration_object.id,
    )

    #Produce the baseline simulation output
    if start_iteration == 0:
        if calibration_object.output is None:
            #We are starting a new calibration and do not have an initial output state to evaluate, compute it
            #Need initial states  (iteration 0) to start DDS loop
            print(f"Running {agent.cmd} to produce initial simulation")
            agent.update_config(
                start_iteration,
                calibration_object.parameters_for_iteration(start_iteration),
                calibration_object.id,
            )
            _execute(agent)
        with pushd(agent.job.workdir):
            _evaluate(0, calibration_object, info=True)
        calibration_object.check_point(0, agent.job)
        start_iteration += 1

    for i in range(start_iteration, iterations+1):
        #Calculate probability of inclusion
        inclusion_probability = 1 - log(i)/log(iterations)
        dds_update(i, inclusion_probability, calibration_object, agent)
        #Run cmd Again...
        print(f"Running {agent.cmd} for iteration {i}")
        _execute(agent)
        with pushd(agent.job.workdir):
            _evaluate(i, calibration_object, info=True)
        calibration_object.check_point(i, agent.job)

def dds_set(start_iteration: int, iterations: int, agent: Agent):
    """
        DDS search that applies to a set of calibration objects.

        This works by giving each object a parameter space, but allows a single execution
        step to happen each iteration, and then each object in the set can be adjusted independently
        and then evaluated as a whole.

        Tolson, B. A., and C. A. Shoemaker (2007), Dynamically dimensioned
        search algorithm for computationally efficient watershed model
        calibration, Water Resour. Res., 43, W01413, doi:10.1029/2005WR004723.V

        Figure 1 in Tolson & Shoemaker 2007 used as reference for implementation.
    """
    # TODO I think the can ultimately be refactored and merged with dds, there only a couple very
    # minor differenes in this implementation, and I think those can be abstrated away
    # by carefully crafting sets and adjustables before this function is ever reached.
    if iterations < 2:
        raise(ValueError("iterations must be >= 2"))
    if start_iteration > iterations:
        raise(ValueError("start_iteration must be <= iterations"))

    # Figure 1
    neighborhood_size = agent.parameters.get('neighborhood', 0.2)

    calibration_sets = agent.model.adjustables
    init = start_iteration - 1 if start_iteration > 0 else start_iteration
    for calibration_set in calibration_sets:
        for calibration_object in calibration_set.adjustables:
            #precompute sigma for each variable based on neighborhood_size and bounds
            calibration_object.df['sigma'] = neighborhood_size*(calibration_object.df['max'] - calibration_object.df['min'])
            #TODO optimize by passing the set and iterating in update, then only have to write once to file
            agent.update_config(
                init,
                calibration_object.parameters_for_iteration(init),
                calibration_object.id,
            )

        #Produce the baseline simulation output
        if start_iteration == 0:
            # NOTE: this is gross... im sorry.
            # `calibration_set.output` side effects and calls the
            # `ngen_cal_model_output` plugin hook so it needs to be run
            # _inside_ the working dir b.c. plugins could expect data relative
            # to workdir. but `_execute` expects to be run from the parent dir.
            exec = False
            with pushd(agent.job.workdir):
                # plugins could expect data relative to workdir
                if calibration_set.output is None:
                    #We are starting a new calibration and do not have an initial output state to evaluate, compute it
                    #Need initial states  (iteration 0) to start DDS loop
                    print(f"Running {agent.cmd} to produce initial simulation")
                    exec = True
            if exec:
                _execute(agent)
            with pushd(agent.job.workdir):
                _evaluate(0, calibration_set, info=True)
            calibration_set.check_point(0, agent.job)
            start_iteration += 1

        for i in range(start_iteration, iterations+1):
            #Calculate probability of inclusion
            inclusion_probability = 1 - log(i)/log(iterations)
            for calibration_object in calibration_set.adjustables:
                dds_update(i, inclusion_probability, calibration_object, agent)
            #Run cmd Again...
            print(f"Running {agent.cmd} for iteration {i}")
            _execute(agent)
            with pushd(agent.job.workdir):
                _evaluate(i, calibration_set, info=True)
            calibration_set.check_point(i, agent.job)

@dataclass(frozen=True)
class ParticleResult:
    """Result from one particle simulation in one PSO generation."""

    generation: int
    particle: int
    score: float
    cost: float
    position: list[float]
    workdir: str


def _score_to_cost(calibration_object: Evaluatable, score: float) -> float:
    """Convert an ngen-cal objective score into a minimization cost."""
    target = calibration_object.eval_params.target
    if target == "min":
        return score
    if target == "max":
        return -score
    return abs(score - float(target))


def compute(calibration_index: int, generation: int, input) -> ParticleResult:
    """Run and evaluate one particle using its own agent and model state."""
    particle, params, agent = input
    calibration_object = agent.model.adjustables[calibration_index]

    calibration_object.df[str(generation)] = params
    with pushd(agent.job.workdir):
        agent.update_config(
            generation,
            calibration_object.parameters_for_iteration(generation),
            calibration_object.id,
        )
        _execute(agent)
        score = _evaluate(generation, calibration_object)
        calibration_object.check_point(generation, agent.job)

    return ParticleResult(
        generation=generation,
        particle=particle,
        score=float(score),
        cost=float(_score_to_cost(calibration_object, score)),
        position=[float(value) for value in params],
        workdir=str(agent.job.workdir),
    )


class PsoTracker:
    """Track swarm-global progress outside particle worker processes."""

    def __init__(self, path: Path, snapshot_dir: Path | None = None):
        self.path = path
        self.snapshot_dir = snapshot_dir
        self.history_path = path.with_name("pso_global_best_log.txt")
        self.generation = 0
        self.best: ParticleResult | None = None
        self.best_history: list[ParticleResult] = []

    def update(self, results: list[ParticleResult]) -> None:
        if not results:
            raise RuntimeError("PSO generation returned no particle results")

        generation_best = min(results, key=lambda result: result.cost)
        improved = self.best is None or generation_best.cost < self.best.cost
        if improved:
            self.best = generation_best
            self._snapshot_best()

        assert self.best is not None
        self.best_history.append(self.best)
        self.generation += 1
        if not self.history_path.exists():
            self.history_path.write_text(
                "generation,best_score_so_far,best_cost_so_far,"
                "best_particle,best_worker_dir\n"
            )
        with self.history_path.open("a+") as file:
            file.write(
                f"{self.generation - 1}, {self.best.score}, "
                f"{self.best.cost}, {self.best.particle}, "
                f"{self.best.workdir}\n"
            )
        self.path.write_text(
            json.dumps(
                {
                    "completed_generations": self.generation,
                    "global_best": asdict(self.best),
                    "particles": [asdict(result) for result in results],
                },
                indent=2,
            )
        )

    def _snapshot_best(self) -> None:
        """Preserve the current global-best particle workspace."""
        if self.snapshot_dir is None or self.best is None:
            return

        if self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir)
        shutil.copytree(self.best.workdir, self.snapshot_dir)


def cost_func(
    calibration_index: int,
    agents: list[Agent],
    process_pool: pool.Pool,
    tracker: PsoTracker,
    params,
):
    """Evaluate every position supplied by pyswarms exactly once."""
    if len(params) != len(agents):
        raise ValueError(
            f"PSO supplied {len(params)} positions for {len(agents)} agents"
        )

    jobs = zip(range(len(agents)), params, agents)
    func = partial(compute, calibration_index, tracker.generation)
    results = list(process_pool.imap(func, jobs))
    tracker.update(results)
    return np.asarray([result.cost for result in results], dtype=float)


def _write_global_best_history_checkpoint(
    calibration_object: Adjustable,
    best_history: list[ParticleResult],
    output_dir: Path,
) -> None:
    """Write a DDS-like PSO best-so-far parameter history."""
    if not best_history:
        raise RuntimeError("No PSO global-best history is available")

    state = calibration_object.df.copy()
    for generation, result in enumerate(best_history):
        state[str(generation)] = result.position
    state.to_parquet(output_dir / calibration_object.check_point_file)


def _load_pso_seed(calibration_object: Adjustable, initialization: dict) -> tuple[np.ndarray, str]:
    """Load a known-best parameter position or fall back to configured init values."""
    initial = calibration_object.df["0"].to_numpy(dtype=float)
    best_path = initialization.get("best_path")
    if best_path is None:
        return initial, "calibration init values"

    path = Path(best_path).expanduser()
    try:
        if path.is_dir():
            state_files = sorted(path.glob("*_parameter_df_state.parquet"))
            if not state_files:
                raise FileNotFoundError(f"no parameter state parquet found in {path}")
            state_path = state_files[0]
            best_params_path = path / "best_params.txt"
        else:
            state_path = path
            best_params_path = path.parent / "best_params.txt"

        state = pd.read_parquet(state_path)
        if best_params_path.exists():
            lines = best_params_path.read_text().splitlines()
            if len(lines) < 2:
                raise ValueError(f"invalid best parameters file: {best_params_path}")
            best_column = lines[1].strip()
        elif "global_best" in state:
            best_column = "global_best"
        else:
            raise FileNotFoundError(
                f"no best_params.txt or global_best column found for {state_path}"
            )

        if best_column not in state:
            raise KeyError(f"best parameter column {best_column!r} not found in {state_path}")

        source = {
            (str(row["model"]), str(row["param"])): float(row[best_column])
            for _, row in state.iterrows()
        }

        seed = np.asarray(
            [
                source[(str(row["model"]), str(row["param"]))]
                for _, row in calibration_object.df.iterrows()
            ],
            dtype=float,
        )

        return seed, str(state_path)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        print(
            f"WARNING: Unable to load PSO best position from {path}: {exc}. "
            "Using calibration init values."
        )
        return initial, "calibration init values"


def _pso_initial_positions(
    calibration_object: Adjustable,
    num_particles: int,
    bounds: tuple[np.ndarray, np.ndarray],
    initialization: dict | None = None,
) -> np.ndarray:
    """Create a diverse swarm containing an exact and nearby warm-start seed."""
    initialization = initialization or {}
    nearby_fraction = float(initialization.get("nearby_fraction", 0.5))
    noise_fraction = float(initialization.get("noise_fraction", 0.1))
    if not 0 <= nearby_fraction <= 1:
        raise ValueError("PSO initialization.nearby_fraction must be between 0 and 1")
    if noise_fraction < 0:
        raise ValueError("PSO initialization.noise_fraction must be >= 0")

    lower, upper = bounds
    seed, source = _load_pso_seed(calibration_object, initialization)
    if np.any(seed < lower) or np.any(seed > upper):
        print(
            f"WARNING: PSO seed from {source} exceeds parameter bounds; "
            "clipping seed values to bounds."
        )
        seed = np.clip(seed, lower, upper)

    positions = np.random.uniform(
        lower,
        upper,
        size=(num_particles, len(seed)),
    )
    positions[0] = seed

    nearby_particles = min(
        num_particles,
        max(1, int(round(num_particles * nearby_fraction))),
    )
    if nearby_particles > 1:
        noise = np.random.normal(
            loc=0.0,
            scale=noise_fraction * (upper - lower),
            size=(nearby_particles - 1, len(seed)),
        )
        positions[1:nearby_particles] = np.clip(seed + noise, lower, upper)

    print(
        f"Initializing PSO from {source}: 1 exact seed, "
        f"{nearby_particles - 1} nearby particles, "
        f"{num_particles - nearby_particles} random particles"
    )
    return positions


class _LinearOptionsSchedule:
    """Linearly vary PSO options from their start values to configured end values."""

    def __init__(self, end_options: dict[str, float], log_path: Path | None = None):
        self.end_options = end_options
        self.log_path = log_path

    def __call__(self, start_options: dict[str, float], **kwargs) -> dict[str, float]:
        iteration = kwargs["iternow"]
        iterations = kwargs["itermax"]
        factor = iteration / iterations
        options = dict(start_options)
        for name, start in start_options.items():
            if name in self.end_options:
                end = self.end_options[name]
                options[name] = start - factor * (start - end)

        if self.log_path is not None:
            if not self.log_path.exists():
                self.log_path.write_text("iteration,w,c1,c2\n")
            with self.log_path.open("a+") as file:
                file.write(
                    f"{iteration}, {options.get('w')}, "
                    f"{options.get('c1')}, {options.get('c2')}\n"
                )
        return options


def _configure_pso_options_schedule(agent: Agent, optimizer) -> None:
    schedule = agent.parameters.get("options_schedule")
    if not schedule:
        return
    if schedule.get("type", "linear") != "linear":
        raise ValueError("PSO options_schedule.type must be 'linear'")

    end_options = schedule.get("end", {})
    if not end_options:
        raise ValueError("PSO options_schedule.end must define one or more of w, c1, c2")

    valid = {"w", "c1", "c2"}
    unknown = set(end_options) - valid
    if unknown:
        raise ValueError(
            "PSO options_schedule.end contains unsupported options: "
            f"{', '.join(sorted(unknown))}"
        )

    optimizer.oh = _LinearOptionsSchedule(
        {name: float(value) for name, value in end_options.items()},
        agent.workdir / "pso_options_log.txt",
    )


def pso_search(start_iteration: int, iterations: int, agent: Agent) -> None:
    """Search for a uniform parameter set using global-best PSO.

    Each particle owns an isolated Agent and ngen worker directory. Particle
    simulations may run concurrently, while global-best state is maintained
    only by the parent process.
    """
    try:
        import pyswarms as ps
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PSO requires pyswarms. Install ngen.cal with the 'pso' extra."
        ) from exc

    if start_iteration != 0:
        raise NotImplementedError("Restarting PSO is not currently supported")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    if len(agent.model.adjustables) != 1:
        raise ValueError("PSO currently requires one uniform calibration set")

    num_particles = int(agent.parameters.get("particles", 4))
    if num_particles < 2:
        raise ValueError("PSO requires at least two particles")
    pool_size = agent.parameters.get("pool", 1)
    pool_size = int(pool_size)
    if pool_size < 1:
        raise ValueError("PSO pool must be >= 1")
    pool_size = min(pool_size, num_particles)

    print(f"Running PSO with {num_particles} particles using {pool_size} processes")
    agents = [agent] + [agent.duplicate() for _ in range(num_particles - 1)]
    default_options = {"c1": 1.5, "c2": 1.5, "w": 0.5}
    options = agent.parameters.get("options", default_options)

    tracker = PsoTracker(
        agent.workdir / "pso_progress.json",
        agent.workdir / "pso_global_best",
    )

    for calibration_index, calibration_object in enumerate(agent.model.adjustables):
        bounds = calibration_object.bounds
        bounds = (bounds[0].values, bounds[1].values)

        initialization = agent.parameters.get("initialization", {})
        initial_positions = _pso_initial_positions(
            calibration_object,
            num_particles,
            bounds,
            initialization,
        )
        optimizer = ps.single.GlobalBestPSO(
            n_particles=num_particles,
            dimensions=len(calibration_object.df),
            options=options,
            bounds=bounds,
            init_pos=initial_positions,
        )
        _configure_pso_options_schedule(agent, optimizer)

        # pyswarms multiprocessing is intentionally disabled so each particle
        # position remains paired with its isolated ngen Agent and workdir.
        with pool.Pool(pool_size) as process_pool:
            cf = partial(
                cost_func,
                calibration_index,
                agents,
                process_pool,
                tracker,
            )
            cost, position = optimizer.optimize(
                cf,
                iters=iterations,
                n_processes=None,
            )

        calibration_object.df.loc[:, "global_best"] = position
        calibration_object.df[str(iterations)] = position
        agent.update_config(
            iterations,
            calibration_object.parameters_for_iteration(iterations),
            calibration_object.id,
        )
        assert tracker.best is not None
        with pushd(agent.job.workdir):
            calibration_object.update(iterations, tracker.best.score, log=True)
        calibration_object.df.to_parquet(
            agent.job.workdir / calibration_object.check_point_file
        )
        if tracker.snapshot_dir is not None:
            _write_global_best_history_checkpoint(
                calibration_object,
                tracker.best_history,
                tracker.snapshot_dir,
            )

        print(
            f"Best score {tracker.best.score} "
            f"(minimization cost {cost}) from particle "
            f"{tracker.best.particle} in generation {tracker.best.generation}"
        )
        print(
            calibration_object.df[["param", "global_best"]].set_index("param")
        )
