class PulseInterfaceException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class NotActivatedException(PulseInterfaceException):
    def __init__(self, message: str = "The plugin is not activated."):
        super().__init__(message)


class NoLoadedModulesException(PulseInterfaceException):
    def __init__(self, message: str = "No loaded modules found."):
        super().__init__(message)


class RNNInUseException(PulseInterfaceException):
    def __init__(self, message: str = "The plugin is in use."):
        super().__init__(message)
