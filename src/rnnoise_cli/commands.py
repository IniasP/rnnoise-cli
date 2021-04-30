import os
import click
from .pulse import PulseInterface, NoneLoadedException
from importlib.metadata import version
import importlib.resources
import configparser

# ANSI escape sequences
ANSI_COLOR_GREEN = "\u001b[32m"
ANSI_COLOR_RED = "\u001b[31m"
ANSI_COLOR_BLUE = "\u001b[34m"
ANSI_COLOR_YELLOW = "\u001b[33m"
ANSI_UNDERLINE = "\u001b[4m"
ANSI_NO_UNDERLINE = "\u001b[24m"
ANSI_STYLE_RESET = "\u001b[0m"

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


def echo_devices_pretty():
    devices = PulseInterface.get_input_devices()
    for d in devices:
        click.echo(
            f"[{ANSI_COLOR_YELLOW}{d.index}{ANSI_STYLE_RESET}] "
            f"{ANSI_COLOR_BLUE}{d.name}{ANSI_STYLE_RESET} "
            f"({d.description})"
        )


def prompt_device_pretty() -> str:
    echo_devices_pretty()
    return click.prompt(
        f"{ANSI_COLOR_YELLOW}Number{ANSI_STYLE_RESET} or "
        f"{ANSI_COLOR_BLUE}name{ANSI_STYLE_RESET} "
        f"of device to use",
        default=PulseInterface.get_default_input_device().index,
        type=str
    )


def get_device_or_default(device: str = None):
    if device is None:
        return PulseInterface.get_default_input_device()
    else:
        try:
            return PulseInterface.get_device_by_num(int(device))
        except ValueError:
            try:
                return PulseInterface.get_device_by_name(device)
            except ValueError:
                return PulseInterface.get_default_input_device()


def prompt_until_valid_device(device: str = None):
    if device is None:
        device = prompt_device_pretty()
    if device == "":
        return PulseInterface.get_default_input_device()
    try:
        # device is a number
        try:
            # device is a valid number
            return PulseInterface.get_device_by_num(int(device))
        except ValueError:
            # device is an invalid number
            click.secho("Invalid device number.", fg="red")
            return prompt_until_valid_device()
    except ValueError:
        # device is a string
        if PulseInterface.get_device_by_name(device):
            # device is a valid string
            return device
        else:
            # device is an invalid string
            click.secho("Invalid device name.", fg="red")
            return prompt_until_valid_device()


@rnnoise.command()
@click.option("--device", "-d", type=str,
              help="Input device name or number (see `rnnoise list`). Default: default input device.")
@click.option("--rate", "-r", type=int,
              help="Microphone sample rate (in Hz). Default: auto.")
@click.option("--control", "-c", type=int,
              help="Control level between 0 and 100. Default: 50.")
@click.option("--no-prompts", "--no-interactive", is_flag=True,
              help="Don't prompt anything, use defaults for everything not provided.")
@click.pass_obj
def activate(ctx: CtxData, device: str, rate: int, control: int, no_prompts: bool):
    """
    Activate the noise suppression plugin.
    """
    try:
        PulseInterface.unload_modules(ctx.verbose)
        click.secho("Unloaded previously loaded modules first.", fg="red")
    except NoneLoadedException:
        pass

    activate_config = ctx.config["activate"]
    if device is None:
        device = activate_config.get("device", None)
    if rate is None:
        rate = activate_config.getint("rate", None)
    if control is None:
        control = activate_config.getint("control", None)

    if no_prompts:
        device = get_device_or_default(device)
    else:
        device = prompt_until_valid_device(device)

    if control is None or not 0 <= control <= 100:
        control = 50

    if rate is not None and rate < 0:
        click.secho(f"Invalid rate, using auto.", fg="red")
        rate = None
    if rate is None:
        rate = device.sample_spec.rate

    if ctx.verbose:
        click.echo("Selected params:")
        click.echo(f"\t{ANSI_UNDERLINE}Device name:{ANSI_STYLE_RESET} {device.name}")
        click.echo(f"\t{ANSI_UNDERLINE}Sampling rate:{ANSI_STYLE_RESET} {rate}")
        click.echo(f"\t{ANSI_UNDERLINE}Control level:{ANSI_STYLE_RESET} {control}")

    PulseInterface.load_modules(device.name, rate, control, ctx.verbose)

    if PulseInterface.rnn_is_loaded():
        click.secho("Activated!", fg="green")


@rnnoise.command()
@click.option("--force", "-f", is_flag=True, default=False,
              help="Remove all modules of the types used by rnnoise-cli (module-loopback, module-null-sink, "
                   "module-ladspa-sink, module-remap-source). This could remove modules loaded by other applications.")
@click.pass_obj
def deactivate(ctx: CtxData, force: bool):
    """
    Deactivate the noise suppression plugin.
    """
    if force:
        PulseInterface.unload_modules_all()
    else:
        try:
            PulseInterface.unload_modules(ctx.verbose)
            click.secho("Deactivated!", fg="green")
        except NoneLoadedException:
            click.secho(f"No loaded modules found, try {ANSI_UNDERLINE}--force{ANSI_NO_UNDERLINE} if you're sure.",
                        fg="red")


@rnnoise.command(name="list")
def list_devices():
    """
    List available devices.
    """
    echo_devices_pretty()


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
    else:
        click.secho("The plugin is not loaded.", fg="red")


ALIASES = {
    "ls": list_devices,
    "devices": list_devices
}
