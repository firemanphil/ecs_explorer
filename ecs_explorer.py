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

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
	return json.JSONEncoder.default(self, o)


class Cluster:
    clustersByName = dict()
    def __init__(self, identifier, name, detail):
        self.identifier = identifier
        self.name = name
        self.detail = detail

    def retrieve_children(self):
        return [ServicesLabel(self.identifier), ContainersLabel(self.identifier)]

class ServicesLabel:
    def __init__(self, cluster_identifier):
        self.name = "Services"
        self.cluster_identifier = cluster_identifier;
        self.detail = ''
        
    def retrieve_children(self):
        return [Service(s['serviceArn'], s['serviceName'], self.cluster_identifier, s) for s in ecs_client.retrieveServicesForCluster(self.cluster_identifier).values()]

class ContainersLabel:
    def __init__(self, cluster_identifier):
        self.name = "Containers"
        self.cluster_identifier = cluster_identifier;
        self.detail = ''

    def retrieve_children(self):
        return [Container(c['containerInstanceArn'], c['ec2InstanceId'], self.cluster_identifier, c) for c in ecs_client.retrieveContainersForCluster(self.cluster_identifier)]

class Container:

    def __init__(self, identifier, name, cluster_identifier, detail):
        self.identifier = identifier
        self.name = name
        self.cluster_identifier = cluster_identifier;
        self.detail = detail;
    
    def retrieve_children(self):
        return []


class Service:

    def __init__(self, identifier, name, cluster_identifier, detail):
        self.identifier = identifier
        self.name = name
        self.cluster_identifier = cluster_identifier;
        self.detail = detail
    
    def retrieve_children(self):
        return [Task(self.identifier, self.cluster_identifier, t['taskArn'], t) for t in ecs_client.retrieveTasksForService(self.cluster_identifier, self.identifier).values()]

class Task:

    def __init__(self, service_identifier, cluster_identifier, identifier, detail):
        self.service_identifier = service_identifier
        self.cluster_identifier = cluster_identifier
        self.identifier = identifier
        self.name = identifier
        self.detail = detail

    def retrieve_children(self):
        return []

parser = argparse.ArgumentParser()
parser.add_argument('--list', action='store_true')
parser.add_argument("acct_to_assume")
parser.add_argument("role_to_assume")

def enter_handler(button):
    item = currentListByName[button.label]
    children = item.retrieve_children()
    if len(children) > 0:
        subListWalker.set_focus(0)
        del subListWalker.lines[:]
        dict_children = dict((c.name, c) for c in children)
        currentListByName.clear()
        currentListByName.update(dict_children)
        stack.append(children)
        data = [urwid.AttrMap(urwid.Button(c.name, enter_handler), None, 'reveal focus') for c in children ]
        subListWalker.lines.extend(data)
        subListWalker.set_focus(0)
        subListWalker._modified()

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
#            #bottomText = urwid.Text(json.dumps(item.detail, indent=4, sort_keys=True))
#    elif input == 'down':
#        focus_widget, idx = subListBox.get_focus()
#        sys.stderr.write("pressed <down> " + str(subListBox.get_focus()) +"\n") 
#        if idx < len(subListWalker.lines) -1:
#            idx = idx+1
#            subListWalker.set_focus(idx)
#            focus_widget, _ = subListBox.get_focus()
#            name = focus_widget.base_widget.text
#            item = currentListByName[name]
#            #bottomText = urwid.Text(json.dumps(item.detail, indent=4, sort_keys=True))
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
    elif input == 'b':
        if len(stack) > 1:
            del subListWalker.lines[:]
            hi = stack.pop()
            previous = stack[-1]
            currentListByName.clear()
            currentListByName.update(dict((c.name, c) for c in previous))
            data = [urwid.AttrMap(urwid.Button(c.name, enter_handler), None, 'reveal focus') for c in previous ]
            subListWalker.lines.extend(data)
            subListWalker.set_focus(0)
            subListWalker._modified()

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
        text = self.lines[focus].base_widget.label
        item = currentListByName[text]
        bottomText.set_text(json.dumps(item.detail, indent=4, sort_keys=True, cls=DateTimeEncoder))
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

currentListByName.update( dict((c.name, c) for c in clusters))
stack = [clusters]

data = [urwid.AttrMap(urwid.Button(c.name, enter_handler), None, 'reveal focus') for c in clusters ]
subListWalker = LineWalker(data)
subListBox = urwid.ListBox(subListWalker)
div = urwid.Divider()
bottomText = urwid.Text(json.dumps(clusters[0].detail, indent=4, sort_keys=True, cls=DateTimeEncoder))
#bottomText = urwid.Text("here")
totalPile = urwid.Pile([urwid.BoxAdapter(subListBox, 30), div, urwid.AttrMap(bottomText, None, 'reveal focus')])
#totalPile = urwid.Pile([subListBox ,div, urwid.AttrMap(urwid.Text('hi'), None, 'reveal focus')])
top = urwid.Filler(totalPile, valign='top')

layout = urwid.Frame(header=header, body = top, footer = footer)

main_loop = urwid.MainLoop(layout, palette, unhandled_input=exit_on_cr)
main_loop.run()
