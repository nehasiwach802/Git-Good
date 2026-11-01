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

    def test_actual_vision_envelopes_and_outputs(self):
        from jsonschema import Draft202012Validator
        from referencing import Registry,Resource
        from reasoning.api import diagnose_input
        analog=json.loads(Path('schemas/diagnose-request.schema.json').read_text())
        vision=json.loads(Path('schemas/vision-diagnose-request.schema.json').read_text())
        registry=Registry().with_resource(analog['$id'],Resource.from_contents(analog))
        Draft202012Validator.check_schema(vision)
        validator=Draft202012Validator(vision,registry=registry)
        response=Draft202012Validator(json.loads(Path('schemas/diagnose-response.schema.json').read_text()))
        for name in ('vision-7400','vision-7400-wrong-wire','vision-7400-unreviewed','vision-rc'):
            request=json.loads(Path(f'examples/{name}.json').read_text())
            validator.validate(request)
            response.validate(diagnose_input(request))

    def test_generalized_examples_and_outputs(self):
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        from reasoning.api import diagnose_input
        registry = Registry()
        schemas = {}
        for name in ('observation', 'reference-record', 'generalized-request', 'generalized-response'):
            schema = json.loads(Path(f'schemas/{name}.schema.json').read_text())
            Draft202012Validator.check_schema(schema)
            schemas[name] = schema
            registry = registry.with_resource(schema['$id'], Resource.from_contents(schema))
        requests = Draft202012Validator(schemas['generalized-request'], registry=registry)
        responses = Draft202012Validator(schemas['generalized-response'], registry=registry)
        for path in Path('examples/generalized').glob('*.json'):
            request = json.loads(path.read_text())
            requests.validate(request)
            responses.validate(diagnose_input(request))
