#!/usr/bin/env python
# encoding: utf-8
import json
import datetime
from datetime import datetime
import sys
import string
import argparse
from ecs_client import EcsClient
from urwid.command_map import ACTIVATE
import urwid

class BodyController(object):

    EMPTY_FILTER_TEXT = "< start typing to filter the results >"

    def __init__(self, initial_buttons):
        self.list_stack = [('Clusters', initial_buttons)]
        self.all_styled_buttons = [urwid.AttrMap(b, None, 'reveal focus')
                          for b in initial_buttons]
        self.list_walker = ChooseFromListWalker(self.all_styled_buttons, self)
        list_box = ChooseFromListBox(self.list_walker)

        column_array = convert_details_to_columns(
            initial_buttons[0].retrieve_important_details())

        self.cols = urwid.Columns(
            [('weight', 1, column_array[0]), ('weight', 4,column_array[1])], )
        self.detail_view = False
        self.base_title_text = self.list_stack[-1][0]
        self.title = urwid.AttrMap(urwid.Text(self.base_title_text + " " + self.EMPTY_FILTER_TEXT), 'title')
        self.cols_title = urwid.AttrMap(urwid.Text(u'Attributes'), 'title')
        self.body = urwid.Pile([(2, urwid.Filler(self.title, valign='top')), list_box, (
            2, urwid.Filler(self.cols_title, valign='top')), self.cols])
        self.before_detail = None
        self.filter_string = ""

    def item_focus_change(self, item):
        column_array = convert_details_to_columns(
            item.retrieve_important_details())

        self.cols.contents = [
            (column_array[0], ('weight', 1, False)), (column_array[1], ('weight', 4, False))]

    def toggle_detail(self, item):
        if not self.detail_view:
            self.before_detail = self.body
            detail_text = json.dumps(
                item.detail, indent=4, sort_keys=True, cls=DateTimeEncoder)
            lines = detail_text.split('\n')
            text_lines = [urwid.Text(l) for l in lines]
            list_box = DetailListBox(
                urwid.SimpleFocusListWalker(text_lines), self)
            self.body = list_box
            LAYOUT.contents['body'] = (self.body, None)
            self.detail_view = True
        else:
            self.body = self.before_detail
            LAYOUT.contents['body'] = (self.body, None)
            del self.before_detail
            self.detail_view = False

    def show_parent_list(self, item):
        if len(self.list_stack) > 1:
            del item.lines[:]
            self.list_stack.pop()
            top_title, previous = self.list_stack[-1]
            self.all_styled_buttons = [urwid.AttrMap(c, None, 'reveal focus') for c in previous]
            self.base_title_text = top_title
            self.title.base_widget.set_text(self.base_title_text + " " + self.EMPTY_FILTER_TEXT)
            item.lines.extend(self.all_styled_buttons)
            item.set_focus(0)
            item._modified()

    def show_children(self, list_walker):
        item = list_walker.lines[list_walker.focus].base_widget
        top_title, children = item.retrieve_children()

        if children:
            self.base_title_text = top_title
            self.title.base_widget.set_text(self.base_title_text + " " + self.EMPTY_FILTER_TEXT)
            list_walker.set_focus(0)
            del list_walker.lines[:]
            self.list_stack.append((top_title, children))
            self.all_styled_buttons = [urwid.AttrMap(ch, None, 'reveal focus') for ch in children]
            list_walker.lines.extend(self.all_styled_buttons)
            list_walker.set_focus(0)
            list_walker._modified()
    
    def filter_by(self, key):
        if key == "backspace":
            self.filter_string = self.filter_string[:-1]
        else:
            self.filter_string += str(key)
        if len(self.filter_string) > 0: 
            self.title.base_widget.set_text(self.base_title_text + " - filter=" + self.filter_string)
        else:
            self.title.base_widget.set_text(self.base_title_text + " " + self.EMPTY_FILTER_TEXT)
        self.list_walker.lines = list(filter(lambda item : item.base_widget.contains_word(self.filter_string), self.all_styled_buttons))
        if len(self.list_walker.lines) > 0:
            self.list_walker.set_focus(0)
        self.list_walker._modified()

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


class DetailListBox(urwid.ListBox):

    def __init__(self, body, controller):
        self.controller = controller
        super(DetailListBox, self).__init__(body)

    def keypress(self, size, key):
        if key == 'B':
            self.controller.toggle_detail(self)
        else:
            super(DetailListBox, self).keypress(size, key)


class EcsButton(urwid.Button):

    def __init__(self, identifier, name, detail):
        self.identifier = identifier
        self.detail = detail
        self.name = name
        self.showing_detail = False
        super(EcsButton, self).__init__(name)

    def retrieve_children(self):
        pass

    def contains_word(self, word):
        return word.lower() in self.name.lower()

class Cluster(EcsButton):
    clustersByName = dict()

    def __init__(self, identifier, name, detail):
        super(Cluster, self).__init__(identifier, name, detail)

    def retrieve_important_details(self):
        return [("Status", self.detail['status']),
                ("Active Services", self.detail['activeServicesCount']),
                ("Running Tasks", self.detail['runningTasksCount']),
                ("Pending Tasks", self.detail['pendingTasksCount']),
                ("Containers", self.detail['registeredContainerInstancesCount'])]

    def retrieve_children(self):
        return ("Choose sub-resource", [ServicesLabel(self.identifier), ContainersLabel(self.identifier)])


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
                ('Private IP', self.detail[1]['PrivateIpAddress']),
                ('Private DNS Name', self.detail[1]['PrivateDnsName']),
                ('Public DNS Name', self.detail[1]['PublicDnsName']),
                ('Running Tasks', cont_detail['runningTasksCount']),
                ('Pending Tasks', cont_detail['pendingTasksCount']),
                ('AMI Id', ami_id),
                ('Instance Type', instance_type),
                ('Availability Zone', availability_zone),
                ('Memory', 'Available: ' + str(available_memory) +
                 " Total: " + str(total_memory)),
                ('CPU', 'Available: ' + str(available_cpu) +
                 " Total: " + str(total_cpu)),
                ('Taken ports', taken_ports)]


class Service(EcsButton):

    def __init__(self, identifier, name, cluster_identifier, detail):
        super(Service, self).__init__(identifier, name, detail)
        self.cluster_identifier = cluster_identifier

    def retrieve_children(self):
        return ("Tasks", [Task(self.identifier, self.cluster_identifier, t['taskArn'].split("/")[1], t) for t in ECS_CLIENT.retrieve_tasks(self.cluster_identifier, self.identifier).values()])

    def retrieve_important_details(self):
        deployment_config = self.detail['deploymentConfiguration']
        min_bracket = deployment_config['minimumHealthyPercent']
        max_bracket = deployment_config['maximumPercent']
        desired = self.detail['desiredCount']

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
                ('Container Instance ID',
                 self.detail['containerInstanceArn'].split("/", 1)[1]),
                ('Containers', '\n'.join(containers))]



def convert_details_to_columns(details):
    labels = []
    data = []
    for detail in details:
        labels.append(detail[0])
        data.append(str(detail[1]))
    text1 = '\n'.join(labels)
    text2 = '\n'.join(data)
    filler1 = urwid.Filler(urwid.Text(text1, 'left'), valign='top')
    filler2 = urwid.Filler(urwid.Text(text2, 'left'), valign='top')
    return [filler1, filler2]


def exit_on_cr(key):
    if key in ('Q'):
        raise urwid.ExitMainLoop()


class ChooseFromListBox(urwid.ListBox):

    def keypress(self, size, key):
        return super(ChooseFromListBox, self).keypress(size, self.body.keypress(size, key))


class ChooseFromListWalker(urwid.ListWalker):

    def __init__(self, data, controller):
        self.all_line = data
        self.lines = data
        self.focus = 0
        self.controller = controller

    def get_focus(self):
        return self._get_at_pos(self.focus)

    def set_focus(self, focus):
        self.focus = focus
        BODY_CONTROLLER.item_focus_change(self.lines[focus].base_widget)

        self._modified()

    def get_next(self, start_from):
        return self._get_at_pos(start_from + 1)

    def get_prev(self, start_from):

        return self._get_at_pos(start_from - 1)

    def _get_at_pos(self, pos):
        """Return a widget for the line number passed."""
        if pos < 0:
            return None, None

        if len(self.lines) > pos:
            return self.lines[pos], pos

        return None, None

    def keypress(self, size, key):
        if key in list(string.ascii_lowercase) or key =="backspace":
            self.controller.filter_by(key)
        elif key == 'D':
            BODY_CONTROLLER.toggle_detail(self.lines[self.focus].base_widget)
        elif key == 'B':
            BODY_CONTROLLER.show_parent_list(self)
        elif key == 'U':
            # show detail
            pass
        elif self.get_focus()[0] is not None and self.get_focus()[0]._command_map[key] == ACTIVATE:
            BODY_CONTROLLER.show_children(self)
        return key

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--role", default=None, help='An STS role to assume')

ARGS = PARSER.parse_args()
ECS_CLIENT = EcsClient(ARGS.role)

PALETTE = [('title', 'yellow', 'dark blue'),
           ('reveal focus', 'black', 'white')]

FOOTER = urwid.AttrMap(urwid.Text(
    u'Press \'U\' to update, \'<enter>\' to look at sub-resources,\'D\' to look at more detail, \'B\' to go back to the previous page and \'Q\' to quit'), 'title')

CLUSTERS = [Cluster(c, k['clusterName'], k)
            for (c, k) in ECS_CLIENT.retrieve_clusters().items()]
CLUSTERS.sort(lambda x, y: cmp(x.name, y.name))
BODY_CONTROLLER = BodyController(CLUSTERS)

LAYOUT = urwid.Frame(body=BODY_CONTROLLER.body, footer=FOOTER)

def __main__():
    MAIN_LOOP = urwid.MainLoop(LAYOUT, PALETTE, unhandled_input=exit_on_cr)
    MAIN_LOOP.run()
