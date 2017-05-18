import argparse
from ecs_client import EcsClient

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--role", default=None, help='An STS role to assume')
PARSER.add_argument("--ssh-script", default=None, help='Full path to the script to execute when trying to ssh to an EC2 instance. This will be passed a single argument which will be the Private IP of the instance. The script must be executable by the current user.')
ARGS = PARSER.parse_args()
ECS_CLIENT = EcsClient(ARGS.role)
SSH_SCRIPT = ARGS.ssh_script