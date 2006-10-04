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

def atcc_t_menu(test_type, t):
	dir_ls = dircache.listdir(at_dir + '/' + test_type)

	u = []

	for i in dir_ls:
		k = i, "", 0
		if i != ".svn":
			u.append(k)

	while 1:
		(code, tag) = d.checklist(text = test_type + ":", choices = u, title = t)
		break
	return tag

def atcc_t_run(res, test_type):
	os.system('if [ ! -e ' + menu_dir + '/tmp/ ]; then mkdir ' + menu_dir + '/tmp/; fi')
	os.system('if [ -f ' + menu_dir + '/tmp/Tests\ results ]; then rm ' + menu_dir + '/tmp/Tests\ results; fi')
	for i in res:
		print i
		os.system(at_dir + '/bin/autotest ' + at_dir + '/' + test_type + '/' + i + '/control')

		os.system('cp ' + at_dir + '/results/default/status ' + menu_dir + '/tmp/' + i + '.status')
		os.system('cp ' + at_dir + '/results/default/' + i + '/debug/stderr ' + menu_dir + '/tmp/' + i + '.stderr')
		os.system('cp ' + at_dir + '/results/default/' + i + '/debug/stdout ' + menu_dir + '/tmp/' + i + '.stdout')
		os.system('cat ' + at_dir + '/results/default/status >> ' + menu_dir + '/tmp/Tests\ results')

def atcc_t_p_run(res, test_type):
	os.system('if [ ! -e ' + menu_dir + '/tmp/ ]; then mkdir ' + menu_dir + '/tmp/; fi')
	os.system('if [ -f ' + menu_dir + '/tmp/Tests\ results ]; then rm ' + menu_dir + '/tmp/Tests\ results; fi')

	file = (menu_dir + '/tmp/parallel')
	f = open(file, 'w')
	
	for i in res:
		line = ("def " + i + "():\n")
		z = str(line)
		f.write(z)
		
		file = (at_dir + '/' + test_type + '/' + i + '/control')
		f2 = open(file, 'r')
		k = f2.readlines()

		for i in k:
			x = ("\t" + i + "\n")
			z = str(x)
			f.write(z)

		f2.close()

	f.write('job.parallel(')

	for i in range(len(res)):
		z = ('[' + res[i] + '],')
		z = str(z)
		f.write(z)

	f.write(')')

	f.close()
	
	os.system(at_dir + '/bin/autotest ' + menu_dir + '/tmp/parallel')
	os.system('cat ' + at_dir + '/results/default/status > ' + menu_dir + '/tmp/Tests\ results')

def atcc_tests_results(t):
	if os.path.exists(menu_dir + "/tmp/"):
		dir_ls = dircache.listdir(menu_dir + "/tmp/")
	else:
		d.infobox(menu_dir + "/tmp/ doesn't exist")
		time.sleep(5)
		return -1

	if len(dir_ls) == 0:
		return -1

	u = []

	for i in dir_ls:
		k = i, ""
		u.append(k)

	while 1:
		(code, tag) = d.menu("Results:", choices = u, title = t)

		if code == d.DIALOG_CANCEL or code == d.DIALOG_ESC:
			break
		else:
			d.textbox(menu_dir + '/tmp/' + tag)

def atcc_config_read(tag, test_type):
	file = (at_dir + '/' + test_type + '/' + tag + '/control')
	f = open(file, 'r')

	z = f.readline()
	z = z.split(',')
	x = len(z)

	if x == 2:
		z = ""
	elif x > 2:
		z = z[2:]
		z[-1] = z[-1].rstrip('\n')
		z[-1] = z[-1].rstrip(')')
		m = ""
		for i in z:
			m += (',' + i)

		m = m.lstrip(',')
		m = m.strip()
		z = str(m)

	f.close()

	return z

def atcc_config_write(tag, test_type, answer):
	file = (at_dir + '/' + test_type + '/' + tag + '/control')
	f = open(file, 'w')

	value = ("job.runtest(None, \'" + tag + "\', " + answer + ")")
	s = str(value)
	z = f.write(s)

	f.close()

def atcc_config_show_help(tag, test_type):
	if os.path.exists(at_dir + '/' + test_type + '/' + tag + '/help'):
		d.textbox(at_dir + '/' + test_type + '/' + tag + '/help')
	else:
		d.infobox(at_dir + '/' + test_type + '/' + tag + '/help' " doesn't exist")
		time.sleep(5)

def atcc_config_choose(tag, test_type):
	conf_opt = atcc_config_read(tag, test_type)

	while 1:
		(code, answer) = d.inputbox("Type 'help' to see documentation", init = conf_opt)

		if code == d.DIALOG_CANCEL or code == d.DIALOG_ESC:
			break
		elif answer == "help":
			atcc_config_show_help(tag, test_type)
			continue
		else:
			atcc_config_write(tag, test_type, answer)
			break

def atcc_config(test_type, t):
	dir_ls = dircache.listdir(at_dir + '/' + test_type)

	u = []

	for i in dir_ls:
		k = i, ""
		if i != ".svn" and i != "netperf2" and i != "pktgen" and i != "sparse" and (os.path.exists(at_dir + '/' + test_type + '/' + i + '/control')):
			u.append(k)

	while 1:
		(code, tag) = d.menu(test_type + ":", choices = u, title = t)

		if code == d.DIALOG_CANCEL or code == d.DIALOG_ESC:
			break
		else:
			atcc_config_choose(tag, test_type)

def atcc_upgrade():
	os.system("svn checkout svn://test.kernel.org/autotest/trunk " + at_dir)

def atcc_main_menu():
	while 1:
		(code, tag) = d.menu("Main menu",
			choices = [("1", "Tests"),
			("2", "Parallel tests"),
			("3", "Profilers"),
			("4", "Tests' results"),
			("5", "Configure tests"),
			("6", "Upgrade Autotest")])
		if handle_exit_code(d, code):
			break
	return tag

def main():
	while 1:
		res = int(atcc_main_menu())
		if res == 1:
			res=atcc_t_menu(test_type = 'tests', t = 'Tests selection menu')
			atcc_t_run(res, test_type = 'tests')
		elif res == 2:
			res=atcc_t_menu(test_type = 'tests', t = 'Parallel tests selection menu')
			atcc_t_p_run(res, test_type = 'tests')
		elif res == 3:
			res=atcc_t_menu(test_type = 'profilers', t = 'Profilers selection menu')
			atcc_t_run(res, test_type = 'profilers')
		elif res == 4:
			atcc_tests_results(t = 'Tests\' results menu')
		elif res == 5:
			atcc_config(test_type = 'tests', t = 'Tests configuration menu')
		elif res == 6:
			atcc_upgrade()
		elif res == 0:
			sys.exit(1)

check_python_version()

menu_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
at_dir = os.path.dirname(menu_dir)

d = dialog.Dialog(dialog = "dialog")
d.add_persistent_args(["--backtitle", "Autotest Control Center v0.04"])

main()
