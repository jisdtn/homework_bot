class NoToken(Exception):
    pass


class KeysAreNotInResponse(Exception):
    pass


class EmptyList(Exception):
    """Список пуст"""
    pass


class JsonException(Exception):
    """Возвращается не json"""
    pass
