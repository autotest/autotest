#!/usr/bin/python

# Copyright (C) 2006  Michal Piotrowski <michal.k.k.piotrowski@gmail.com>
#		      Linux Testers Group
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os, sys, dircache, string, dialog, time

def check_python_version():
	version = string.split(string.split(sys.version)[0], ".")
	if map(int, version) < [2, 4, 0]:
		print "Python 2.4 or newer is needed"
		sys.exit(1)

def handle_exit_code(d, code):
	if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
		if d.yesno("Do you want to exit Autotest Control Center?") == d.DIALOG_OK:
			sys.exit(0)
			return 0
	else:
		return 1

def atcc_t_menu(test_type):
	dir_ls = dircache.listdir(at_dir + '/' + test_type)

	u = []

	for i in dir_ls:
		k = i, "", 0
		if i != ".svn":
			u.append(k)

	while 1:
		(code, tag) = d.checklist(text = test_type + ":", choices = u, title = test_type + " menu")
		break
	return tag

def atcc_t_run(res, test_type):
	os.system('if [ ! -e /tmp/.at/ ]; then mkdir /tmp/.at; fi')
	for i in res:
		print i
		os.system(at_dir + '/bin/autotest ' + at_dir + '/' + test_type + '/' + i + '/control')

		os.system('cp ' + at_dir + '/results/default/status /tmp/.at/' + i + '.status')
		os.system('cp ' + at_dir + '/results/default/' + i + '/debug/stderr /tmp/.at/' + i + '.stderr' )
		os.system('cp ' + at_dir + '/results/default/' + i + '/debug/stdout /tmp/.at/' + i + '.stdout' )

def atcc_tests_results():
	if os.path.exists('/tmp/.at/'):
		dir_ls=dircache.listdir('/tmp/.at/')
	else:
		d.infobox("/tmp/.at/ doesn't exist")
		time.sleep(5)
		return -1

	u = []

	for i in dir_ls:
		k = i, ""
		u.append(k)

	while 1:
		(code, tag) = d.menu("Results:", choices=u, title="Results menu")

		if code == d.DIALOG_CANCEL or code == d.DIALOG_ESC:
			break
		else:
			d.textbox('/tmp/.at/' + tag)

def atcc_configure_set(tag, test_type):
#	file = (at_dir + '/' + test_type + '/' + tag + '/control')
#	f = open(file, 'r+')
#	print f
#	f.seek(11)
#	z = f.readline()
#	f.close()

	while 1:
		(code, answer) = d.inputbox("Config options", init="")

		if code == d.DIALOG_CANCEL or code == d.DIALOG_ESC:
			break
		else:
			file = (at_dir + '/' + test_type + '/' + tag + '/control')
			f = open(file, 'w')
			print f
			value = ("job.runtest(None, \'" + tag + "\', " + answer + ")")
			s = str(value)
			f.seek(0)
			z = f.write(s)
			print z
			f.close()
			break

def atcc_configure(test_type):
	dir_ls = dircache.listdir(at_dir + '/' + test_type)

	u = []

	for i in dir_ls:
		k = i, ""
		if i != ".svn":
			u.append(k)

	while 1:
		(code, tag) = d.menu(test_type + ":", choices=u, title = test_type + " configuration menu")

		if code == d.DIALOG_CANCEL or code == d.DIALOG_ESC:
			break
		else:
			atcc_configure_set(tag, test_type)

def atcc_main_menu():
	while 1:
		(code, tag) = d.menu("Main menu",
			choices=[("1", "Tests"),
			("2", "Profilers"),
			("3", "Tests' results"),
			("4", "Configure tests")])
		if handle_exit_code(d, code):
			break
	return tag

def main():
	while 1:
		res=int(atcc_main_menu())
		if res == 1:
			res=atcc_t_menu(test_type = 'tests')
			atcc_t_run(res, test_type = 'tests')
		elif res == 2:
			res=atcc_t_menu(test_type = 'profilers')
			atcc_t_run(res, test_type = 'profilers')
		elif res == 3:
			atcc_tests_results()
		elif res == 4:
			atcc_configure(test_type = 'tests')
		elif res == 0:
			sys.exit(1)

check_python_version()

menu_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
at_dir = os.path.dirname(menu_dir)

d = dialog.Dialog(dialog="dialog")
d.add_persistent_args(["--backtitle", "Autotest Control Center v0.03"])

main()
