import unittest
from collections import namedtuple
from unittest.mock import patch
from click.testing import CliRunner
from rnnoise_cli.commands import rnnoise


class TestList(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    @staticmethod
    def get_test_devices() -> list:
        test_device_1 = namedtuple("obj", ["index", "name", "description"])(
            0, "test.device", "Test device description"
        )
        test_device_2 = namedtuple("obj", ["index", "name", "description"])(
            1, "test.device.2 another one", "Test device two description"
        )
        return [test_device_1, test_device_2]

    @patch("rnnoise_cli.commands.PulseInterface.get_input_devices")
    def test_list_formatting(self, get_input_devices):
        get_input_devices.return_value = self.get_test_devices()
        result = self.runner.invoke(rnnoise, "list")
        assert result.exit_code == 0
        assert result.output == (
            "[0]  test.device                Test device description    \n"
            "[1]  test.device.2 another one  Test device two description\n"
        )


if __name__ == '__main__':
    unittest.main()
