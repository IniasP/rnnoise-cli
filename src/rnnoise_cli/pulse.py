import os
import sys
from typing import List

import click
import pulsectl
import contextlib
import pickle

pulse = pulsectl.Pulse("rnnoise_cli")
LADSPA_PLUGIN_PATH = os.path.join(sys.prefix, "rnnoise_cli", "librnnoise_ladspa.so")
CACHE_PATH = os.path.join(os.environ["HOME"], ".cache", "rnnoise_cli")
LOADED_MODULES_PATH = os.path.join(CACHE_PATH, "loaded_modules.pickle")


class NoneLoadedException(Exception):
    pass


class PulseInterface:
    @staticmethod
    def cli_command(command: List[str]):
        with contextlib.closing(pulsectl.connect_to_cli()) as s:
            for c in command:
                s.write(c + "\n")

    @staticmethod
    def load_modules(mic_name: str, mic_rate: int, control_level: int, verbose: bool):
        # TODO: add stereo mic support

        # Try to read previously loaded modules
        try:
            with open(LOADED_MODULES_PATH, "rb") as file:
                loaded = pickle.load(file)
        except FileNotFoundError:
            loaded: List[int] = []

        null_sink_opts = (
            "sink_name=rnnoise_mic_denoised_out "
            f"rate={mic_rate} "
            "sink_properties=\"device.description='RNNoise Null Sink'\""
        )
        null_sink_index = pulse.module_load("module-null-sink", null_sink_opts)
        loaded.append(null_sink_index)
        if verbose:
            click.echo(f"Loaded module-null-sink with index {null_sink_index} and options: {null_sink_opts}")

        ladspa_sink_opts = (
            "sink_name=rnnoise_mic_raw_in "
            "sink_master=rnnoise_mic_denoised_out "
            "label=noise_suppressor_mono "
            f"plugin=\"{LADSPA_PLUGIN_PATH}\" "
            f"control={control_level} "
            "sink_properties=\"device.description='RNNoise LADSPA Sink'\""
        )
        ladspa_sink_index = pulse.module_load("module-ladspa-sink", ladspa_sink_opts)
        loaded.append(ladspa_sink_index)
        if verbose:
            click.echo(f"Loaded module-ladspa-sink with index {ladspa_sink_index} and options: {ladspa_sink_opts}")

        loopback_opts = (
            f"source={mic_name} "
            "sink=rnnoise_mic_raw_in "
            "channels=1 "
            "source_dont_move=true "
            "sink_dont_move=true"
        )
        loopback_index = pulse.module_load("module-loopback", loopback_opts)
        loaded.append(loopback_index)
        if verbose:
            click.echo(f"Loaded module-loopback with index {loopback_index} and options: {loopback_opts}")

        remap_source_opts = (
            "master=rnnoise_mic_denoised_out.monitor "
            "source_name=rnnoise_denoised "
            "channels=1 "
            "source_properties=\"device.description='RNNoise Denoised Microphone'\""
        )
        remap_source_index = pulse.module_load("module-remap-source", remap_source_opts)
        loaded.append(remap_source_index)
        if verbose:
            click.echo(f"Loadied module-remap-source with index {remap_source_index} and options: {remap_source_opts}")

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

    @staticmethod
    def unload_modules(verbose: bool = False, modules: List[int] = None):
        """
        Raises NoneLoadedException if `modules` is None and it doesn't find anything to unload.
        """
        if modules is None:
            try:
                with open(LOADED_MODULES_PATH, "rb") as file:
                    modules = pickle.load(file)
            except FileNotFoundError:
                raise NoneLoadedException

        if not modules:
            raise NoneLoadedException
        else:
            for index in modules:
                try:
                    pulse.module_unload(index)
                    if verbose:
                        click.echo(f"Unloaded module {index}.")
                except pulsectl.pulsectl.PulseOperationFailed:
                    # The module was already unloaded for some reason.
                    pass

        try:
            os.remove(LOADED_MODULES_PATH)
        except FileNotFoundError:
            pass

    @staticmethod
    def get_input_devices() -> list:
        return pulse.source_list()

    @staticmethod
    def get_default_input_device():
        return PulseInterface.get_device_by_name(pulse.server_info().default_source_name)

    @staticmethod
    def get_device_by_name(name: str):
        try:
            return next((s for s in pulse.source_list() if s.name == name))
        except StopIteration:
            raise ValueError

    @staticmethod
    def get_device_by_num(num: int):
        try:
            return next((s for s in pulse.source_list() if s.index == num))
        except StopIteration:
            raise ValueError

    @staticmethod
    def rnn_is_loaded():
        """
        Check whether the plugin is loaded.
        This is more of a heuristic than something dependable.
        Checks if the pickle contains loaded modules and if a source with name "rnnoise_denoised" exists.
        The latter check is useful because after a reboot while activated, the modules are reset,
        which would lead to a module being present in the pickle file but not actually activated.
        """
        try:
            with open(LOADED_MODULES_PATH, "rb") as file:
                loaded = pickle.load(file)
                return loaded != [] and any(s.name == "rnnoise_denoised" for s in pulse.source_list())
        except FileNotFoundError:
            return False
