#!/usr/bin/env python
# encoding: utf-8
import json
import datetime
from datetime import datetime
import string
import subprocess
import argparse
import urwid
from urwid.command_map import ACTIVATE
from ecs_client import EcsClient
from widgets import Cluster 
from widgets import RefreshableItems
from settings import SSH_SCRIPT
from settings import ECS_CLIENT

class BodyController(object):

    EMPTY_FILTER_TEXT = "< start typing to filter the results >"

    def __init__(self, initial_buttons):
        self.list_stack = [initial_buttons]
        self.all_styled_buttons = [urwid.AttrMap(b, None, 'reveal focus')
                                   for b in initial_buttons.items]
        self.list_walker = ChooseFromListWalker(self.all_styled_buttons, self)
        list_box = ChooseFromListBox(self.list_walker)

        column_array = convert_details_to_columns(
            initial_buttons.items[0].retrieve_important_details())

        self.cols = urwid.Columns(
            [('weight', 1, column_array[0]), ('weight', 4, column_array[1])], )
        self.detail_view = False
        self.base_title_text = self.list_stack[-1].items_title
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
            previous = self.list_stack[-1]
            self.all_styled_buttons = [urwid.AttrMap(c, None, 'reveal focus') for c in previous.items]
            self.base_title_text = previous.items_title
            self.title.base_widget.set_text(self.base_title_text + " " + self.EMPTY_FILTER_TEXT)
            item.lines.extend(self.all_styled_buttons)
            item.set_focus(0)
            item._modified()

    def show_children(self, list_walker):
        item = list_walker.lines[list_walker.focus].base_widget
        refreshable_items = RefreshableItems(item.retrieve_children, [])

        self.show_next_level(list_walker, refreshable_items)

    def update(self, list_walker):
        current = self.list_stack.pop()
        current.refresh()
        self.show_next_level(list_walker, current, current.highlighted)

    def show_next_level(self, list_walker, new_items, highlight_text=None):
        if new_items:
            self.base_title_text = new_items.items_title
            self.title.base_widget.set_text(self.base_title_text + " " + self.EMPTY_FILTER_TEXT)
            list_walker.set_focus(0)
            del list_walker.lines[:]
            self.list_stack.append(new_items)
            self.all_styled_buttons = [urwid.AttrMap(ch, None, 'reveal focus') for ch in new_items.items]
            list_walker.lines.extend(self.all_styled_buttons)
            if highlight_text is None:
                list_walker.set_focus(0)
            else:
                list_walker.focus_on(highlight_text)
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
        self.list_walker.lines = list(filter(lambda item: item.base_widget.contains_word(self.filter_string), self.all_styled_buttons))
        if len(self.list_walker.lines) > 0:
            self.list_walker.set_focus(0)
        self.list_walker._modified()

    def pass_special_instruction(self, list_walker, key):
        item = list_walker.lines[list_walker.focus].base_widget
        type_of_action, args = item.special_action(key)
        key_dealt_with = False
        if type_of_action is "SSH" and SSH_SCRIPT is not None:
            subprocess.call([SSH_SCRIPT, args])
            key_dealt_with = True

        if not key_dealt_with:
            result = RefreshableItems(item.retrieve_by_highlight, key)
            if len(result.items) is 0:
                return key
            self.show_next_level(list_walker, result, highlight_text=result.highlighted)


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

def convert_details_to_columns(details):
    labels = []
    data = []
    for detail in details:
        if type(detail[0]) is list:
            labels.extend(detail[0])
        else:
            labels.append(detail[0])
        labels.append('\n')
        data.append(str(detail[1]))
    text2 = '\n'.join(data)
    if len(labels) == 0:
        labels = ''
        text2 = ''
    filler1 = urwid.Filler(urwid.Text(labels, 'left'), valign='top')
    filler2 = urwid.Filler(urwid.Text(text2, 'left'), valign='top')
    return [filler1, filler2]

def exit_on_cr(key):
    if isinstance(key, basestring) and key in 'Q':
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

    def focus_on(self, text):
        texts = [s.base_widget.label for s in self.lines]
        self.set_focus(texts.index(text))

    def set_focus(self, focus):
        self.focus = focus
        BODY_CONTROLLER.item_focus_change(self.lines[focus].base_widget)

        self._modified()

    def get_next(self, start_from):
        return self._get_at_pos(start_from + 1)

    def get_prev(self, start_from):

        return self._get_at_pos(start_from - 1)

    def _get_at_pos(self, pos):
        if pos < 0:
            return None, None

        if len(self.lines) > pos:
            return self.lines[pos], pos

        return None, None

    def keypress(self, size, key):
        if key in list(string.ascii_lowercase) or key == "backspace":
            self.controller.filter_by(key)
        elif key == 'D':
            BODY_CONTROLLER.toggle_detail(self.lines[self.focus].base_widget)
        elif key == 'B':
            BODY_CONTROLLER.show_parent_list(self)
        elif key == 'U':
            BODY_CONTROLLER.update(self)
        elif key in list(string.ascii_uppercase):
            self.controller.pass_special_instruction(self, key)
        elif self.get_focus()[0] is not None and self.get_focus()[0]._command_map[key] == ACTIVATE:
            BODY_CONTROLLER.show_children(self)
        return key



PALETTE = [('title', 'yellow', 'dark blue'),
           ('reveal focus', 'black', 'white'),
           ('key', 'yellow', 'dark blue', ('standout','underline'))]
FOOTER = urwid.AttrMap(urwid.Text(
    u'Press \'U\' to update, \'<enter>\' to look at sub-resources,\'D\' to look at more detail, \'B\' to go back to the previous page and \'Q\' to quit'), 'title')

def retrieve_clusters():
    return ('Clusters', [Cluster(c, k['clusterName'], k)
            for (c, k) in ECS_CLIENT.retrieve_clusters().items()])

BODY_CONTROLLER = BodyController(RefreshableItems(retrieve_clusters, []))

LAYOUT = urwid.Frame(body=BODY_CONTROLLER.body, footer=FOOTER)

def __main__():
    MAIN_LOOP = urwid.MainLoop(LAYOUT, PALETTE, unhandled_input=exit_on_cr)
    MAIN_LOOP.run()
