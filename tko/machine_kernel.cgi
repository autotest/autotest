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
	machines = frontend.machine.select(db)
	print_machines_vs_all_kernels(machines)


def status_html(status_count):
	total = sum(status_count.values())
	status_pct = {}
	for status in status_count.keys():
		status_pct[status] = (100 * status_count[status]) / total
	rows = []
	for status in sorted(status_pct.keys(), reverse = True):
		status_word = db.status_word[status]
		# string = "%d&nbsp(%d%%)" % (status_count[status], status_pct[status])
		string = "%d&nbsp;%s" % (status_count[status], status_word)
		box = display.box(string, status_word)
		rows.append("<tr>%s</tr>" % box.html())
	return '<table>%s</table>' % '\n'.join(rows)


def kernel_machine_box(kernel, machine):
	status = None
	status_word = ''
	tests = frontend.test.select(db, { 'kernel_idx' : kernel.idx ,
					   'machine_idx' : machine.idx })

	status_count = {}
	for t in tests:
		if status_count.has_key(t.status_num):
			status_count[t.status_num] +=1
		else:
			status_count[t.status_num] = 1

		if not status or t.status_num < status:
			status = t.status_num
			status_word = db.status_word[status]

	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(machine.idx, kernel.idx)
	if status_word:
		html = '<a href="%s">%s</a>' % (link, status_html(status_count))
	else:
		html = None
	return display.box(html, color_key = status_word)


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def print_machines_vs_all_kernels(machines):
	headers = ['Version'] + [machine.hostname for machine in machines]
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
