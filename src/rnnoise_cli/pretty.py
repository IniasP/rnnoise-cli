# ANSI escape sequences
from rnnoise_cli.pulse import LoadInfo

ANSI_COLOR_GREEN = "\u001b[32m"
ANSI_COLOR_RED = "\u001b[31m"
ANSI_COLOR_BLUE = "\u001b[34m"
ANSI_COLOR_YELLOW = "\u001b[33m"
ANSI_UNDERLINE = "\u001b[4m"
ANSI_NO_UNDERLINE = "\u001b[24m"
ANSI_STYLE_RESET = "\u001b[0m"

DEVICE_PROMPT = f"{ANSI_COLOR_YELLOW}Number{ANSI_STYLE_RESET} or " \
                f"{ANSI_COLOR_BLUE}name{ANSI_STYLE_RESET} " \
                "of device to use"
ALREADY_LOADED_CONFIRM = f"{ANSI_COLOR_RED}RNNoise is already loaded.{ANSI_STYLE_RESET}\nContinue anyway?"
STREAM_IN_USE_UNLOAD_CONFIRM = f"{ANSI_COLOR_RED}The RNNoise input stream is in use, " \
                               f"unloading may cause applications to misbehave.{ANSI_STYLE_RESET}\n" \
                               f"Are you sure?"
NO_LOADED_MODULES = f"No loaded modules found (already deactivated?), " \
                    f"try {ANSI_UNDERLINE}--force-unload-all{ANSI_NO_UNDERLINE} if you are sure."
STREAM_IN_USE_CONTROL_CONFIRM = f"{ANSI_COLOR_RED}The RNNoise input stream is in use, " \
                                f"changing control level may cause applications to misbehave.{ANSI_STYLE_RESET}\n" \
                                "Are you sure?"


def list_devices(devices):
    device_strings = [(
        f"[{ANSI_COLOR_YELLOW}{d.index}{ANSI_STYLE_RESET}]",
        f"{ANSI_COLOR_BLUE}{d.name}{ANSI_STYLE_RESET}",
        d.description
    ) for d in devices]
    column_lens = []
    for col in zip(*device_strings):
        column_lens.append(max(len(val) for val in col))
    fmt = f"{{:>{column_lens[0]}}}  {{:<{column_lens[1]}}}  {{:<{column_lens[2]}}}"
    return "\n".join(fmt.format(*s) for s in device_strings)


def params(device, control):
    return f"\t{ANSI_UNDERLINE}Device{ANSI_STYLE_RESET}:         {device.name}\n" \
           f"\t{ANSI_UNDERLINE}Control level{ANSI_STYLE_RESET}:  {control}"


def load_info(info: LoadInfo):
    return f"{ANSI_UNDERLINE}Device{ANSI_STYLE_RESET}:   {info.device.name}\n" \
           f"{ANSI_UNDERLINE}Control{ANSI_STYLE_RESET}:  {info.control}"
