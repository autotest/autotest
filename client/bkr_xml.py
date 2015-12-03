# bkr_xml.py
#
# Copyright (C) 2011 Jan Stancek <jstancek@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""
module to parse beaker xml recipe
"""
__author__ = """Copyright Jan Stancek 2011"""

import logging
import os
from xml.dom import minidom

log = logging


def xml_attr(node, key, default=None):
    try:
        return str(node.attributes[key].value)
    except:
        return default


def xml_get_nodes(node, tag):
    return [n for n in node.childNodes if n.nodeName == tag]


class Recipe(object):

    def __init__(self):
        self.tasks = []
        self.id = -1
        self.job_id = -1
        self.exclude_dir = []


class Task(object):

    """
        Simple record to store task properties
    """

    def __init__(self):
        self.name = ''
        self.params = {}
        self.rpmName = ''
        self.rpmPath = ''
        self.timeout = ''
        self.exclude_dir = []
        self.id = -1

    def __str__(self):
        return "- %s %s" % (self.name, str(self.params))

    def __repr__(self):
        return "%s %s" % (self.name, str(self.params))

    def get_param(self, key, default=None):
        if key in self.params:
            return self.params[key]
        else:
            return default


class BeakerXMLParser(object):

    """
        Handles parsing of beaker job xml
    """

    def __init__(self):
        self.recipes = {}

    def parse_from_file(self, file_name):
        log.debug('BeakerXMLParser - opening file: %s', file_name)
        f = open(os.path.expanduser(file_name), 'r')
        contents = f.read()
        f.close()
        log.debug('BeakerXMLParser - content read ok')
        return self.parse_xml(contents)

    def parse_xml(self, xml):
        """
        Returns dict, mapping hostname to recipe
        """
        log.debug('Parsing recipes')
        log.debug("xml type is %s" % type(xml))
        doc = minidom.parseString(xml)
        recipe_nodes = doc.getElementsByTagName('recipe')

        self.handle_recipes(recipe_nodes)
        log.debug('Parsing recipes ok')
        return self.recipes

    def handle_recipes(self, recipe_nodes):
        for recipe_node in recipe_nodes:
            self.handle_recipe(recipe_node)

    def handle_recipe(self, recipe_node):
        hostname = recipe_node.getAttribute('system')
        recipe = Recipe()
        recipe.id = recipe_node.getAttribute('id')
        recipe.job_id = recipe_node.getAttribute('job_id')
        log.debug('Parsing recipe with id: <%s>', recipe.id)
        #tasks = recipe.getElementsByTagName('task')
        task_nodes = xml_get_nodes(recipe_node, 'task')
        self.handle_tasks(recipe, task_nodes)
        self.recipes[hostname] = recipe
        return True

    def handle_tasks(self, recipe, task_nodes):
        for task_node in task_nodes:
            self.handle_task(recipe, task_node)

    def handle_task(self, recipe, task_node):
        task = Task()
        task.name = task_node.getAttribute('name')
        task.id = task_node.getAttribute('id')
        task.timeout = task_node.getAttribute('max_time') or task_node.getAttribute('avg_time')
        task.status = task_node.getAttribute('status')
        log.debug('Parsing task with id: <%s>', task.id)

        recipe.tasks.append(task)

        params_tags = xml_get_nodes(task_node, 'params')
        if params_tags:
            param_nodes = params_tags[0].getElementsByTagName('param')
            self.handle_task_params(task, param_nodes)

        rpm_nodes = xml_get_nodes(task_node, 'rpm')
        task.rpmName = rpm_nodes[0].getAttribute('name')
        task.rpmPath = rpm_nodes[0].getAttribute('path')

    def handle_task_params(self, task, param_nodes):
        for param_node in param_nodes:
            self.handle_task_param(task, param_node)

    def handle_task_param(self, task, param_node):
        param_name = param_node.getAttribute('name')
        param_value = param_node.getAttribute('value')
        task.params[param_name] = param_value
