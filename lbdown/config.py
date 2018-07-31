import os

import yaml


# Parse configuration
if 'LBDOWN_CONFIG_DIR' in os.environ:
    CONFIG_DIR = os.path.realpath(os.environ['LBDOWN_CONFIG_DIR'])
else:
    raise RuntimeError(
            'The LBDOWN_CONFIG_DIR environment variable is not set.\n'
            'Please set it to point to a valid configuration directory.')

with open(CONFIG_DIR + '/flask.yml', 'r') as stream:
    flask = yaml.load(stream, yaml.SafeLoader)

with open(CONFIG_DIR + '/application.yml', 'r') as stream:
    application = yaml.load(stream, yaml.SafeLoader)


