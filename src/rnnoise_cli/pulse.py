import os
import sys
from typing import List

import click
import pulsectl
import contextlib
import pickle
from .exceptions import NoneLoadedException

pulse = pulsectl.Pulse("rnnoise_cli")
LADSPA_PLUGIN_PATH = os.path.join(sys.prefix, "rnnoise_cli", "librnnoise_ladspa.so")
CACHE_PATH = os.path.join(os.environ["HOME"], ".cache", "rnnoise_cli")
LOADED_MODULES_PATH = os.path.join(CACHE_PATH, "loaded_modules.pickle")


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
            "sink_name=mic_denoised_out "
            f"rate={mic_rate} "
            "sink_properties=\"device.description='RNNoise Null Sink'\""
        )
        if verbose:
            click.echo(f"Loading module-null-sink with options: {null_sink_opts}")
        loaded.append(pulse.module_load("module-null-sink", null_sink_opts))

        ladspa_sink_opts = (
            "sink_name=mic_raw_in "
            "sink_master=mic_denoised_out "
            "label=noise_suppressor_mono "
            f"plugin=\"{LADSPA_PLUGIN_PATH}\" "
            f"control={control_level} "
            "sink_properties=\"device.description='RNNoise LADSPA Sink'\""
        )
        if verbose:
            click.echo(f"Loading module-ladspa-sink with options: {ladspa_sink_opts}")
        loaded.append(pulse.module_load("module-ladspa-sink", ladspa_sink_opts))

        loopback_opts = (
            f"source={mic_name} "
            "sink=mic_raw_in "
            "channels=1 "
            "source_dont_move=true "
            "sink_dont_move=true"
        )
        if verbose:
            click.echo(f"Loading module-loopback with options: {loopback_opts}")
        loaded.append(pulse.module_load("module-loopback", loopback_opts))

        remap_source_opts = (
            "master=mic_denoised_out.monitor "
            "source_name=denoised "
            "channels=1 "
            "source_properties=\"device.description='RNNoise Denoised Microphone'\""
        )
        if verbose:
            click.echo(f"Loading module-remap-source with options: {remap_source_opts}")
        loaded.append(pulse.module_load("module-remap-source", remap_source_opts))

        if verbose:
            click.echo(f"Loaded modules: {loaded}")
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
    def unload_modules():
        """
        Raises NoneLoadedException if it doesn't find anything to unload.
        """
        try:
            with open(LOADED_MODULES_PATH, "rb") as file:
                loaded = pickle.load(file)
        except FileNotFoundError:
            raise NoneLoadedException

        if not loaded:
            raise NoneLoadedException
        else:
            for index in loaded:
                try:
                    pulse.module_unload(index)
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
        return any((s.name == "denoised" for s in pulse.source_list()))
