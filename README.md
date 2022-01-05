# rnnoise-cli

A CLI wrapper for the LADSPA plugin at https://github.com/werman/noise-suppression-for-voice.
To be used with systems running PulseAudio (basically any Linux distro).
This was written out of frustration that Discord+Krisp is unavailable on Linux.
If you'd like a GUI alternative, check out [Cadmus](https://github.com/josh-richardson/cadmus)
(as of May 2021, it has some issues and the developer seems to be MIA).

## Installation

Install from [PyPI](https://pypi.org/project/rnnoise-cli):
```
pip install rnnoise-cli
```

Or install from source, see [development](#development).

## Enabling shell completion

The click library offers tab completion for bash, zsh and fish, but it's not installed automatically.

If you downloaded the source, the [Makefile](Makefile) can generate the relevant scripts after installing (run `make help`).
Otherwise, generate a script as follows:

```bash
_RNNOISE_COMPLETE=bash_source rnnoise > rnnoise_completion.sh
```

You can replace `bash_source` with `zsh_source` or `fish_source` for other shells.
The generated script should be sourced from `.bashrc`/`.zshrc`/`~/.config/fish/completions/rnnoise.sh`.

See [the click documentation](https://click.palletsprojects.com/en/8.0.x/shell-completion/) for more info.

## Usage

```bash
rnnoise activate
```
It will show a list of eligible input devices and prompt you to select one.

You can use `--control` to set the control level.
Control level 0 means only try to filter noise and never cut to silence,
100 means silence unless RNNoise is 100% sure you're talking.
The default of 50 means that if RNNoise determines the probability that you're talking to be below 50%,
the output will be silent.
Your strategy should be to start at the default of 50 and go up if it blocks too little or down if your voice is
cutting out while talking.

A new input option named "RNNoise Denoised Microphone" should now be available to your system.


Check out `rnnoise --help` for more commands.

## Configure defaults

Defaults are optionally loaded from `~/.config/rnnoise_cli/rnnoise_cli.conf`.
These settings are overridden by the corresponding options when provided (e.g. `--device`, see `rnnoise --help`).

Example config with currently supported options:
```ini
[activate]
# device to use, omitted by default
# `rnnoise activate` will prompt for it if omitted (and provide a list of options)
device = "some.device.name"
# control level (0-100), 50 by default
control = 50
```

## Development

The project should work with any Python ≥ 3.7.

Create a virtual environment:
```bash
python3 -m venv venv
# activate or alternatively configure IDE (e.g. PyCharm) to use the env's interpreter
source venv/bin/activate
```

Install dev requirements:
```bash
# this runs pip install -r requirements.txt
make init
```

## Credits
- Initially based on the work at https://github.com/josh-richardson/cadmus
- Uses the plugin from https://github.com/werman/noise-suppression-for-voice (the file `res/librnnoise_ladspa.so` is obtained from
the [noise-suppression-for-voice releases](https://github.com/werman/noise-suppression-for-voice/releases).
)
- The plugin above is in turn based on a recurrent neural network: https://github.com/xiph/rnnoise
