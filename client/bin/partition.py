"""
This is a high level partition module that executes the contents of
base_partition.py and if it exists the contents of site_partition.py.
"""
import os

execfile(os.path.join(os.path.dirname(__file__), 'base_partition.py'))

__site_path = os.path.join(os.path.dirname(__file__), 'site_partition.py')
if os.path.exists(__site_path):
    execfile(__site_path)
