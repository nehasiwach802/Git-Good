"""Backend-owned reference/board configuration; never supplied by a phone."""
from copy import deepcopy
import json
from labvision.geometry import hole_positions
from reasoning.observations import validate_reference


def load_catalog(path):
    data = json.loads(path.read_text())
    result = {}
    for item in data['experiments']:
        validate_reference(item['reference'])
        hole_positions(item['board'])
        key = (item['experiment_id'], item['version'])
        if key in result or key != (item['reference']['experiment_id'],item['reference']['version']):
            raise ValueError('Duplicate or inconsistent experiment ID/version')
        if type(item.get('workflow_approved',False)) is not bool or type(item.get('simulated',False)) is not bool:
            raise ValueError('Workflow and simulation flags must be explicit booleans')
        if not item.get('reported_parts'):
            raise ValueError('Experiment must declare supported reported parts')
        result[key] = deepcopy(item)
    return result
