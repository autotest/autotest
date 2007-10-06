#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys
sys.stdout.flush()
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, frontend, display
client_bin = os.path.abspath(os.path.join(tko, '../client/bin'))
sys.path.insert(0, client_bin)
import kernel_versions

db = db.db()

def main():

	display.print_main_header()

	machines = frontend.machine.select(db)
	print_machines_vs_all_kernels(machines)


def kernel_machines_box(kernel, machines):
	status = None
	status_word = ''
	tests = []
	for machine in machines:
		where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx }
		tests += frontend.test.select(db, where)

	machine_idxs = ['%d' % machine.idx for machine in machines]
	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(','.join(machine_idxs), kernel.idx)
	return display.status_count_box(db, tests, link)


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def print_machines_vs_all_kernels(machines):
	groups = {}
	for machine in machines:
		if machine.group:
			groupname = machine.group
		else:
			groupname = machine.hostname
		if groups.has_key(groupname):
			groups[groupname].append(machine)
		else:
			groups[groupname] = [machine]
	group_list = sorted(groups.keys())

	headers = ['Version'] + group_list
	header_row = [ display.box(x, header=True) for x in headers ] 

	kernels = frontend.kernel.select(db)
	kernels.sort(key = kernel_encode, reverse = True)

	matrix = [header_row]
	for kernel in kernels:
		row = [display.box(kernel.printable)]
		for group in group_list:
			machines = groups[group]
			row.append(kernel_machines_box(kernel, machines))
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


main()
