## ECS Explorer

ECS Explorer is a CLI that allows you to browse and inspect your AWS ECS resources.

## Motivation

The web console for AWS ECS is notoriously bad and kills productivity. I made ECS Explorer to speed up the process of troubleshooting my ECS resources.

## Installation

ECS Explorer is installed via [Pip](http://pip.readthedocs.io), the Python package manager.
```sh
pip install ecs_explorer
```
It is then started with the command ```ecs_explorer```. You must have your AWS credentials available either as env variables or in a credentials file.

It also supports assuming STS roles
```sh
ecs_explorer --role arn:aws:iam::437692186728:role/myrole
```
