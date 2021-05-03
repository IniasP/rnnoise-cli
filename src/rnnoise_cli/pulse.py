import os
import sys
import contextlib
import pickle
from typing import List, Dict
from dataclasses import dataclass

import click
import pulsectl

LADSPA_PLUGIN_PATH = os.path.join(sys.prefix, "rnnoise_cli", "librnnoise_ladspa.so")
CACHE_PATH = os.path.join(os.environ["HOME"], ".cache", "rnnoise_cli")
LOADED_MODULES_PATH = os.path.join(CACHE_PATH, "load_info.pickle")


class NoneLoadedException(Exception):
    pass


class NotActivatedException(Exception):
    pass


@dataclass
class LoadParams:
    mic_name: str
    mic_rate: int
    control: int


class LoadInfo:
    params: LoadParams = None
    modules: Dict[str, int] = {}

    def __init__(self, params: LoadParams, modules: Dict[str, int]):
        self.params = params
        self.modules = modules

    @classmethod
    def from_pickle(cls, pickle_path=LOADED_MODULES_PATH) -> 'LoadInfo':
        """
        Raises FileNotFoundError if path doesn't exist
        or ValueError if the file is invalid.
        """
        with open(pickle_path, "rb") as file:
            result = pickle.load(file)
        if not isinstance(result, cls):
            raise ValueError

        return result

    def write_pickle(self, pickle_path=LOADED_MODULES_PATH):
        dirname = os.path.dirname(pickle_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(LOADED_MODULES_PATH, 'wb') as file:
            pickle.dump(self, file, protocol=pickle.HIGHEST_PROTOCOL)


class PulseInterface:
    pulse = pulsectl.Pulse("rnnoise_cli")
    null_sink_name = "rnnoise_mic_denoised_out"
    ladspa_sink_name = "rnnoise_mic_raw_in"
    loopback_key = "loopback"
    remap_source_name = "rnnoise_denoised"

    @staticmethod
    def cli_command(command: List[str]):
        with contextlib.closing(pulsectl.connect_to_cli()) as s:
            for c in command:
                s.write(c + "\n")

    @staticmethod
    def get_loaded_modules() -> Dict[str, int]:
        try:
            with open(LOADED_MODULES_PATH, "rb") as file:
                loaded = pickle.load(file)
        except FileNotFoundError:
            loaded = {}
        if not isinstance(loaded, dict):
            loaded = {}
        return loaded

    @staticmethod
    def write_loaded_modules(loaded: Dict[str, int]):
        if not os.path.exists(CACHE_PATH):
            os.makedirs(CACHE_PATH)
        with open(LOADED_MODULES_PATH, 'wb') as file:
            pickle.dump(loaded, file, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load_modules(cls, load_params: LoadParams, verbose: bool) -> LoadInfo:
        # TODO: add stereo mic support

        loaded = {}

        null_sink_opts = (
            f"sink_name={cls.null_sink_name} "
            f"rate={load_params.mic_rate} "
            "sink_properties=\"device.description='RNNoise Null Sink'\""
        )
        loaded[cls.null_sink_name] = cls.pulse.module_load("module-null-sink", null_sink_opts)
        if verbose:
            click.echo(f"Loaded module-null-sink {cls.null_sink_name} "
                       f"with index {loaded[cls.null_sink_name]} "
                       f"and options: {null_sink_opts}")

        ladspa_sink_opts = (
            f"sink_name={cls.ladspa_sink_name} "
            f"sink_master={cls.null_sink_name} "
            "label=noise_suppressor_mono "
            f"plugin=\"{LADSPA_PLUGIN_PATH}\" "
            f"control={load_params.control} "
            "sink_properties=\"device.description='RNNoise LADSPA Sink'\""
        )
        loaded[cls.ladspa_sink_name] = cls.pulse.module_load("module-ladspa-sink", ladspa_sink_opts)
        if verbose:
            click.echo(f"Loaded module-ladspa-sink {cls.ladspa_sink_name} "
                       f"with index {loaded[cls.ladspa_sink_name]} "
                       f"and options: {ladspa_sink_opts}")

        loopback_opts = (
            f"source={load_params.mic_name} "
            f"sink={cls.ladspa_sink_name} "
            "channels=1 "
            "source_dont_move=true "
            "sink_dont_move=true"
        )
        loaded[cls.loopback_key] = cls.pulse.module_load("module-loopback", loopback_opts)
        if verbose:
            click.echo(f"Loaded module-loopback "
                       f"with index {loaded[cls.loopback_key]} "
                       f"and options: {loopback_opts}")

        remap_source_opts = (
            f"master={cls.null_sink_name}.monitor "
            f"source_name={cls.remap_source_name} "
            "channels=1 "
            "source_properties=\"device.description='RNNoise Denoised Microphone'\""
        )
        loaded[cls.remap_source_name] = cls.pulse.module_load("module-remap-source", remap_source_opts)
        if verbose:
            click.echo(f"Loaded module-remap-source {cls.remap_source_name} "
                       f"with index {loaded[cls.remap_source_name]} "
                       f"and options: {remap_source_opts}")

        # Set default
        cls.pulse.source_default_set(cls.remap_source_name)

        load_info = LoadInfo(load_params, loaded)
        load_info.write_pickle()
        return load_info

    @staticmethod
    def get_loaded_modules() -> Dict[str, int]:
        try:
            return LoadInfo.from_pickle().modules
        except (ValueError, FileNotFoundError):
            return {}

        # Write loaded modules for proper unloading
        if not os.path.exists(CACHE_PATH):
            os.makedirs(CACHE_PATH)
        with open(LOADED_MODULES_PATH, 'wb') as file:
            pickle.dump(loaded, file, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def unload_modules_all():
        try:
            os.remove(LOADED_MODULES_PATH)
        except FileNotFoundError:
            pass
        PulseInterface.cli_command(
            [
                "unload-module module-loopback",
                "unload-module module-null-sink",
                "unload-module module-ladspa-sink",
                "unload-module module-remap-source",
            ]
        )

    @classmethod
    def unload_modules(cls, modules: Dict[str, int] = None, verbose: bool = False):
        """
        Raises NoneLoadedException if `modules` is None and it doesn't find anything to unload.
        """
        if modules is None:
            modules = cls.get_loaded_modules()

        if not modules:
            raise NoneLoadedException
        else:
            for name, index in modules.items():
                try:
                    cls.pulse.module_unload(index)
                    if verbose:
                        click.echo(f"Unloaded module {name} ({index}).")
                except pulsectl.pulsectl.PulseOperationFailed:
                    # The module was already unloaded for some reason.
                    pass

        try:
            os.remove(LOADED_MODULES_PATH)
        except FileNotFoundError:
            pass

    @classmethod
    def get_input_devices(cls) -> list:
        return cls.pulse.source_list()

    @classmethod
    def get_default_input_device(cls):
        return cls.get_source_by_name(cls.pulse.server_info().default_source_name)

    @classmethod
    def get_source_by_name(cls, name: str):
        try:
            return cls.pulse.get_source_by_name(name)
        except pulsectl.PulseIndexError:
            raise ValueError

    @classmethod
    def get_source_by_num(cls, num: int):
        try:
            return next((s for s in cls.pulse.source_list() if s.index == num))
        except StopIteration:
            raise ValueError

    @classmethod
    def rnn_is_loaded(cls):
        """
        Check whether the plugin is loaded.
        This is more of a heuristic than something dependable.
        Checks if the pickle contains loaded modules and if a source with name "rnnoise_denoised" exists.
        The latter check is useful because after a reboot while activated, the modules are reset,
        which would lead to a module being present in the pickle file but not actually activated.
        """
        loaded = cls.get_loaded_modules()
        return bool(loaded) and any(s.name == cls.remap_source_name for s in cls.pulse.source_list())
