import os, re, string, sys
import frontend, reason_qualifier

color_map = {
        'header'        : '#e5e5c0', # greyish yellow
        'blank'         : '#ffffff', # white
        'plain_text'    : '#e5e5c0', # greyish yellow
        'borders'       : '#bbbbbb', # grey
        'white'         : '#ffffff', # white
        'green'         : '#66ff66', # green
        'yellow'        : '#fffc00', # yellow
        'red'           : '#ff6666', # red

        #### additional keys for shaded color of a box
        #### depending on stats of GOOD/FAIL
        '100pct'  : '#32CD32', # green, 94% to 100% of success
        '95pct'   : '#c0ff80', # step twrds yellow, 88% to 94% of success
        '90pct'   : '#ffff00', # yellow, 82% to 88%
        '85pct'   : '#ffc040', # 76% to 82%
        '75pct'   : '#ff4040', # red, 1% to 76%
        '0pct'    : '#d080d0', # violet, <1% of success

}

_brief_mode = False


def set_brief_mode():
    global _brief_mode
    _brief_mode = True


def is_brief_mode():
    return _brief_mode


def color_keys_row():
    """ Returns one row table with samples of 'NNpct' colors
            defined in the color_map
            and numbers of corresponding %%
    """
    ### This function does not require maintenance in case of
    ### color_map augmenting - as long as
    ### color keys for box shading have names that end with 'pct'
    keys = filter(lambda key: key.endswith('pct'), color_map.keys())
    def num_pct(key):
        return int(key.replace('pct',''))
    keys.sort(key=num_pct)
    html = ''
    for key in keys:
        html+= "\t\t\t<td bgcolor =%s>&nbsp;&nbsp;&nbsp;</td>\n"\
                        % color_map[key]
        hint = key.replace('pct',' %')
        if hint[0]<>'0': ## anything but 0 %
            hint = 'to ' + hint
        html+= "\t\t\t<td> %s </td>\n" % hint

    html = """
<table width = "500" border="0" cellpadding="2" cellspacing="2">\n
    <tbody>\n
            <tr>\n
%s
            </tr>\n
    </tbody>
</table><br>
""" % html
    return html


def calculate_html(link, data, tooltip=None, row_label=None, column_label=None):
    if not is_brief_mode():
        hover_text = '%s:%s' % (row_label, column_label)
        if data:  ## cell is not empty
            hover_text += '<br>%s' % tooltip
        else:
            ## avoid "None" printed in empty cells
            data = '&nbsp;'
        html = ('<center><a class="info" href="%s">'
                '%s<span>%s</span></a></center>' %
                (link, data, hover_text))
        return html
    # no hover if embedded into AFE but links shall redirect to new window
    if data: ## cell is non empty
        html =  '<a href="%s" target="_blank">%s</a>' % (link, data)
        return html
    else: ## cell is empty
        return '&nbsp;'


class box:
    def __init__(self, data, color_key = None, header = False, link = None,
                 tooltip = None, row_label = None, column_label = None):

        ## in brief mode we display grid table only and nothing more
        ## - mouse hovering feature is stubbed in brief mode
        ## - any link opens new window or tab

        redirect = ""
        if is_brief_mode():
            ## we are acting under AFE
            ## any link shall open new window
            redirect = " target=NEW"

        if data:
            data = "<tt>%s</tt>" % data

        if link and not tooltip:
            ## FlipAxis corner, column and row headers
            self.data = ('<a href="%s"%s>%s</a>' %
                         (link, redirect, data))
        else:
            self.data = calculate_html(link, data, tooltip,
                                       row_label, column_label)

        if color_map.has_key(color_key):
            self.color = color_map[color_key]
        elif header:
            self.color = color_map['header']
        elif data:
            self.color = color_map['plain_text']
        else:
            self.color = color_map['blank']
        self.header = header


    def html(self):
        if self.data:
            data = self.data
        else:
            data = '&nbsp'

        if self.header:
            box_html = 'th'
        else:
            box_html = 'td'

        return "<%s bgcolor=%s>%s</%s>" % \
                                (box_html, self.color, data, box_html)


def grade_from_status(status):
    # % of goodness
    # GOOD (6)  -> 1
    # TEST_NA (8) is not counted
    # ##  If the test doesn't PASS, it FAILS
    # else -> 0

    if status == 6:
        return 1.0
    else:
        return 0.0


def average_grade_from_status_count(status_count):
    average_grade = 0
    total_count = 0
    for key in status_count.keys():
        if key not in (8, 9): # TEST_NA, RUNNING
            average_grade += (grade_from_status(key)
                                    * status_count[key])
            total_count += status_count[key]
    if total_count != 0:
        average_grade = average_grade / total_count
    else:
        average_grade = 0.0
    return average_grade


def shade_from_status_count(status_count):
    if not status_count:
        return None

    ## average_grade defines a shade of the box
    ## 0 -> violet
    ## 0.76 -> red
    ## 0.88-> yellow
    ## 1.0 -> green
    average_grade = average_grade_from_status_count(status_count)

    ## find appropiate keyword from color_map
    if average_grade<0.01:
        shade = '0pct'
    elif average_grade<0.75:
        shade = '75pct'
    elif average_grade<0.85:
        shade = '85pct'
    elif average_grade<0.90:
        shade = '90pct'
    elif average_grade<0.95:
        shade = '95pct'
    else:
        shade = '100pct'

    return shade


def status_html(db, box_data, shade):
    """
    status_count: dict mapping from status (integer key) to count
    eg. { 'GOOD' : 4, 'FAIL' : 1 }
    """
    status_count_subset = box_data.status_count.copy()
    status_count_subset[8] = 0  # Don't count TEST_NA
    status_count_subset[9] = 0  # Don't count RUNNING
    html = "%d&nbsp;/&nbsp;%d " % (status_count_subset.get(6, 0),
                                   sum(status_count_subset.values()))
    if 8 in box_data.status_count.keys():
        html += ' (%d&nbsp;N/A)' % box_data.status_count[8]
    if 9 in box_data.status_count.keys():
        html += ' (%d&nbsp;running)' % box_data.status_count[9]

    if box_data.reasons_list:
        reasons_list = box_data.reasons_list
        aggregated_reasons_list = \
                reason_qualifier.aggregate_reason_fields(reasons_list)
        for reason in aggregated_reasons_list:
            ## a bit of more postprocessing
            ## to look nicer in a cell
            ## in future: to do subtable within the cell
            reason = reason.replace('<br>','\n')
            reason = reason.replace('<','[').replace('>',']')
            reason = reason.replace('|','\n').replace('&',' AND ')
            reason = reason.replace('\n','<br>')
            html += '<br>' + reason

    tooltip = ""
    for status in sorted(box_data.status_count.keys(), reverse = True):
        status_word = db.status_word[status]
        tooltip += "%d %s " % (box_data.status_count[status], status_word)
    return (html,tooltip)


def status_count_box(db, tests, link = None):
    """
    Display a ratio of total number of GOOD tests
    to total number of all tests in the group of tests.
    More info (e.g. 10 GOOD, 2 WARN, 3 FAIL) is in tooltips
    """
    if not tests:
        return box(None, None)

    status_count = {}
    for test in tests:
        count = status_count.get(test.status_num, 0)
        status_count[test.status_num] = count + 1
    return status_precounted_box(db, status_count, link)


def status_precounted_box(db, box_data, link = None,
                                 x_label = None, y_label = None):
    """
    Display a ratio of total number of GOOD tests
    to total number of all tests in the group of tests.
    More info (e.g. 10 GOOD, 2 WARN, 3 FAIL) is in tooltips
    """
    status_count = box_data.status_count
    if not status_count:
        return box(None, None)

    shade = shade_from_status_count(status_count)
    html,tooltip = status_html(db, box_data, shade)
    precounted_box = box(html, shade, False, link, tooltip,
                            x_label, y_label)
    return precounted_box


def print_table(matrix):
    """
    matrix: list of lists of boxes, giving a matrix of data
    Each of the inner lists is a row, not a column.

    Display the given matrix of data as a table.
    """

    print ('<table bgcolor="%s" cellspacing="1" cellpadding="5" '
           'style="margin-right: 200px;">') % (
           color_map['borders'])
    for row in matrix:
        print '<tr>'
        for element in row:
            print element.html()
        print '</tr>'
    print '</table>'


def sort_tests(tests):
    kernel_order = ['patch', 'config', 'build', 'mkinitrd', 'install']

    results = []
    for kernel_op in kernel_order:
        test = 'kernel.' + kernel_op
        if tests.count(test):
            results.append(test)
            tests.remove(test)
    if tests.count('boot'):
        results.append('boot')
        tests.remove('boot')
    return results + sorted(tests)


def print_main_header():
    hover_css="""\
a.info{
position:relative; /*this is the key*/
z-index:1
color:#000;
text-decoration:none}

a.info:hover{z-index:25;}

a.info span{display: none}

a.info:hover span{ /*the span will display just on :hover state*/
display:block;
position:absolute;
top:1em; left:1em;
min-width: 100px;
overflow: visible;
border:1px solid #036;
background-color:#fff; color:#000;
text-align: left
}
"""
    print '<head><style type="text/css">'
    print 'a { text-decoration: none }'
    print hover_css
    print '</style></head>'
    print '<h2>'
    print '<a href="compose_query.cgi">Functional</a>'
    print '&nbsp&nbsp&nbsp'
    print '<a href="machine_benchmark.cgi">Performance</a>'
    print '&nbsp&nbsp&nbsp'
    print '<a href="http://crackerjack.good-day.net/cjk/compare_results?col=!d&row=!d">Crackerjack</a>'
    print '&nbsp&nbsp&nbsp'
    print '<a href="http://autotest.kernel.org">[About Page]</a>'
    print '</h2><p>'


def group_name(group):
    name = re.sub('_', '<br>', group.name)
    if re.search('/', name):
        (owner, machine) = name.split('/', 1)
        name = owner + '<br>' + machine
    return name

def print_add_test_form(available_params, attributes, cleared):
    print '<form method="post">'
    print '<input type="hidden" name="attributes" value="%s" />' % attributes
    print '<input type="hidden" name="cleared" value="%s" />' % cleared
    print '<select name="key">'
    for text in available_params:
        print '<option value="%s">%s</option>' % (text, text)
    print '</select>'
    print '<input type="submit" name="add" value="Add test" />'
    print '<input type="submit" name="clear" value="Clear all tests" />'
    print '<input type="submit" name="reset" value="Reset" />'
    print '</form>'
