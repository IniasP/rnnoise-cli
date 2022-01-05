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


def obtain_device(activate_config: configparser.SectionProxy, device_str: str, prompt: bool):
    if device_str is None:
        device_str = activate_config.get("device", None)
    device = None if device_str is None else PulseInterface.get_source(device_str)
    if device is None:
        if prompt:
            while True:
                device_str = prompt_device_pretty()
                device = PulseInterface.get_source(device_str)
                if device is None:
                    click.secho(f"Device not found: \"{device_str}\"", fg="red")
                else:
                    return device
        else:
            return PulseInterface.get_default_input_device()
    else:
        return device


@rnnoise.command()
@click.option("--device", "-d", "device_str", type=str,
              help="Input device name or number (see `rnnoise list`). Default: default input device.")
@click.option("--control", "-c", type=int,
              help="Control level between 0 and 100. Default: 50.")
@click.option("--prompt/--no-prompt", default=True,
              help="When no device is configured or given, prompt or use default device immediately?")
@click.option("--set-default/--no-set-default", default=True,
              help="Set the new RNNoise device as default device.")
@click.pass_obj
def activate(ctx: CtxData, device_str: str, control: int, prompt: bool, set_default: bool):
    """
    Activate the noise suppression plugin.
    """
    if PulseInterface.rnn_is_loaded():
        if not click.confirm(pretty.ALREADY_LOADED_CONFIRM):
            return

    activate_config = ctx.config["activate"]
    if control is None:
        control = activate_config.getint("control", None)

    device = obtain_device(activate_config, device_str, prompt)

    if control is None or not 0 <= control <= 100:
        control = 50

    if ctx.verbose:
        click.echo(pretty.params(device, control))

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
    Subcommands to manage the control level.
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
        click.secho(pretty.load_info(LoadInfo.from_pickle()))
    else:
        click.secho("The plugin is not loaded.", fg="red")


ALIASES = {
    "ls": list_devices,
    "devices": list_devices
}
