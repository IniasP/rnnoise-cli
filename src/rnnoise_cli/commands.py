import os
import click
from .pulse import PulseInterface, LoadInfo
from .pulse.exceptions import *
from . import pretty
from importlib.metadata import version
import importlib.resources
import configparser

CONFIG_FILE_PATH = os.path.join(os.environ["HOME"], ".config", "rnnoise_cli", "rnnoise_cli.conf")

CONFIG_DEFAULTS = {
    "activate": {
        # "device": omitted,
        # "rate": omitted,
        "control": "50"
    }
}


class AliasedGroup(click.Group):
    """
    Courtesy of https://stackoverflow.com/a/53144555/11520125.
    """

    def get_command(self, ctx, cmd_name):
        try:
            cmd_name = ALIASES[cmd_name].name
        except KeyError:
            pass
        return super().get_command(ctx, cmd_name)


class CtxData:
    def __init__(self, config: configparser.ConfigParser, verbose: bool):
        self.config = config
        self.verbose = verbose


@click.group(cls=AliasedGroup)
@click.version_option(version=version("rnnoise-cli"))
@click.option("--verbose", "-v", is_flag=True,
              help="Print more.")
@click.pass_context
def rnnoise(ctx, verbose: bool):
    config = configparser.ConfigParser()
    # load defaults
    config.read_dict(CONFIG_DEFAULTS)
    # load actual config
    config.read(CONFIG_FILE_PATH)
    ctx.obj = CtxData(config, verbose)


def prompt_device_pretty() -> str:
    click.echo(pretty.list_devices(PulseInterface.get_input_devices()))
    return click.prompt(
        pretty.DEVICE_PROMPT,
        default=PulseInterface.get_default_input_device().index,
        type=str
    )


def get_device_or_default(device: str = None):
    if device is None:
        return PulseInterface.get_default_input_device()
    else:
        try:
            return PulseInterface.get_source_by_num(int(device))
        except ValueError:
            try:
                return PulseInterface.get_source_by_name(device)
            except ValueError:
                return PulseInterface.get_default_input_device()


def get_device_or_prompt(device: str = None):
    if device is None:
        device = prompt_device_pretty()
    if device == "":
        return PulseInterface.get_default_input_device()
    try:
        # device is a number
        try:
            # device is a valid number
            return PulseInterface.get_source_by_num(int(device))
        except ValueError:
            # device is an invalid number
            click.secho("Invalid device number.", fg="red")
            return get_device_or_prompt()
    except ValueError:
        # device is a string
        try:
            # device is a valid string
            return PulseInterface.get_source_by_name(device)
        except ValueError:
            # device is an invalid string
            click.secho("Invalid device name.", fg="red")
            return get_device_or_prompt()


# TODO: rate parameter is quite useless, better remove it
@rnnoise.command()
@click.option("--device", "-d", type=str,
              help="Input device name or number (see `rnnoise list`). Default: default input device.")
@click.option("--rate", "-r", type=int,
              help="Microphone sample rate (in Hz). Default: auto.")
@click.option("--control", "-c", type=int,
              help="Control level between 0 and 100. Default: 50.")
@click.option("--prompt/--no-prompt", default=True,
              help="When no device is configured, prompt or use default device immediately?")
@click.option("--set-default/--no-set-default", default=True,
              help="Set the new RNNoise device as default device.")
@click.pass_obj
def activate(ctx: CtxData, device: str, rate: int, control: int, prompt: bool, set_default: bool):
    """
    Activate the noise suppression plugin.
    """
    if PulseInterface.rnn_is_loaded():
        if not click.confirm(pretty.ALREADY_LOADED_CONFIRM):
            return

    activate_config = ctx.config["activate"]
    if device is None:
        device = activate_config.get("device", None)
    if rate is None:
        rate = activate_config.getint("rate", None)
    if control is None:
        control = activate_config.getint("control", None)

    if prompt:
        device = get_device_or_prompt(device)
    else:
        device = get_device_or_default(device)

    if control is None or not 0 <= control <= 100:
        control = 50

    if rate is not None and rate < 0:
        click.secho(f"Invalid rate, using auto.", fg="red")
        rate = None
    if rate is None:
        rate = device.sample_spec.rate

    if ctx.verbose:
        click.echo(pretty.params(device, rate, control))

    PulseInterface.load_modules(device, control, ctx.verbose, set_default)

    if PulseInterface.rnn_is_loaded():
        click.secho("Activated!", fg="green")


@rnnoise.command()
@click.option("--force-unload-all", is_flag=True, default=False,
              help="Remove all modules of the types used by rnnoise-cli (module-loopback, module-null-sink, "
                   "module-ladspa-sink, module-remap-source). This could remove modules loaded by other applications.")
@click.option("--force", is_flag=True, default=False,
              help="Unload even if the RNNoise input stream is active.")
@click.pass_obj
def deactivate(ctx: CtxData, force_unload_all: bool, force: bool):
    """
    Deactivate the noise suppression plugin.
    """
    if force_unload_all:
        PulseInterface.unload_modules_all()
    else:
        try:
            PulseInterface.unload_modules(verbose=ctx.verbose, force=force)
            click.secho("Deactivated!", fg="green")
        except RNNInUseException:
            if click.confirm(pretty.STREAM_IN_USE_UNLOAD_CONFIRM):
                PulseInterface.unload_modules(verbose=ctx.verbose, force=True)
        except NoLoadedModulesException:
            click.secho(pretty.NO_LOADED_MODULES, fg="red")


@rnnoise.group(name="control")
@click.pass_obj
def control_(ctx: CtxData):
    """
    Change the control level.
    """
    pass


@control_.command(name="get")
def control_get():
    """
    Get control level.
    """
    click.echo(LoadInfo.from_pickle().control)


@control_.command(name="set")
@click.argument("control_level", type=int)
@click.option("--force", "-f", is_flag=True, default=False,
              help="Change control level, even if the RNNoise input stream is active.")
@click.option("--set-default/--no-set-default", default=False,
              help="Set the updated RNNoise device as default device.")
@click.pass_obj
def control_set(ctx: CtxData, control_level: int, force: bool, set_default: bool):
    """
    Set control level.
    """
    try:
        PulseInterface.change_control_level(control_level, ctx.verbose, force, set_default)
    except NotActivatedException:
        click.secho("Plugin is not activated, cannot change control level.", fg="red")
    except RNNInUseException:
        if click.confirm(pretty.STREAM_IN_USE_CONTROL_CONFIRM):
            PulseInterface.change_control_level(control_level, ctx.verbose, True, set_default)


@rnnoise.command(name="list")
def list_devices():
    """
    List available devices.
    """
    click.echo(pretty.list_devices(PulseInterface.get_input_devices()))


@rnnoise.command(name="license")
def license_():
    """
    Show license info and exit.
    """
    notice = importlib.resources.read_text("rnnoise_cli.data", "license_info.txt")
    click.echo(notice)
    exit()


@rnnoise.command()
def status():
    """
    Show whether the LADSPA plugin is loaded.
    """
    if PulseInterface.rnn_is_loaded():
        click.secho("The plugin is loaded.", fg="green")
        click.secho(LoadInfo.from_pickle().pretty)
    else:
        click.secho("The plugin is not loaded.", fg="red")


ALIASES = {
    "ls": list_devices,
    "devices": list_devices
}
