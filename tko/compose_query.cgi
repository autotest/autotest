#!/usr/bin/python

"""
Selects all rows and columns that satisfy the condition specified
and draws the matrix. There is a seperate SQL query made for every (x,y)
in the matrix.
"""

print "Content-type: text/html\n"

import sys, os, urllib, cgi, cgitb, re, datetime, time

total_wall_time_start = time.time()

import common
from autotest_lib.tko import display, frontend, db, query_lib
from autotest_lib.client.common_lib import kernel_versions

html_header = """\
<form action="/tko/compose_query.cgi" method="get">
<table border="0">
<tr>
  <td>Column: </td>
  <td>Row: </td>
  <td>Condition: </td>
  <td align="center">
  <a href="http://autotest.kernel.org/wiki/AutotestTKOCondition">Help</a>
  </td>
</tr>
<tr>
  <td>
  <SELECT NAME="columns">
  %s
 </SELECT>
  </td>
  <td>
  <SELECT NAME="rows">
  %s
  </SELECT>
  </td>
  <td>
    <input type="text" name="condition" size="30" value="%s">
    <input type="hidden" name="title" value="%s">
  </td>
  <td align="center"><input type="submit" value="Submit">
  </td>
</tr>
</table>
</form>
<form action="/tko/save_query.cgi" method="get">
<table border="0">
<tr>
 <td>Name your query:&nbsp;&nbsp;</td>
  <td>
    <input type="text" name="label" size="15" value="">
  </td>
  <td align="center">&nbsp;<input type="submit" value="Save Query">
  </td>
 <td>&nbsp;&nbsp;<a href="/tko/query_history.cgi">View saved queries</a></td>
  <td>
    <input type="hidden" name="columns" value="%s">
    <input type="hidden" name="rows" value="%s">
    <input type="hidden" name="condition" value="%s">
  </td>
</tr>
</table>
</form>
"""


next_field = {
    'machine_group': 'hostname',
    'hostname': 'tag',
    'tag': 'tag',

    'kernel': 'test',
    'test': 'label',
    'label': 'tag',

    'reason': 'tag',
    'user': 'tag',
    'status': 'tag',
   
    'time': 'tag',
    'time_daily': 'time',
}


def parse_field(form, form_field, field_default):
    if not form_field in form:
        return field_default
    field_input = form[form_field].value.lower()
    if field_input and field_input in frontend.test_view_field_dict:
        return field_input
    return field_default


def parse_condition(form, form_field, field_default):
    if not form_field in form:
        return field_default
    return form[form_field].value


form = cgi.FieldStorage()

title_field = parse_condition(form, 'title', '')
row = parse_field(form, 'rows', 'kernel')
column = parse_field(form, 'columns', 'machine_group')
condition_field = parse_condition(form, 'condition', '')

if 'brief' in form.keys() and form['brief'].value <> '0':
    display.set_brief_mode()

## caller can specify rows and columns that shall be included into the report
## regardless of whether actual test data is available yet
force_row_field = parse_condition(form,'force_row','')
force_column_field = parse_condition(form,'force_column','')


def split_forced_fields(force_field):
    if force_field:
        return force_field.split()
    else:
        return []

force_row =  split_forced_fields(force_row_field)
force_column =  split_forced_fields(force_column_field)
  
cgitb.enable()
db_obj = db.db()


def construct_link(x, y):
    next_row = row
    next_column = column
    condition_list = []
    if condition_field != '':
        condition_list.append(condition_field)
    if y:
        next_row = next_field[row]
        condition_list.append("%s='%s'" % (row, y))
    if x:
        next_column = next_field[column]
        condition_list.append("%s='%s'" % (column, x))
    next_condition = '&'.join(condition_list)
    link = '/tko/compose_query.cgi?' + urllib.urlencode({'columns': next_column,
               'rows': next_row, 'condition': next_condition,
               'title': title_field})
    return link


def construct_logs_link(x, y, job_tag):
    job_path = frontend.html_root + job_tag + '/'
    test = ''
    if (row == 'test' and
        not y.split('.')[0] in ('boot', 'build', 'install')):
        test = y
    if (column == 'test' and
        not x.split('.')[0] in ('boot', 'build', 'install')):
        test = x
    return '/tko/retrieve_logs.cgi?' + urllib.urlencode({'job' : job_path,
         'test' : test})


def create_select_options(selected_val):
    ret = ""
    for option in sorted(frontend.test_view_field_dict.keys()):
        if selected_val == option:
            selected = " SELECTED"
        else:
            selected = ""

        ret += '<OPTION VALUE="%s"%s>%s</OPTION>\n' % \
                        (option, selected, option)
    return ret


def map_kernel_base(kernel_name):
    ## insert <br> after each / in kernel name
    ## but spare consequtive //
    kernel_name = kernel_name.replace('/','/<br>')
    kernel_name = kernel_name.replace('/<br>/<br>','//')
    return kernel_name


def header_tuneup(field_name, header):
        ## header tune up depends on particular field name and may include:
        ## - breaking header into several strings if it is long url
        ## - creating date from datetime stamp
        ## - possibly, expect more various refinements for different fields
        if field_name == 'kernel':
                return  map_kernel_base(header)
        else:
                return header


# Kernel name mappings -- the kernels table 'printable' field is
# effectively a sortable identifier for the kernel It encodes the base
# release which is used for overall sorting, plus where patches are
# applied it adds an increasing pNNN patch combination identifier
# (actually the kernel_idx for the entry).  This allows sorting
# as normal by the base kernel version and then sub-sorting by the
# "first time we saw" a patch combination which should keep them in
# approximatly date order.  This patch identifier is not suitable
# for display, so we have to map it to a suitable html fragment for
# display.  This contains the kernel base version plus the truncated
# names of all the patches,
#
#     2.6.24-mm1 p112
#     +add-new-string-functions-
#     +x86-amd-thermal-interrupt
# 
# This mapping is produced when the first mapping is request, with
# a single query over the patches table; the result is then cached.
#
# Note: that we only count a base version as patched if it contains
# patches which are not already "expressed" in the base version.
# This includes both -gitN and -mmN kernels.
map_kernel_map = None


def map_kernel_init():
    fields = ['base', 'k.kernel_idx', 'name', 'url']
    map = {}
    for (base, idx, name, url) in db_obj.select(','.join(fields),
            'kernels k,patches p', 'k.kernel_idx=p.kernel_idx'):
        match = re.match(r'.*(-mm[0-9]+|-git[0-9]+)\.(bz2|gz)$', url)
        if match:
            continue

        key = base + ' p%d' % (idx)
        if not map.has_key(key):
            map[key] = map_kernel_base(base) + ' p%d' % (idx)
        map[key] += ('<br>+<span title="' + name + '">' +
                 name[0:25] + '</span>')

    return map


def map_kernel(name):
    global map_kernel_map
    if map_kernel_map is None:
        map_kernel_map = map_kernel_init()

    if map_kernel_map.has_key(name):
        return map_kernel_map[name]

    return map_kernel_base(name.split(' ')[0])


field_map = {
    'kernel':map_kernel
}

sql_wall_time = 0

def gen_matrix():
    where = None
    if condition_field.strip() != '':
        try:
            where = query_lib.parse_scrub_and_gen_condition(
                condition_field, frontend.test_view_field_dict)
            print "<!-- where clause: %s -->" % (where,)
        except:
            msg = "Unspecified error when parsing condition"
            return [[display.box(msg)]]

    wall_time_start = time.time()
    try:
        ## Unfortunately, we can not request reasons of failure always
        ## because it may result in an inflated size of data transfer
        ## (at the moment we fetch 500 bytes of reason descriptions into
        ## each cell )
        ## If 'status' in [row,column] then either width or height
        ## of the table <=7, hence table is not really 2D, and
        ## query_reason is relatively save.
        ## At the same time view when either rows or columns grouped
        ## by status is when users need reasons of failures the most.
        
        ## TO DO: implement [Show/Hide reasons] button or link in
        ## all views and make thorough performance testing 
        test_data = frontend.get_matrix_data(db_obj, column, row, where,
                query_reasons = ('status' in [row,column])
                )
        global sql_wall_time
        sql_wall_time = time.time() - wall_time_start

    except db.MySQLTooManyRows, error:
        return [[display.box(str(error))]]            
    
    for f_row in force_row:
        if not f_row in test_data.y_values:
            test_data.y_values.append(f_row)
    for f_column in force_column:
        if not f_column in test_data.x_values:
            test_data.x_values.append(f_column)

    if not test_data.y_values:
        msg = "There are no results for this query (yet?)."
        return [[display.box(msg)]]

    dict_url = {'columns': row,
               'rows': column, 'condition': condition_field,
               'title': title_field}
    link = '/tko/compose_query.cgi?' + urllib.urlencode(dict_url)
    header_row = [display.box("<center>(Flip Axis)</center>", link=link)]

    for x in test_data.x_values:
        dx = x
        if field_map.has_key(column):
            dx = field_map[column](x)
        x_header = header_tuneup(column, dx)
        link = construct_link(x, None)
        header_row.append(display.box(x_header,header=True,link=link))

    matrix = [header_row]
    # For each row, we are looping horizontally over the columns.
    for y in test_data.y_values:
        dy = y
        if field_map.has_key(row):
            dy = field_map[row](y)
        y_header = header_tuneup(row, dy)
        link = construct_link(None, y)
        cur_row = [display.box(y_header, header=True, link=link)]
        for x in test_data.x_values:
            ## next 2 lines: temporary, until non timestamped
            ## records are in the database
            if x==datetime.datetime(1970,1,1): x = None
            if y==datetime.datetime(1970,1,1): y = None
            try:
                box_data = test_data.data[x][y]
            except:
                cur_row.append(display.box(None, None, 
                           row_label=y, column_label=x))
                continue
            job_tag = test_data.data[x][y].job_tag
            if job_tag:
                link = construct_logs_link(x, y, job_tag)
            else:
                link = construct_link(x, y)

            apnd = display.status_precounted_box(db_obj, box_data,
                                 link, y, x)
            cur_row.append(apnd)
        matrix.append(cur_row)
    return matrix


def main():
    if display.is_brief_mode():
        ## create main grid table only as provided by gen_matrix()
        display.print_table(gen_matrix())
    else:
        # create the actual page 
        print '<html><head><title>'
        print 'Filtered Autotest Results'
        print '</title></head><body>'
        display.print_main_header()
        print html_header % (create_select_options(column),
                     create_select_options(row),
                     condition_field, title_field,
                     ## history form
                     column,row,condition_field)
        if title_field:
            print '<h1> %s </h1>' % (title_field)
        print display.color_keys_row()
        display.print_table(gen_matrix())
        print display.color_keys_row()
        total_wall_time = time.time() - total_wall_time_start
        
        perf_info = '<p style="font-size:x-small;">'
        perf_info += 'sql access wall time = %s secs,' % sql_wall_time
        perf_info += 'total wall time = %s secs</p>' % total_wall_time
        print perf_info
        print '</body></html>'


main()
