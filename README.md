# rnnoise-cli
TODO: description

## Installation
TODO: instructions

## Configure defaults

Defaults are optionally loaded from `~/.config/rnnoise_cli/rnnoise_cli.conf`.

Example config with currently supported options:
```ini
[activate]
# device to use, omitted by default
# `rnnoise activate` will prompt for it if omitted (and provide a list of options)
device = "some.device.name"
# sampling rate, omitted by default
# `rnnoise activate` will automatically get the right rate if omitted
rate = 44100
# control level (0-100), 50 by default
control = 50
```

## Development
TODO: instructions

## Credits
- Uses the plugin from: https://github.com/werman/noise-suppression-for-voice
- Initially based on the work at https://github.com/josh-richardson/cadmus
