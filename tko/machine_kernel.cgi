#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, frontend, display
client_bin = os.path.abspath(os.path.join(tko, '../client/bin'))
sys.path.insert(0, client_bin)
import kernel_versions

db = db.db()


def kernel_group_box(kernel, group, box_data):
	machine_idxs = ['%d' % machine.idx for machine in group.machines()]
	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(','.join(machine_idxs), kernel.idx)
	return display.status_precounted_box(db, box_data, link)


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def main():
	display.print_main_header()

	ret = frontend.get_matrix_data(db, 'machine_group', 'kernel_printable')
	(data, group_list, kernel_list, status_list, job_tags) = ret

	groups = frontend.group.select(db)
	group_names = [display.group_name(g) for g in groups]
	headers = ['Version'] + group_names
	header_row = [ display.box(x, header=True) for x in headers ] 

	kernels = frontend.kernel.select(db)
	kernels.sort(key = kernel_encode, reverse = True)

	matrix = [header_row]
	for kernel in kernels:
		link = 'group_test.cgi?kernel=%s' % kernel.idx
		row = [display.box(kernel.printable, link=link)]
		for group in groups:
			try:
				box_data = data[group.name][kernel.printable]
			except:
				row.append(display.box(None, None))
				continue
			row.append(kernel_group_box(kernel, group, box_data))
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


main()
