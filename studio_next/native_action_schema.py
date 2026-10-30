"""Machine-readable native control ABI for capable structured-output backends.

Tool identities come from actual host discovery. Native artistic inputs remain
unrestricted here and are validated by the editor's own discovered schemas.
"""


def native_action_schema(tool_names, *, compact_catalog=False, selected_tools=None):
    names = list(tool_names)
    if ((not names and not compact_catalog) or
            any(not isinstance(name, str) or not name for name in names) or
            len(set(names)) != len(names)):
        raise ValueError('Unique discovered native tool names are required')
    # The host remains authoritative: compact mode avoids putting thousands
    # of tool names into a small model's JSON grammar/prompt on every turn.
    # The actual controller resolves/grants every submitted tool independently.
    if compact_catalog:
        selected = [] if selected_tools is None else list(selected_tools)
        if (len(selected) > 8 or
                any(not isinstance(name, str) or not name or len(name) > 160
                    for name in selected) or
                len(set(selected)) != len(selected)):
            raise ValueError('Compact tool options must be exact, bounded native IDs')
        # Retrieval-conditioned grammar: an unavailable or unsearched tool
        # is unrepresentable, not merely a name the model is told to avoid.
        tool = {'type': 'string', 'enum': selected} if selected else None
    else:
        tool = {'type': 'string', 'enum': names}
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
    # A compact catalog cannot reveal all tool names via `discover`;
    # in that mode the only meaningful discovery instrument is `search`.
    # In full mode search has no index. Do not advertise inert actions to
    # tiny models as if they advanced native editing.
    if compact_catalog:
        del arguments['discover']
    else:
        del arguments['search']
    if tool is None:
        del arguments['describe']
        del arguments['invoke']
    return {'oneOf': [{'type': 'object', 'properties': {'action': {'const': action},
        'arguments': schema, 'reason': {'type': 'string', 'minLength': 1}},
        'required': ['action', 'arguments', 'reason'], 'additionalProperties': False}
        for action, schema in arguments.items()]}
