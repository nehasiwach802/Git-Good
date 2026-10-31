import importlib.util
import json
import unittest
from pathlib import Path
from reasoning.engine import diagnose


@unittest.skipUnless(importlib.util.find_spec('jsonschema'), 'install test extras to validate JSON Schemas')
class SchemaTests(unittest.TestCase):
    def test_examples_and_responses(self):
        from jsonschema import Draft202012Validator
        request_schema = json.loads(Path('schemas/diagnose-request.schema.json').read_text())
        response_schema = json.loads(Path('schemas/diagnose-response.schema.json').read_text())
        Draft202012Validator.check_schema(request_schema)
        Draft202012Validator.check_schema(response_schema)
        requests, responses = Draft202012Validator(request_schema), Draft202012Validator(response_schema)
        for path in (Path('examples/rc.json'),Path('examples/opamp.json')):
            request = json.loads(path.read_text())
            requests.validate(request)
            for prediction in ({'status':'unavailable'}, {'status':'ok','value':.70710678}):
                responses.validate(diagnose(request,lambda c,p:prediction))
            request['student_circuit']['components'][0]['confirmed'] = False
            responses.validate(diagnose(request))
            request.pop('safety_profile')
            responses.validate(diagnose(request))

    def test_invalid_structural_examples(self):
        from jsonschema import Draft202012Validator
        validator = Draft202012Validator(json.loads(Path('schemas/diagnose-request.schema.json').read_text()))
        for request in ({}, [], {'schema_version':'2.0'}):
            self.assertFalse(validator.is_valid(request))
