#!/usr/bin/python

# Copyright (C) 2006  Michal Piotrowski <michal.k.k.piotrowski@gmail.com>
#		      Linux Testers Group
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os, sys, dircache, string

def check_python_version():
	version = string.split(string.split(sys.version)[0], ".")
	if map(int, version) < [2, 4, 0]:
		print "Python 2.4 or newer is needed"
		sys.exit(1)

def print_error_dialog():
        print "Please install python-dialog package"
        sys.exit(1)

def handle_exit_code(d, code):
	if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
		if code == d.DIALOG_CANCEL:
			msg = "You chose cancel in the last dialog box. Do you want to " \
			"exit Autotest Control Center?"
		else:
			msg = "You pressed ESC in the last dialog box. Do you want to " \
			"exit Autotest Control Center?"
		if d.yesno(msg) == d.DIALOG_OK:
			sys.exit(0)
			return 0
	else:
		return 1

def atcc_t_menu(test_type):
	dir_ls=dircache.listdir('../' + test_type)

	u = []

	for i in dir_ls:
		k = i, "", 0
		if i != ".svn":
		    u.append(k)

	while 1:
		(code, tag) = d.checklist(text=test_type + ":",
			choices=u,
			title=test_type + " menu")
		if handle_exit_code(d, code):
			break
	return tag

def atcc_t_run(res, test_type):
	for i in res:
		print i
		os.system('../bin/autotest ../' + test_type + '/' + i + '/control')

def atcc_main_menu():
	while 1:
		(code, tag) = d.menu(
			"Main menu",
			choices=[("1", "Tests"),
			("2", "Profilers")])
		if handle_exit_code(d, code):
			break
	return tag

def main():
	res=int(atcc_main_menu())
	if res == 1:
		res=atcc_t_menu(test_type = 'tests')
		atcc_t_run(res, test_type = 'tests')
	elif res == 2:
		res=atcc_t_menu(test_type = 'profilers')
		atcc_t_run(res, test_type = 'profilers')
	else:
		print "error: bla2"

check_python_version()

try:
	import dialog
except ImportError:
	print_error_dialog()

d = dialog.Dialog(dialog="dialog")
d.add_persistent_args(["--backtitle", "Autotest Control Center v0.02"])

main()
