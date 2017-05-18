import urwid
from ecs_client import EcsClient
import subprocess
from settings import ECS_CLIENT

class RefreshableItems(object):
    def __init__(self, retrieval_method, method_args):
        self.retrieval_method = retrieval_method
        self.method_args = method_args
        results = self.retrieval_method(*self.method_args)
        if len(results) is 2:
            self.items_title, self.items = results
            self.highlighted = None
        else:
            self.items_title, self.items, self.highlighted = results

    def refresh(self):
        results = self.retrieval_method(*self.method_args)
        if len(results) is 2:
            self.items_title, self.items = results
            self.highlighted = None
        else:
            self.items_title, self.items, self.highlighted = results

class EcsButton(urwid.Button):

    def __init__(self, identifier, name, detail):
        self.identifier = identifier
        self.detail = detail
        self.name = name
        self.showing_detail = False
        super(EcsButton, self).__init__(name)

    def retrieve_children(self):
        pass

    def retrieve_by_highlight(self, key):
        pass

    def special_action(self, key):
        return (None, None)

    def contains_word(self, word):
        return word.lower() in self.name.lower()

class Cluster(EcsButton):

    def __init__(self, identifier, name, detail):
        super(Cluster, self).__init__(identifier, name, detail)

    def retrieve_important_details(self):
        return [("Status", self.detail['status']),
                (["Active ", ('key', "S"), "ervices"], self.detail['activeServicesCount']),
                (["Running ", ('key', "T"), "asks"], self.detail['runningTasksCount']),
                ("Pending Tasks", self.detail['pendingTasksCount']),
                ([('key',"C"), "ontainers"], self.detail['registeredContainerInstancesCount'])]

    def retrieve_children(self):
        return ("Choose sub-resource", [ServicesLabel(self.identifier), ContainersLabel(self.identifier)])

    def retrieve_by_highlight(self, key):
        if key is "T":
            return ("Tasks", [Task(None, self.identifier, t['taskArn'].split("/")[1], t) for t in ECS_CLIENT.retrieve_tasks(self.identifier).values()], None)
        if key is "S":
            return ("Services", [Service(s['serviceArn'], s['serviceName'], self.identifier, s) for s in ECS_CLIENT.retrieve_services(self.identifier).values()], None)
        if key is "C":
            containers = ECS_CLIENT.retrieve_containers(self.identifier)
            containers_by_id = dict((value[0]['containerInstanceArn'], value) for (key, value) in containers.iteritems())
            return ("Containers", [Container(key, key.split("/")[1], self.identifier, value) for (key, value) in containers_by_id.iteritems()], None)
        else:
            return (None, [])


class ServicesLabel(EcsButton):
    def __init__(self, cluster_identifier):
        super(ServicesLabel, self).__init__(cluster_identifier, "Services", "")

    def retrieve_children(self):
        return ("Services", [Service(s['serviceArn'], s['serviceName'], self.identifier, s) for s in ECS_CLIENT.retrieve_services(self.identifier).values()])

    def retrieve_important_details(self):
        return []


class ContainersLabel(EcsButton):
    def __init__(self, cluster_identifier):
        super(ContainersLabel, self).__init__(
            cluster_identifier, "Containers", "")

    def retrieve_children(self):

        containers = ECS_CLIENT.retrieve_containers(self.identifier)
        containers_by_id = dict((value[0]['containerInstanceArn'], value) for (key, value) in containers.iteritems())
        return ("Containers", [Container(key, key.split("/")[1], self.identifier, value) for (key, value) in containers_by_id.iteritems()])

    def retrieve_important_details(self):
        return []


class Container(EcsButton):

    def __init__(self, identifier, name, cluster_identifier, detail):
        super(Container, self).__init__(identifier, name, detail)
        self.cluster_identifier = cluster_identifier

    def retrieve_children(self):
        return (None, None)

    def retrieve_important_details(self):
        cont_detail = self.detail[0]
        attributes = cont_detail['attributes']
        registered_resources = cont_detail['registeredResources']
        available_resources = cont_detail['remainingResources']
        ami_id = next(
            obj for obj in attributes if obj['name'] == 'ecs.ami-id')['value']
        instance_type = next(
            obj for obj in attributes if obj['name'] == 'ecs.instance-type')['value']
        availability_zone = next(
            obj for obj in attributes if obj['name'] == 'ecs.availability-zone')['value']
        available_memory = next(
            obj for obj in available_resources if obj['name'] == 'MEMORY')['integerValue']
        total_memory = next(
            obj for obj in registered_resources if obj['name'] == 'MEMORY')['integerValue']
        available_cpu = next(obj for obj in available_resources if obj['name'] == 'CPU')[
            'integerValue']
        total_cpu = next(obj for obj in registered_resources if obj['name'] == 'CPU')[
            'integerValue']
        taken_ports = ", ".join(sorted(next(
            obj for obj in available_resources if obj['name'] == 'PORTS')['stringSetValue']))
        return [('Status', cont_detail['status']),
                ('EC2 Instance Id', cont_detail['ec2InstanceId']),
                (['Private ', ('key', 'I'), 'P'], self.detail[1]['PrivateIpAddress']),
                ('Private DNS Name', self.detail[1]['PrivateDnsName']),
                ('Public DNS Name', self.detail[1]['PublicDnsName']),
                (['Running ', ('key','T'), 'asks'], cont_detail['runningTasksCount']),
                ('Pending Tasks', cont_detail['pendingTasksCount']),
                ('AMI Id', ami_id),
                ('Instance Type', instance_type),
                ('Availability Zone', availability_zone),
                ('Memory', 'Available: ' + str(available_memory) +
                 " Total: " + str(total_memory)),
                ('CPU', 'Available: ' + str(available_cpu) +
                 " Total: " + str(total_cpu)),
                ('Taken ports', taken_ports)]

    def retrieve_by_highlight(self, key):
        if key is "T":
            return ("Tasks", [Task(self.identifier, self.cluster_identifier, t['taskArn'].split("/")[1], t) for t in ECS_CLIENT.retrieve_tasks_for_container(self.cluster_identifier, self.identifier).values()], None)
        else:
            return (None, [])

    def special_action(self, key):
        if key is "I":
            return ("SSH", self.detail[1]['PrivateIpAddress'])
        else:
            return (None, None)

class Service(EcsButton):

    def __init__(self, identifier, name, cluster_identifier, detail):
        super(Service, self).__init__(identifier, name, detail)
        self.cluster_identifier = cluster_identifier

    def retrieve_children(self):
        return ("Tasks", [Task(self.identifier, self.cluster_identifier, t['taskArn'].split("/")[1], t) for t in ECS_CLIENT.retrieve_tasks_for_service(self.cluster_identifier, self.identifier).values()])

    def retrieve_important_details(self):
        deployment_config = self.detail['deploymentConfiguration']
        min_bracket = deployment_config['minimumHealthyPercent']
        max_bracket = deployment_config['maximumPercent']

        return [('Status', self.detail['status']),
                ('Task Definition', self.detail['taskDefinition']),
                ('Running', self.detail['runningCount']),
                ('Pending', self.detail['pendingCount']),
                ('Desired', self.detail['desiredCount']),
                ('Redeployment bracket', "Min: " + str(min_bracket) + "%, Max: " + str(max_bracket) + "%")]


class Task(EcsButton):

    def __init__(self, service_identifier, cluster_identifier, identifier, detail):
        super(Task, self).__init__(identifier, identifier, detail)
        self.service_identifier = service_identifier
        self.cluster_identifier = cluster_identifier

    def retrieve_children(self):
        return (None, None)

    def rewrite_container(self, container):
        network_bindings = container['networkBindings']
        bindings = [network['bindIP'] + " (" + str(network['hostPort']) + "[host] -> " + str(
            network['containerPort']) + "[network])" for network in network_bindings]
        if bindings is []:
            bindings = "no network binding"
        else:
            bindings = ', '.join(bindings)
        return container['name'] + " -> " + bindings

    def retrieve_important_details(self):
        containers = [self.rewrite_container(cont)
                      for cont in self.detail['containers']]
        return [('Status', self.detail['lastStatus']),
                ('Desired Status', self.detail['desiredStatus']),
                ('Task Definition', self.detail['taskDefinitionArn']),
                (['Container ', ('key', 'I'), 'nstance ID'],
                 self.detail['containerInstanceArn'].split("/", 1)[1]),
                ('Containers', '\n'.join(containers))]

    def retrieve_by_highlight(self, key):
        if key is "I":
            containers = ECS_CLIENT.retrieve_containers(self.cluster_identifier)
            containers_by_id = dict((value[0]['containerInstanceArn'], value) for (key, value) in containers.iteritems())
            return ("Containers", [Container(key, key.split("/")[1], self.cluster_identifier, value) for (key, value) in containers_by_id.iteritems()], self.detail['containerInstanceArn'].split("/", 1)[1])
        else:
            return (None, [])
