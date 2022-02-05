import contextlib
import importlib.resources
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

import click
import pulsectl

from .exceptions import *

CACHE_PATH = Path.home() / ".cache" / "rnnoise_cli"
LOADED_MODULES_PATH = Path(CACHE_PATH) / "load_info.pickle"


@dataclass
class LoadInfo:
    """
    Info on a loaded configuration that can be used to unload it.
    This is pickled to be able to remember it between invocations of the application.
    It has to be checked, since the plugin can be unloaded outside this application, e.g. by rebooting.
    """
    device: pulsectl.PulseSourceInfo
    control: int
    modules: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_pickle(cls, pickle_path: Path = LOADED_MODULES_PATH) -> 'LoadInfo':
        """
        Args:
            pickle_path:
                Path to a pickle file.
        Raises:
            FileNotFoundError:
                The path does not exist.
            ValueError:
                The file is invalid.
        """
        with open(pickle_path, "rb") as file:
            result = pickle.load(file)
        if not isinstance(result, cls):
            raise ValueError

        return result

    def write_pickle(self, pickle_path: Path = LOADED_MODULES_PATH):
        """
        Args:
            pickle_path:
                Path to a pickle file.
        Raises:
            FileNotFoundError:
                The path does not exist.
        """
        pickle_path.parent.mkdir(parents=True, exist_ok=True)
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
        """
        For calling `pactl` commands as you would on the command line.
        """
        with contextlib.closing(pulsectl.connect_to_cli()) as s:
            for c in command:
                s.write(c + "\n")

    @classmethod
    def load_modules(cls,
                     device: pulsectl.PulseSourceInfo,
                     control: int,
                     verbose: bool = False,
                     set_default: bool = True) -> LoadInfo:
        """
        Args:
            device: Pulse source to use, e.g. as obtained by `PulseInterface.get_source_by_name()`.
            control: Control level for the RNNoise plugin.
            verbose: Whether to print extra stuff.
            set_default: Whether to select the new denoised output as the default output.
        Returns:
            Info about what was loaded that can be used for unloading.
            This is also pickled to the default location.
        """

        loaded = cls.get_loaded_modules()

        mic_name = device.name
        mic_rate = device.sample_spec.rate
        stereo = (device.channel_count == 2)

        null_sink_opts = (
            f"sink_name={cls.null_sink_name} "
            f"rate={mic_rate} "
            "sink_properties=\"device.description='RNNoise Denoised Sink'\""
        )
        loaded[cls.null_sink_name] = cls.pulse.module_load(
            "module-null-sink", null_sink_opts)
        if verbose:
            click.echo(f"Loaded module-null-sink {cls.null_sink_name} "
                       f"with index {loaded[cls.null_sink_name]} "
                       f"and options: {null_sink_opts}")

        with importlib.resources.path("rnnoise_cli.data", "librnnoise_ladspa.so") as plugin_path:
            ladspa_sink_opts = (
                f"sink_name={cls.ladspa_sink_name} "
                f"sink_master={cls.null_sink_name} "
                f"label=noise_suppressor_{'stereo' if stereo else 'mono'} "
                f"plugin=\"{plugin_path}\" "
                f"control={control} "
                "sink_properties=\"device.description='RNNoise Raw Input Sink'\""
            )
        loaded[cls.ladspa_sink_name] = cls.pulse.module_load(
            "module-ladspa-sink", ladspa_sink_opts)
        if verbose:
            click.echo(f"Loaded module-ladspa-sink {cls.ladspa_sink_name} "
                       f"with index {loaded[cls.ladspa_sink_name]} "
                       f"and options: {ladspa_sink_opts}")

        loopback_opts = (
            f"source={mic_name} "
            f"sink={cls.ladspa_sink_name} "
            f"channels={2 if stereo else 1} "
            "source_dont_move=true "
            "sink_dont_move=true "
            "latency_msec=1"
        )
        loaded[cls.loopback_key] = cls.pulse.module_load(
            "module-loopback", loopback_opts)
        if verbose:
            click.echo(f"Loaded module-loopback "
                       f"with index {loaded[cls.loopback_key]} "
                       f"and options: {loopback_opts}")

        remap_source_opts = (
            f"master={cls.null_sink_name}.monitor "
            f"source_name={cls.remap_source_name} "
            f"channels={2 if stereo else 1} "
            "source_properties=\"device.description='RNNoise Denoised Microphone'\""
        )
        loaded[cls.remap_source_name] = cls.pulse.module_load(
            "module-remap-source", remap_source_opts)
        if verbose:
            click.echo(f"Loaded module-remap-source {cls.remap_source_name} "
                       f"with index {loaded[cls.remap_source_name]} "
                       f"and options: {remap_source_opts}")

        if set_default:
            cls.pulse.source_default_set(cls.remap_source_name)

        load_info = LoadInfo(device=device, control=control, modules=loaded)
        load_info.write_pickle()
        return load_info

    @staticmethod
    def get_loaded_modules() -> Dict[str, int]:
        """
        Get the loaded modules from the default pickle file.
        """
        try:
            return LoadInfo.from_pickle().modules
        except (ValueError, FileNotFoundError):
            return {}

    @classmethod
    def change_control_level(cls, control: int, verbose: bool = False, force: bool = False, set_default: bool = False):
        """
        Change the control level on a loaded configuration.
        I haven't found a stable way to do this without unloading and re-loading the module.
        Args:
            control:
                The new control level.
            verbose:
                Whether to print extra stuff, passed to `unload_modules` and `load_modules`.
            force:
                Whether to continue even if it seems like an application is using the sink.
                Because of the reloading, the sink will get removed and re-added
                and most applications do not deal with that smoothly.
            set_default:
                Passed as the `set_default` argument to `load_modules`.
        """
        not_activated_msg = "The plugin is not activated. Cannot change control level."
        if not cls.rnn_is_loaded():
            raise NotActivatedException(not_activated_msg)

        if not force and cls.streams_using_rnnoise():
            raise RNNInUseException("The RNNoise plugin is being used by some application. "
                                    "Not allowed to change control level without `force` argument.")

        try:
            old_device = LoadInfo.from_pickle().device
        except (ValueError, FileNotFoundError):
            raise NotActivatedException(not_activated_msg)

        cls.unload_modules(verbose)
        cls.load_modules(old_device, control, verbose, set_default)

    @classmethod
    def streams_using_rnnoise(cls) -> bool:
        """
        Whether some stream is using the RNNoise output.
        """
        try:
            index = cls.get_source_by_name(cls.remap_source_name).index
        except ValueError:
            return False
        return any(s.source == index for s in cls.pulse.source_output_list())

    @staticmethod
    def unload_modules_all():
        """
        Force unload by onloading all modules of the same types as those loaded by `load_modules`.
        This is very aggressive and likely to remove other stuff if you are using anything beyond the default
        pulseaudio setup.
        Use with care!
        """
        LOADED_MODULES_PATH.unlink(missing_ok=True)
        PulseInterface.cli_command(
            [
                "unload-module module-loopback",
                "unload-module module-null-sink",
                "unload-module module-ladspa-sink",
                "unload-module module-remap-source",
            ]
        )

    @classmethod
    def unload_modules(cls, verbose: bool = False, force: bool = False):
        """
        Unloads all modules specified to be loaded in the default pickle file.
        Args:
            verbose:
                Whether to print extra stuff.
            force:
                Whether to continue even if it seems like an application is using the sink.
        Raises:
            PulseInterfaceException:
                `modules` is None and there is nothing to unload.
        """
        if not force and cls.streams_using_rnnoise():
            raise RNNInUseException("The RNNoise plugin is being used by some application. "
                                    "Not allowed to unload without `force` argument.")

        modules = cls.get_loaded_modules()

        if not modules:
            raise NoLoadedModulesException(
                "No modules loaded, cannot unload modules.")
        else:
            for name, index in modules.items():
                try:
                    cls.pulse.module_unload(index)
                    if verbose:
                        click.echo(f"Unloaded module {name} ({index}).")
                except pulsectl.PulseOperationFailed:
                    # The module was already unloaded for some reason.
                    pass

        LOADED_MODULES_PATH.unlink(missing_ok=True)

    @classmethod
    def get_input_devices(cls) -> List[pulsectl.PulseSourceInfo]:
        """
        Returns:
            A list of the available input devices.
        """
        return cls.pulse.source_list()

    @classmethod
    def get_default_input_device(cls):
        """
        Returns:
            The default input device.
        """
        return cls.get_source_by_name(cls.pulse.server_info().default_source_name)

    @classmethod
    def get_source(cls, identifier: str):
        """
        Get a source by either its name or its number.
        Args:
            identifier:
                A string containing either a pulse source's number or its name.
        Returns:
            The corresponding source if one with the given number or name exists.
            Otherwise, `None`.
        """
        try:
            return PulseInterface.get_source_by_num(int(identifier))
        except ValueError:
            try:
                return PulseInterface.get_source_by_name(identifier)
            except ValueError:
                return None

    @classmethod
    def get_source_by_name(cls, name: str) -> pulsectl.PulseSourceInfo:
        """
        Get a source by its name.
        Args:
            name: The source name.
        Returns:
            The corresponding source.
        Raises:
            ValueError:
                There is no source with this name.
        """
        try:
            return cls.pulse.get_source_by_name(name)
        except pulsectl.PulseIndexError:
            raise ValueError

    @classmethod
    def get_source_by_num(cls, num: int):
        """
        Get a source by its number.
        Args:
            num: The source number.
        Returns:
            The corresponding source.
        Raises:
            ValueError:
                There is no source with this number.
        """
        try:
            return next(s for s in cls.pulse.source_list() if s.index == num)
        except StopIteration:
            raise ValueError

    @classmethod
    def rnn_is_loaded(cls):
        """
        Check whether the plugin is loaded.
        This checks whether the pickle file is present,
        but also checks if the modules are actually loaded, as e.g. a reboot will reset pulse.
        Returns:
            Whether the plugin seems to be loaded.
        """
        if cls.get_loaded_modules():
            # Check if any of the modules are actually present
            rnn_names = [cls.null_sink_name, cls.ladspa_sink_name,
                         cls.loopback_key, cls.remap_source_name]
            return any(s.name in rnn_names for s in cls.pulse.source_list())
        else:
            return False
