"""Machine-readable native control ABI for capable structured-output backends.

Tool identities come from actual host discovery. Native artistic inputs remain
unrestricted here and are validated by the editor's own discovered schemas.
"""


def native_action_schema(tool_names, *, compact_catalog=False):
    names = list(tool_names)
    if ((not names and not compact_catalog) or
            any(not isinstance(name, str) or not name for name in names) or
            len(set(names)) != len(names)):
        raise ValueError('Unique discovered native tool names are required')
    # The host remains authoritative: compact mode avoids putting thousands
    # of tool names into a small model's JSON grammar/prompt on every turn.
    # The actual controller resolves/grants every submitted tool independently.
    tool = ({'type': 'string', 'minLength': 1, 'maxLength': 160}
            if compact_catalog else {'type': 'string', 'enum': names})
    arguments = {
        'discover': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        'search': {'type': 'object', 'properties': {
            'query': {'type': 'string', 'minLength': 1, 'maxLength': 160},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 8}},
            'required': ['query'], 'additionalProperties': False},
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
