#!/usr/bin/python

import cgi, cgitb, os, sys
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, frontend, display
client_bin = os.path.abspath(os.path.join(tko, '../client/bin'))
sys.path.insert(0, client_bin)
import kernel_versions

db = db.db()


def main():
	print "Content-type: text/html\n"
	print_machines_vs_all_kernels(['cagg2', 'cagg4', 'cagg6', 'elm3b163', 'elm3b163.beaverton.ibm.com', 'dirt.ltc.austin.ibm.com', 'bucket.ltc.austin.ibm.com'])


def kernel_machine_box(kernel, machine):
	status = None
	status_word = ''
	tests = frontend.test.select(db, { 'kernel_idx' : kernel.idx ,
					   'machine' : machine })
	for t in tests:
		if not status or t.status_num < status:
			status = t.status_num
			status_word = db.status_word[status]

	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(machine, kernel.idx)
	if status_word:
		html = '<a href="%s">%s</a>' % (link, status_word)
	else:
		html = None
	return display.box(html, color_key = status_word)


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def print_machines_vs_all_kernels(machines):
	headers = ['Version'] + machines
	header_row = [ display.box(x, header=True) for x in headers ] 

	kernels = frontend.kernel.select(db)
	kernels.sort(key = kernel_encode, reverse = True)

	matrix = [header_row]
	for kernel in kernels:
		row = [display.box(kernel.printable)]
		for machine in machines:
			row.append(kernel_machine_box(kernel, machine))
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


main()
