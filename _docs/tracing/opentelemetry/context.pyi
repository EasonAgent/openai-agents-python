from opentelemetry.context import create_key, set_value, get_value, get_current, attach, detach

import typing
""" --------------------------------------------------------------------------------------------------------------------
Context: 不可修改的字典

> from opentelemetry.context.context import Context
-------------------------------------------------------------------------------------------------------------------- """
class Context(typing.Dict[str, object]):
    def __setitem__(self, key: str, value: object) -> None:
        raise ValueError