class PerfumeNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class InvalidCodeError(Exception):
    pass


class TooManyAttemptsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass
