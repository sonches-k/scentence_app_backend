"""
Доменные исключения.

Единое место для бизнес-ошибок — используется в use cases и перехватывается в API слое.
"""


class PerfumeNotFoundError(Exception):
    """Аромат не найден."""
    pass


class UserNotFoundError(Exception):
    """Пользователь не найден."""
    pass


class InvalidCodeError(Exception):
    """Неверный или истёкший код подтверждения."""
    pass


class TooManyAttemptsError(Exception):
    """Превышен лимит попыток ввода кода."""
    pass
