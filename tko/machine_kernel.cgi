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


def kernel_group_box(kernel, group):
	tests = group.tests({ 'kernel_idx':kernel.idx })

	machine_idxs = ['%d' % machine.idx for machine in group.machines()]
	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(','.join(machine_idxs), kernel.idx)
	return display.status_count_box(db, tests, link)


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def main():
	display.print_main_header()

	groups = frontend.group.select(db)

	headers = ['Version'] + [g.name for g in groups]
	header_row = [ display.box(x, header=True) for x in headers ] 

	kernels = frontend.kernel.select(db)
	kernels.sort(key = kernel_encode, reverse = True)

	matrix = [header_row]
	for kernel in kernels:
		row = [display.box(kernel.printable)]
		for group in groups:
			row.append(kernel_group_box(kernel, group))
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)


main()
