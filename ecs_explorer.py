#!/usr/bin/env python
# encoding: utf-8
import json
import urwid
import threading
import boto3
import datetime
from datetime import datetime
import sys
from collections import defaultdict
from dateutil.tz import tzlocal
import argparse
import pprint
from ecs_client import EcsClient
from urwid.command_map import ACTIVATE

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
	return json.JSONEncoder.default(self, o)

class DetailListBox(urwid.ListBox):

    def __init__(self, body, parent):
        self.parent = parent
        super(DetailListBox, self).__init__(body)

    def keypress(self, size, key):
        if key == 'b':
            self.parent.keypress(size, 'd')
        else:
            urwid.ListBox.keypress(self, size, key)

class EcsButton(urwid.Button):
    
    def __init__(self, identifier, name, detail):
        self.identifier = identifier
        self.detail = detail
        self.name=name
        self.showing_detail = False
        super(EcsButton, self).__init__(name)

    def keypress(self, size, key):
        sys.stderr.write("key was " + key + "\n")
        if key == 'd':
            self.toggle_detail()
        elif key == 'b':
            if len(stack) > 1:
                del subListWalker.lines[:]
                hi = stack.pop()
                previous = stack[-1]
                currentListByName.clear()
                currentListByName.update(dict((c.name, c) for c in previous))
                data = [urwid.AttrMap(c, None, 'reveal focus') for c in previous ]
                subListWalker.lines.extend(data)
                subListWalker.set_focus(0)
                subListWalker._modified()
        elif key == 'u':
            #show detail
            pass
        elif self._command_map[key] == ACTIVATE:
            self.show_children()
        return key

    def toggle_detail(self):
        if not self.showing_detail:
            self.before_detail = layout.contents['body']
            detail_text = json.dumps(self.detail, indent=4, sort_keys=True, cls=DateTimeEncoder)
            lines = detail_text.split('\n')
            text_lines = [urwid.Text(l) for l in lines]
            list_box = DetailListBox(urwid.SimpleFocusListWalker(text_lines), self)
            layout.contents['body'] = (list_box, None) 
            self.showing_detail = True
        else: 
            layout.contents['body'] = self.before_detail
            del self.before_detail
            self.showing_detail = False
    
    def show_children(self):

        children = self.retrieve_children()
        if len(children) > 0:
            subListWalker.set_focus(0)
            del subListWalker.lines[:]
            dict_children = dict((c.name, c) for c in children)
            currentListByName.clear()
            currentListByName.update(dict_children)
            sys.stderr.write("\n"+ str(currentListByName))
            stack.append(children)
            data = [urwid.AttrMap(c, None, 'reveal focus') for c in children ]
            subListWalker.lines.extend(data)
            subListWalker.set_focus(0)
            subListWalker._modified()

    def retrieve_children():
        pass

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
        return [ServicesLabel(self.identifier), ContainersLabel(self.identifier)]

class ServicesLabel(EcsButton):
    def __init__(self, cluster_identifier):
        super(ServicesLabel, self).__init__(cluster_identifier, "Services", "")
        
    def retrieve_children(self):
        return [Service(s['serviceArn'], s['serviceName'], self.identifier, s) for s in ecs_client.retrieveServicesForCluster(self.identifier).values()]

    def retrieve_important_details(self):
        return []

class ContainersLabel(EcsButton):
    def __init__(self, cluster_identifier):
        super(ContainersLabel, self).__init__(cluster_identifier, "Containers", "")

    def retrieve_children(self):
        return [Container(c['containerInstanceArn'], c['ec2InstanceId'], self.identifier, c) for c in ecs_client.retrieveContainersForCluster(self.identifier)]

    def retrieve_important_details(self):
        return []

class Container(EcsButton):

    def __init__(self, identifier, name, cluster_identifier, detail):
        super(Container, self).__init__(identifier, name, detail)
        self.cluster_identifier = cluster_identifier;
    
    def retrieve_children(self):
        return []

    def retrieve_important_details(self):
        return []

class Service(EcsButton):

    def __init__(self, identifier, name, cluster_identifier, detail):
        super(Service, self).__init__(identifier, name, detail)
        self.cluster_identifier = cluster_identifier;
    
    def retrieve_children(self):
        return [Task(self.identifier, self.cluster_identifier, t['taskArn'], t) for t in ecs_client.retrieveTasksForService(self.cluster_identifier, self.identifier).values()]

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
                ('Redeployment bracket', "Min: " + str(min_bracket) + "%, Max: " + str(max_bracket))]
class Task(EcsButton):

    def __init__(self, service_identifier, cluster_identifier, identifier, detail):
        super(Task, self).__init__(identifier, identifier, detail)
        self.service_identifier = service_identifier
        self.cluster_identifier = cluster_identifier

    def retrieve_children(self):
        return []

    def rewriteContainer(self, container):
        networkBindings = container['networkBindings']
        bindings = [network['bindIP'] + " (" + str(network['hostPort']) + "[host] -> " + str(network['containerPort'])+ "[network])" for network in networkBindings]
        if bindings is []:
            bindings = "no network binding"
        else:
            sys.stderr.write( "\n[" + str(bindings) + "]\n")
            bindings = ', '.join(bindings) 
        return container['name'] + " -> " + bindings 
        
    def retrieve_important_details(self):
        containers = [self.rewriteContainer(c) for c in self.detail['containers']]
        return [('Status', self.detail['lastStatus']),
                ('Desired Status', self.detail['desiredStatus']),
                ('Container Instance ID', self.detail['containerInstanceArn'].split("/",1)[1]),
                ('Containers', '\n'.join(containers))]


parser = argparse.ArgumentParser()
parser.add_argument('--list', action='store_true')
parser.add_argument("acct_to_assume")
parser.add_argument("role_to_assume")

def createButtonForListItem(item):
    button  = urwid.Button(c.name)
    return button

def convertDetailsToColumns(details):
    labels = []
    data = []
    for detail in details:
        sys.stderr.write("conv" + str(detail[0]))
        labels.append(detail[0])
        data.append(str(detail[1]))
    text1 = '\n'.join(labels)
    sys.stderr.flush()
    text2 = '\n'.join(data)
    filler1 = urwid.Filler(urwid.Text(text1, 'left'), valign='top')
    filler2 = urwid.Filler(urwid.Text(text2, 'left'), valign='top')
    return [filler1,filler2]

def exit_on_cr(input):
    if input in ('q', 'Q'):
        raise urwid.ExitMainLoop()

#    elif input == 'up':
#        focus_widget, idx = subListBox.get_focus()
#        sys.stderr.write("pressed <up> " + str(subListBox.get_focus()) +"\n") 
#        if idx > 0:
#            idx = idx-1
#
#            subListWalker.set_focus(idx)
#            focus_widget, _ = subListBox.get_focus()
#            name = focus_widget.base_widget.text
#            item = currentListByName[name]
#    elif input == 'down':
#        focus_widget, idx = subListBox.get_focus()
#        sys.stderr.write("pressed <down> " + str(subListBox.get_focus()) +"\n") 
#        if idx < len(subListWalker.lines) -1:
#            idx = idx+1
#            subListWalker.set_focus(idx)
#            focus_widget, _ = subListBox.get_focus()
#            name = focus_widget.base_widget.text
#            item = currentListByName[name]
#    elif input == 'enter':
#        focus_widget, _ = subListBox.get_focus()
#        name = focus_widget.base_widget.text
#        item = currentListByName[name]
#        subListWalker.set_focus(0)
#        del subListWalker.lines[:]
#        children = item.retrieve_children()
#        dict_children = dict((c.name, c) for c in children)
#        currentListByName.clear()
#        currentListByName.update(dict_children)
#        stack.append(children)
#        data = [urwid.AttrMap(urwid.Text(c.name), None, 'reveal focus') for c in children ]
#        subListWalker.lines.extend(data)
#        subListWalker._modified()

class LineWalker(urwid.ListWalker):
    """ListWalker-compatible class for lazily reading file contents."""

    def __init__(self, data):
        self.lines = data
        self.focus = 0

    def get_focus(self):
        sys.stderr.write("get_focus " + str(self.focus) +"\n") 
        return self._get_at_pos(self.focus)

    def set_focus(self, focus):
        sys.stderr.write("set_focus " + str(focus) +"\n") 
        self.focus = focus        
        sys.stderr.write("widg " + str(self.lines))
        text = self.lines[focus].base_widget.label
        item = currentListByName[text]
        columnArray = convertDetailsToColumns(item.retrieve_important_details()) 

        cols.contents = [(columnArray[0], ('weight', 1, False)), (columnArray[1], ('weight', 4, False))]
        
        self._modified()

    def get_next(self, start_from):
        sys.stderr.write("get_next " + str(start_from) +"\n") 
        return self._get_at_pos(start_from + 1)

    def get_prev(self, start_from):
        sys.stderr.write("get_prev " + str(start_from) +"\n") 
        
        return self._get_at_pos(start_from - 1)

    def _get_at_pos(self, pos):
        """Return a widget for the line number passed."""
        sys.stderr.write("_get_at_pos " + str(pos) +"\n") 
        if pos < 0:
            # line 0 is the start of the file, no more above
            return None, None

        if len(self.lines) > pos:
            # we have that line so return it
            return self.lines[pos], pos

        return None, None


currentListByName = dict()

args = parser.parse_args()
ecs_client = EcsClient(args.acct_to_assume, args.role_to_assume)

palette = [('title', 'black', 'white'),
           ('reveal focus', 'black', 'white')]

header = urwid.AttrMap(urwid.Text(u'ECS Explorer'), 'title')
footer = urwid.Text(u'Press \'u\' to update and \'q\' to quit')

clusters = [Cluster(c, k['clusterName'], k) for (c,k) in ecs_client.retrieveClusters().items()]

currentListByName.update( dict((c.label, c) for c in clusters))
stack = [clusters]

data = [urwid.AttrMap(c, None, 'reveal focus') for c in clusters ]
subListWalker = LineWalker(data)
subListBox = urwid.ListBox(subListWalker)
div = urwid.Filler(urwid.Divider(), valign='top')
text1 = urwid.Filler(urwid.Text("text1", 'left'), valign='top')
text2 = urwid.Filler(urwid.Text("text1", 'left'), valign='top')

cols = urwid.Columns([text1, text2], )

totalPile = urwid.Pile([subListBox, cols])
#totalPile = urwid.Pile([('weight', 1,subListBox),('weight', 1, cols)])
#totalPile = urwid.Pile([('weight', 1,subListBox)])
#totalPile = urwid.Pile([urwid.BoxAdapter(subListBox, 30), div,cols])
#top = urwid.Filler(totalPile, valign='top')

layout = urwid.Frame(header=header, body = totalPile, footer = footer)

main_loop = urwid.MainLoop(layout, palette, unhandled_input=exit_on_cr)
main_loop.run()
