"""Constrain the control protocol, never select the model's creative actions."""
import importlib.util
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


if __name__ == '__main__': unittest.main()
