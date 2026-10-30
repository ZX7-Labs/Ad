"""Machine-readable native control ABI for capable structured-output backends.

Tool identities come from actual host discovery. Native artistic inputs remain
unrestricted here and are validated by the editor's own discovered schemas.
"""


def native_action_schema(tool_names):
    names = list(tool_names)
    if not names or any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError('Unique discovered native tool names are required')
    tool = {'type': 'string', 'enum': names}
    arguments = {
        'discover': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        'describe': {'type': 'object', 'properties': {'tool': tool}, 'required': ['tool'], 'additionalProperties': False},
        'invoke': {'type': 'object', 'properties': {'tool': tool, 'inputs': {'type': 'object'}},
                   'required': ['tool', 'inputs'], 'additionalProperties': False},
        'finish': {'type': 'object', 'properties': {'summary': {'type': 'string', 'minLength': 1}},
                   'required': ['summary'], 'additionalProperties': False},
    }
    return {'oneOf': [{'type': 'object', 'properties': {'action': {'const': action},
        'arguments': schema, 'reason': {'type': 'string', 'minLength': 1}},
        'required': ['action', 'arguments', 'reason'], 'additionalProperties': False}
        for action, schema in arguments.items()]}
