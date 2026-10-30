"""Constrain the control protocol, never select the model's creative actions."""
import importlib.util
import json
import unittest
from studio_next.native_action_schema import native_action_schema

HAS_SCHEMA = importlib.util.find_spec('jsonschema') is not None


@unittest.skipUnless(HAS_SCHEMA, 'Install the editor extra for schema validation')
class NativeActionSchemaTests(unittest.TestCase):
    def setUp(self):
        import jsonschema
        self.validator = jsonschema.Draft202012Validator(native_action_schema(['get_project', 'add_text_clip']))

    def test_all_actions_and_free_native_inputs_remain_available(self):
        for action, arguments in [('discover', {}), ('describe', {'tool': 'get_project'}),
                ('invoke', {'tool': 'add_text_clip', 'inputs': {'text': 'अपनी रचना', 'style': {'custom': [1, .25]}}}),
                ('finish', {'summary': 'Actual result remains subject to review'})]:
            self.validator.validate({'action': action, 'arguments': arguments, 'reason': 'Model choice'})

    def test_actual_live_failure_cannot_be_encoded(self):
        bad = {'action': 'describe', 'arguments': {'tool': 'describe', 'parameters': {}}, 'reason': 'Inspect'}
        self.assertFalse(self.validator.is_valid(bad))
        for args in ({'tool': 'invented'}, {'tool': 'get_project', 'parameters': {}}):
            self.assertFalse(self.validator.is_valid({'action': 'describe', 'arguments': args, 'reason': 'Inspect'}))

    def test_protocol_errors_are_rejected_without_fixing_artistic_values(self):
        for value in ({'action': 'execute', 'arguments': {}, 'reason': 'x'},
                {'action': 'invoke', 'arguments': {'tool': 'get_project', 'inputs': []}, 'reason': 'x'},
                {'action': 'finish', 'arguments': {'summary': 'done'}, 'reason': 'x', 'allowed_tools': ['shell']}):
            self.assertFalse(self.validator.is_valid(value))

    def test_compact_brain_grammar_supports_host_indexed_discovery_not_giant_tool_enum(self):
        import jsonschema
        compact = native_action_schema([], compact_catalog=True)
        payload = json.dumps(compact)
        self.assertNotIn("get_project", payload)
        self.assertNotIn('"enum"', payload)
        validator = jsonschema.Draft202012Validator(compact)
        self.assertFalse(validator.is_valid({
            "action": "discover", "arguments": {}, "reason": "No tools in indexed mode"}))
        self.assertFalse(self.validator.is_valid({
            "action": "search", "arguments": {"query": "video"}, "reason": "Full mode has no index"}))
        validator.validate({"action": "search",
            "arguments": {"query": "editable motion project", "limit": 4},
            "reason": "Discover currently available host capabilities"})
        # No tool is selectable until BODY has actually searched/returned it.
        self.assertFalse(validator.is_valid({"action": "describe",
            "arguments": {"tool": "model_selected_actual_name"}, "reason": "Guess"}))
        self.assertFalse(validator.is_valid({"action": "invoke",
            "arguments": {"tool": "search", "inputs": {"query": "project"}},
            "reason": "Confuse protocol with editor"}))
        returned = native_action_schema([], compact_catalog=True,
                                        selected_tools=["create_project", "get_project"])
        exact = jsonschema.Draft202012Validator(returned)
        exact.validate({"action": "invoke",
            "arguments": {"tool": "create_project", "inputs": {"name": "Original"}},
            "reason": "Model selected a real discovered project tool"})
        self.assertFalse(exact.is_valid({"action": "invoke",
            "arguments": {"tool": "search", "inputs": {}}, "reason": "wrong layer"}))
        self.assertFalse(exact.is_valid({"action": "invoke",
            "arguments": {"tool": "unreturned_tool", "inputs": {}},
            "reason": "Made up a command"}))
        for bad in ({"query": "x", "limit": 12},
                    {"query": "", "limit": 1},
                    {"query": "x", "other": "hidden"}):
            with self.subTest(bad=bad):
                self.assertFalse(validator.is_valid({
                    "action": "search", "arguments": bad, "reason": "Model search"}))


if __name__ == '__main__': unittest.main()
