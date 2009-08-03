import base64, os, tempfile, operator, pickle, datetime, django.db
import os.path, getpass
from math import sqrt

# When you import matplotlib, it tries to write some temp files for better
# performance, and it does that to the directory in MPLCONFIGDIR, or, if that
# doesn't exist, the home directory. Problem is, the home directory is not
# writable when running under Apache, and matplotlib's not smart enough to
# handle that. It does appear smart enough to handle the files going
# away after they are written, though.

temp_dir = os.path.join(tempfile.gettempdir(),
                        '.matplotlib-%s' % getpass.getuser())
if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)
os.environ['MPLCONFIGDIR'] = temp_dir

import matplotlib
matplotlib.use('Agg')

import matplotlib.figure, matplotlib.backends.backend_agg
import StringIO, colorsys, PIL.Image, PIL.ImageChops
from autotest_lib.frontend.afe import readonly_connection
from autotest_lib.frontend.afe.model_logic import ValidationError
from autotest_lib.frontend.afe.simplejson import encoder
from autotest_lib.client.common_lib import global_config
from autotest_lib.new_tko.tko import models, tko_rpc_utils

_FIGURE_DPI = 100
_FIGURE_WIDTH_IN = 10
_FIGURE_BOTTOM_PADDING_IN = 2 # for x-axis labels

_SINGLE_PLOT_HEIGHT = 6
_MULTIPLE_PLOT_HEIGHT_PER_PLOT = 4

_MULTIPLE_PLOT_MARKER_TYPE = 'o'
_MULTIPLE_PLOT_MARKER_SIZE = 4
_SINGLE_PLOT_STYLE = 'bs-' # blue squares with lines connecting
_SINGLE_PLOT_ERROR_BAR_COLOR = 'r'

_LEGEND_FONT_SIZE = 'xx-small'
_LEGEND_HANDLE_LENGTH = 0.03
_LEGEND_NUM_POINTS = 3
_LEGEND_MARKER_TYPE = 'o'

_LINE_XTICK_LABELS_SIZE = 'x-small'
_BAR_XTICK_LABELS_SIZE = 8

_json_encoder = encoder.JSONEncoder()

class NoDataError(Exception):
    """\
    Exception to raise if the graphing query returned an empty resultset.
    """


def _colors(n):
    """\
    Generator function for creating n colors. The return value is a tuple
    representing the RGB of the color.
    """
    for i in xrange(n):
        yield colorsys.hsv_to_rgb(float(i) / n, 1.0, 1.0)


def _resort(kernel_labels, list_to_sort):
    """\
    Resorts a list, using a list of kernel strings as the keys. Returns the
    resorted list.
    """

    labels = [tko_rpc_utils.KernelString(label) for label in kernel_labels]
    resorted_pairs = sorted(zip(labels, list_to_sort))

    # We only want the resorted list; we are not interested in the kernel
    # strings.
    return [pair[1] for pair in resorted_pairs]


def _quote(string):
    return "%s%s%s" % ("'", string.replace("'", r"\'"), "'")


_HTML_TEMPLATE = """\
<html><head></head><body>
<img src="data:image/png;base64,%s" usemap="#%s"
  border="0" alt="graph">
<map name="%s">%s</map>
</body></html>"""

_AREA_TEMPLATE = """\
<area shape="rect" coords="%i,%i,%i,%i" title="%s"
href="#"
onclick="%s(%s); return false;">"""


class MetricsPlot(object):
    def __init__(self, query_dict, plot_type, inverted_series, normalize_to,
                 drilldown_callback):
        """
        query_dict: dictionary containing the main query and the drilldown
            queries.  The main query returns a row for each x value.  The first
            column contains the x-axis label.  Subsequent columns contain data
            for each series, named by the column names.  A column named
            'errors-<x>' will be interpreted as errors for the series named <x>.

        plot_type: 'Line' or 'Bar', depending on the plot type the user wants

        inverted_series: list of series that should be plotted on an inverted
            y-axis

        normalize_to:
            None - do not normalize
            'first' - normalize against the first data point
            'x__%s' - normalize against the x-axis value %s
            'series__%s' - normalize against the series %s

        drilldown_callback: name of drilldown callback method.
        """
        self.query_dict = query_dict
        if plot_type == 'Line':
            self.is_line = True
        elif plot_type == 'Bar':
            self.is_line = False
        else:
            raise ValidationError({'plot' : 'Plot must be either Line or Bar'})
        self.plot_type = plot_type
        self.inverted_series = inverted_series
        self.normalize_to = normalize_to
        if self.normalize_to is None:
            self.normalize_to = ''
        self.drilldown_callback = drilldown_callback


class QualificationHistogram(object):
    def __init__(self, query, filter_string, interval, drilldown_callback):
        """
        query: the main query to retrieve the pass rate information.  The first
            column contains the hostnames of all the machines that satisfied the
            global filter. The second column (titled 'total') contains the total
            number of tests that ran on that machine and satisfied the global
            filter. The third column (titled 'good') contains the number of
            those tests that passed on that machine.

        filter_string: filter to apply to the common global filter to show the
                       Table View drilldown of a histogram bucket

        interval: interval for each bucket. E.g., 10 means that buckets should
                  be 0-10%, 10%-20%, ...

        """
        self.query = query
        self.filter_string = filter_string
        self.interval = interval
        self.drilldown_callback = drilldown_callback


def _create_figure(height_inches):
    """\
    Creates an instance of matplotlib.figure.Figure, given the height in inches.
    Returns the figure and the height in pixels.
    """

    fig = matplotlib.figure.Figure(
        figsize=(_FIGURE_WIDTH_IN, height_inches + _FIGURE_BOTTOM_PADDING_IN),
        dpi=_FIGURE_DPI, facecolor='white')
    fig.subplots_adjust(bottom=float(_FIGURE_BOTTOM_PADDING_IN) / height_inches)
    return (fig, fig.get_figheight() * _FIGURE_DPI)


def _create_line(plots, labels, plot_info):
    """\
    Given all the data for the metrics, create a line plot.

    plots: list of dicts containing the plot data. Each dict contains:
            x: list of x-values for the plot
            y: list of corresponding y-values
            errors: errors for each data point, or None if no error information
                    available
            label: plot title
    labels: list of x-tick labels
    plot_info: a MetricsPlot
    """
    # when we're doing any kind of normalization, all series get put into a
    # single plot
    single = bool(plot_info.normalize_to)

    area_data = []
    lines = []
    if single:
        plot_height = _SINGLE_PLOT_HEIGHT
    else:
        plot_height = _MULTIPLE_PLOT_HEIGHT_PER_PLOT * len(plots)
    figure, height = _create_figure(plot_height)

    if single:
        subplot = figure.add_subplot(1, 1, 1)

    # Plot all the data
    for plot_index, (plot, color) in enumerate(zip(plots, _colors(len(plots)))):
        needs_invert = (plot['label'] in plot_info.inverted_series)

        # Add a new subplot, if user wants multiple subplots
        # Also handle axis inversion for subplots here
        if not single:
            subplot = figure.add_subplot(len(plots), 1, plot_index + 1)
            subplot.set_title(plot['label'])
            if needs_invert:
                # for separate plots, just invert the y-axis
                subplot.set_ylim(1, 0)
        elif needs_invert:
            # for a shared plot (normalized data), need to invert the y values
            # manually, since all plots share a y-axis
            plot['y'] = [-y for y in plot['y']]

        # Plot the series
        subplot.set_xticks(range(0, len(labels)))
        subplot.set_xlim(-1, len(labels))
        if single:
            lines += subplot.plot(plot['x'], plot['y'], label=plot['label'],
                                  marker=_MULTIPLE_PLOT_MARKER_TYPE,
                                  markersize=_MULTIPLE_PLOT_MARKER_SIZE)
            error_bar_color = lines[-1].get_color()
        else:
            lines += subplot.plot(plot['x'], plot['y'], _SINGLE_PLOT_STYLE,
                                  label=plot['label'])
            error_bar_color = _SINGLE_PLOT_ERROR_BAR_COLOR
        if plot['errors']:
            subplot.errorbar(plot['x'], plot['y'], linestyle='None',
                             yerr=plot['errors'], color=error_bar_color)
        subplot.set_xticklabels([])

    # Construct the information for the drilldowns.
    # We need to do this in a separate loop so that all the data is in
    # matplotlib before we start calling transform(); otherwise, it will return
    # incorrect data because it hasn't finished adjusting axis limits.
    for line in lines:

        # Get the pixel coordinates of each point on the figure
        x = line.get_xdata()
        y = line.get_ydata()
        label = line.get_label()
        icoords = line.get_transform().transform(zip(x,y))

        # Get the appropriate drilldown query
        drill = plot_info.query_dict['__' + label + '__']

        # Set the title attributes (hover-over tool-tips)
        x_labels = [labels[x_val] for x_val in x]
        titles = ['%s - %s: %f' % (label, x_label, y_val)
                  for x_label, y_val in zip(x_labels, y)]

        # Get the appropriate parameters for the drilldown query
        params = [dict(query=drill, series=line.get_label(), param=x_label)
                  for x_label in x_labels]

        area_data += [dict(left=ix - 5, top=height - iy - 5,
                           right=ix + 5, bottom=height - iy + 5,
                           title= title,
                           callback=plot_info.drilldown_callback,
                           callback_arguments=param_dict)
                      for (ix, iy), title, param_dict
                      in zip(icoords, titles, params)]

    subplot.set_xticklabels(labels, rotation=90, size=_LINE_XTICK_LABELS_SIZE)

    # Show the legend if there are not multiple subplots
    if single:
        font_properties = matplotlib.font_manager.FontProperties(
            size=_LEGEND_FONT_SIZE)
        legend = figure.legend(lines, [plot['label'] for plot in plots],
                               prop=font_properties,
                               handlelen=_LEGEND_HANDLE_LENGTH,
                               numpoints=_LEGEND_NUM_POINTS)
        # Workaround for matplotlib not keeping all line markers in the legend -
        # it seems if we don't do this, matplotlib won't keep all the line
        # markers in the legend.
        for line in legend.get_lines():
            line.set_marker(_LEGEND_MARKER_TYPE)

    return (figure, area_data)


def _get_adjusted_bar(x, bar_width, series_index, num_plots):
    """\
    Adjust the list 'x' to take the multiple series into account. Each series
    should be shifted such that the middle series lies at the appropriate x-axis
    tick with the other bars around it.  For example, if we had four series
    (i.e. four bars per x value), we want to shift the left edges of the bars as
    such:
    Bar 1: -2 * width
    Bar 2: -width
    Bar 3: none
    Bar 4: width
    """
    adjust = (-0.5 * num_plots - 1 + series_index) * bar_width
    return [x_val + adjust for x_val in x]


# TODO(showard): merge much of this function with _create_line by extracting and
# parameterizing methods
def _create_bar(plots, labels, plot_info):
    """\
    Given all the data for the metrics, create a line plot.

    plots: list of dicts containing the plot data.
            x: list of x-values for the plot
            y: list of corresponding y-values
            errors: errors for each data point, or None if no error information
                    available
            label: plot title
    labels: list of x-tick labels
    plot_info: a MetricsPlot
    """

    area_data = []
    bars = []
    figure, height = _create_figure(_SINGLE_PLOT_HEIGHT)

    # Set up the plot
    subplot = figure.add_subplot(1, 1, 1)
    subplot.set_xticks(range(0, len(labels)))
    subplot.set_xlim(-1, len(labels))
    subplot.set_xticklabels(labels, rotation=90, size=_BAR_XTICK_LABELS_SIZE)
    # draw a bold line at y=0, making it easier to tell if bars are dipping
    # below the axis or not.
    subplot.axhline(linewidth=2, color='black')

    # width here is the width for each bar in the plot. Matplotlib default is
    # 0.8.
    width = 0.8 / len(plots)

    # Plot the data
    for plot_index, (plot, color) in enumerate(zip(plots, _colors(len(plots)))):
        # Invert the y-axis if needed
        if plot['label'] in plot_info.inverted_series:
            plot['y'] = [-y for y in plot['y']]

        adjusted_x = _get_adjusted_bar(plot['x'], width, plot_index + 1,
                                       len(plots))
        bar_data = subplot.bar(adjusted_x, plot['y'],
                               width=width, yerr=plot['errors'],
                               facecolor=color,
                               label=plot['label'])
        bars.append(bar_data[0])

    # Construct the information for the drilldowns.
    # See comment in _create_line for why we need a separate loop to do this.
    for plot_index, plot in enumerate(plots):
        adjusted_x = _get_adjusted_bar(plot['x'], width, plot_index + 1,
                                       len(plots))

        # Let matplotlib plot the data, so that we can get the data-to-image
        # coordinate transforms
        line = subplot.plot(adjusted_x, plot['y'], linestyle='None')[0]
        label = plot['label']
        upper_left_coords = line.get_transform().transform(zip(adjusted_x,
                                                               plot['y']))
        bottom_right_coords = line.get_transform().transform(
            [(x + width, 0) for x in adjusted_x])

        # Get the drilldown query
        drill = plot_info.query_dict['__' + label + '__']

        # Set the title attributes
        x_labels = [labels[x] for x in plot['x']]
        titles = ['%s - %s: %f' % (plot['label'], label, y)
                  for label, y in zip(x_labels, plot['y'])]
        params = [dict(query=drill, series=plot['label'], param=x_label)
                  for x_label in x_labels]
        area_data += [dict(left=ulx, top=height - uly,
                           right=brx, bottom=height - bry,
                           title=title,
                           callback=plot_info.drilldown_callback,
                           callback_arguments=param_dict)
                      for (ulx, uly), (brx, bry), title, param_dict
                      in zip(upper_left_coords, bottom_right_coords, titles,
                             params)]

    figure.legend(bars, [plot['label'] for plot in plots])
    return (figure, area_data)


def _normalize(data_values, data_errors, base_values, base_errors):
    """\
    Normalize the data against a baseline.

    data_values: y-values for the to-be-normalized data
    data_errors: standard deviations for the to-be-normalized data
    base_values: list of values normalize against
    base_errors: list of standard deviations for those base values
    """
    values = []
    for value, base in zip(data_values, base_values):
        try:
            values.append(100 * (value - base) / base)
        except ZeroDivisionError:
            # Base is 0.0 so just simplify:
            #   If value < base: append -100.0;
            #   If value == base: append 0.0 (obvious); and
            #   If value > base: append 100.0.
            values.append(100 * float(cmp(value, base)))

    # Based on error for f(x,y) = 100 * (x - y) / y
    if data_errors:
        if not base_errors:
            base_errors = [0] * len(data_errors)
        errors = []
        for data, error, base_value, base_error in zip(
                data_values, data_errors, base_values, base_errors):
            try:
                errors.append(sqrt(error**2 * (100 / base_value)**2
                        + base_error**2 * (100 * data / base_value**2)**2
                        + error * base_error * (100 / base_value**2)**2))
            except ZeroDivisionError:
                # Again, base is 0.0 so do the simple thing.
                errors.append(100 * abs(error))
    else:
        errors = None

    return (values, errors)


def _create_png(figure):
    """\
    Given the matplotlib figure, generate the PNG data for it.
    """

    # Draw the image
    canvas = matplotlib.backends.backend_agg.FigureCanvasAgg(figure)
    canvas.draw()
    size = canvas.get_renderer().get_canvas_width_height()
    image_as_string = canvas.tostring_rgb()
    image = PIL.Image.fromstring('RGB', size, image_as_string, 'raw', 'RGB', 0,
                                 1)
    image_background = PIL.Image.new(image.mode, image.size,
                                     figure.get_facecolor())

    # Crop the image to remove surrounding whitespace
    non_whitespace = PIL.ImageChops.difference(image, image_background)
    bounding_box = non_whitespace.getbbox()
    image = image.crop(bounding_box)

    image_data = StringIO.StringIO()
    image.save(image_data, format='PNG')

    return image_data.getvalue(), bounding_box


def _create_image_html(figure, area_data, plot_info):
    """\
    Given the figure and drilldown data, construct the HTML that will render the
    graph as a PNG image, and attach the image map to that image.

    figure: figure containing the drawn plot(s)
    area_data: list of parameters for each area of the image map. See the
               definition of the template string '_AREA_TEMPLATE'
    plot_info: a MetricsPlot or QualHistogram
    """

    png, bbox = _create_png(figure)

    # Construct the list of image map areas
    areas = [_AREA_TEMPLATE %
             (data['left'] - bbox[0], data['top'] - bbox[1],
              data['right'] - bbox[0], data['bottom'] - bbox[1],
              data['title'], data['callback'],
              _json_encoder.encode(data['callback_arguments'])
                  .replace('"', '&quot;'))
             for data in area_data]

    map_name = plot_info.drilldown_callback + '_map'
    return _HTML_TEMPLATE % (base64.b64encode(png), map_name, map_name,
                             '\n'.join(areas))


def _find_plot_by_label(plots, label):
    for index, plot in enumerate(plots):
        if plot['label'] == label:
            return index
    raise ValueError('no plot labeled "%s" found' % label)


def _normalize_to_series(plots, base_series):
    base_series_index = _find_plot_by_label(plots, base_series)
    base_plot = plots[base_series_index]
    base_xs = base_plot['x']
    base_values = base_plot['y']
    base_errors = base_plot['errors']
    del plots[base_series_index]

    for plot in plots:
        old_xs, old_values, old_errors = plot['x'], plot['y'], plot['errors']
        new_xs, new_values, new_errors = [], [], []
        new_base_values, new_base_errors = [], []
        # Select only points in the to-be-normalized data that have a
        # corresponding baseline value
        for index, x_value in enumerate(old_xs):
            try:
                base_index = base_xs.index(x_value)
            except ValueError:
                continue

            new_xs.append(x_value)
            new_values.append(old_values[index])
            new_base_values.append(base_values[base_index])
            if old_errors:
                new_errors.append(old_errors[index])
                new_base_errors.append(base_errors[base_index])

        if not new_xs:
            raise NoDataError('No normalizable data for series ' +
                              plot['label'])
        plot['x'] = new_xs
        plot['y'] = new_values
        if old_errors:
            plot['errors'] = new_errors

        plot['y'], plot['errors'] = _normalize(plot['y'], plot['errors'],
                                               new_base_values,
                                               new_base_errors)


def _create_metrics_plot_helper(plot_info, extra_text=None):
    """
    Create a metrics plot of the given plot data.
    plot_info: a MetricsPlot object.
    extra_text: text to show at the uppper-left of the graph

    TODO(showard): move some/all of this logic into methods on MetricsPlot
    """
    query = plot_info.query_dict['__main__']
    cursor = readonly_connection.connection().cursor()
    cursor.execute(query)

    if not cursor.rowcount:
        raise NoDataError('query did not return any data')
    rows = cursor.fetchall()
    # "transpose" rows, so columns[0] is all the values from the first column,
    # etc.
    columns = zip(*rows)

    plots = []
    labels = [str(label) for label in columns[0]]
    needs_resort = (cursor.description[0][0] == 'kernel')

    # Collect all the data for the plot
    col = 1
    while col < len(cursor.description):
        y = columns[col]
        label = cursor.description[col][0]
        col += 1
        if (col < len(cursor.description) and
            'errors-' + label == cursor.description[col][0]):
            errors = columns[col]
            col += 1
        else:
            errors = None
        if needs_resort:
            y = _resort(labels, y)
            if errors:
                errors = _resort(labels, errors)

        x = [index for index, value in enumerate(y) if value is not None]
        if not x:
            raise NoDataError('No data for series ' + label)
        y = [y[i] for i in x]
        if errors:
            errors = [errors[i] for i in x]
        plots.append({
            'label': label,
            'x': x,
            'y': y,
            'errors': errors
        })

    if needs_resort:
        labels = _resort(labels, labels)

    # Normalize the data if necessary
    normalize_to = plot_info.normalize_to
    if normalize_to == 'first' or normalize_to.startswith('x__'):
        if normalize_to != 'first':
            baseline = normalize_to[3:]
            try:
                baseline_index = labels.index(baseline)
            except ValueError:
                raise ValidationError({
                    'Normalize' : 'Invalid baseline %s' % baseline
                    })
        for plot in plots:
            if normalize_to == 'first':
                plot_index = 0
            else:
                try:
                    plot_index = plot['x'].index(baseline_index)
                # if the value is not found, then we cannot normalize
                except ValueError:
                    raise ValidationError({
                        'Normalize' : ('%s does not have a value for %s'
                                       % (plot['label'], normalize_to[3:]))
                        })
            base_values = [plot['y'][plot_index]] * len(plot['y'])
            if plot['errors']:
                base_errors = [plot['errors'][plot_index]] * len(plot['errors'])
            plot['y'], plot['errors'] = _normalize(plot['y'], plot['errors'],
                                                   base_values,
                                                   None or base_errors)

    elif normalize_to.startswith('series__'):
        base_series = normalize_to[8:]
        _normalize_to_series(plots, base_series)

    # Call the appropriate function to draw the line or bar plot
    if plot_info.is_line:
        figure, area_data = _create_line(plots, labels, plot_info)
    else:
        figure, area_data = _create_bar(plots, labels, plot_info)

    # TODO(showard): extract these magic numbers to named constants
    if extra_text:
        text_y = .95 - .0075 * len(plots)
        figure.text(.1, text_y, extra_text, size='xx-small')

    return (figure, area_data)


def create_metrics_plot(query_dict, plot_type, inverted_series, normalize_to,
                        drilldown_callback, extra_text=None):
    plot_info = MetricsPlot(query_dict, plot_type, inverted_series,
                            normalize_to, drilldown_callback)
    figure, area_data = _create_metrics_plot_helper(plot_info, extra_text)
    return _create_image_html(figure, area_data, plot_info)


def _get_hostnames_in_bucket(hist_data, bucket):
    """\
    Get all the hostnames that constitute a particular bucket in the histogram.

    hist_data: list containing tuples of (hostname, pass_rate)
    bucket: tuple containing the (low, high) values of the target bucket
    """

    return [hostname for hostname, pass_rate in hist_data
            if bucket[0] <= pass_rate < bucket[1]]


def _create_qual_histogram_helper(plot_info, extra_text=None):
    """\
    Create a machine qualification histogram of the given data.

    plot_info: a QualificationHistogram
    extra_text: text to show at the upper-left of the graph

    TODO(showard): move much or all of this into methods on
    QualificationHistogram
    """
    cursor = readonly_connection.connection().cursor()
    cursor.execute(plot_info.query)

    if not cursor.rowcount:
        raise NoDataError('query did not return any data')

    # Lists to store the plot data.
    # hist_data store tuples of (hostname, pass_rate) for machines that have
    #     pass rates between 0 and 100%, exclusive.
    # no_tests is a list of machines that have run none of the selected tests
    # no_pass is a list of machines with 0% pass rate
    # perfect is a list of machines with a 100% pass rate
    hist_data = []
    no_tests = []
    no_pass = []
    perfect = []

    # Construct the lists of data to plot
    for hostname, total, good in cursor.fetchall():
        if total == 0:
            no_tests.append(hostname)
            continue

        if good == 0:
            no_pass.append(hostname)
        elif good == total:
            perfect.append(hostname)
        else:
            percentage = 100.0 * good / total
            hist_data.append((hostname, percentage))

    interval = plot_info.interval
    bins = range(0, 100, interval)
    if bins[-1] != 100:
        bins.append(bins[-1] + interval)

    figure, height = _create_figure(_SINGLE_PLOT_HEIGHT)
    subplot = figure.add_subplot(1, 1, 1)

    # Plot the data and get all the bars plotted
    _,_, bars = subplot.hist([data[1] for data in hist_data],
                         bins=bins, align='left')
    bars += subplot.bar([-interval], len(no_pass),
                    width=interval, align='center')
    bars += subplot.bar([bins[-1]], len(perfect),
                    width=interval, align='center')
    bars += subplot.bar([-3 * interval], len(no_tests),
                    width=interval, align='center')

    buckets = [(bin, min(bin + interval, 100)) for bin in bins[:-1]]
    # set the x-axis range to cover all the normal bins plus the three "special"
    # ones - N/A (3 intervals left), 0% (1 interval left) ,and 100% (far right)
    subplot.set_xlim(-4 * interval, bins[-1] + interval)
    subplot.set_xticks([-3 * interval, -interval] + bins + [100 + interval])
    subplot.set_xticklabels(['N/A', '0%'] +
                        ['%d%% - <%d%%' % bucket for bucket in buckets] +
                        ['100%'], rotation=90, size='small')

    # Find the coordinates on the image for each bar
    x = []
    y = []
    for bar in bars:
        x.append(bar.get_x())
        y.append(bar.get_height())
    f = subplot.plot(x, y, linestyle='None')[0]
    upper_left_coords = f.get_transform().transform(zip(x, y))
    bottom_right_coords = f.get_transform().transform(
        [(x_val + interval, 0) for x_val in x])

    # Set the title attributes
    titles = ['%d%% - <%d%%: %d machines' % (bucket[0], bucket[1], y_val)
              for bucket, y_val in zip(buckets, y)]
    titles.append('0%%: %d machines' % len(no_pass))
    titles.append('100%%: %d machines' % len(perfect))
    titles.append('N/A: %d machines' % len(no_tests))

    # Get the hostnames for each bucket in the histogram
    names_list = [_get_hostnames_in_bucket(hist_data, bucket)
                  for bucket in buckets]
    names_list += [no_pass, perfect]

    if plot_info.filter_string:
        plot_info.filter_string += ' AND '

    # Construct the list of drilldown parameters to be passed when the user
    # clicks on the bar.
    params = []
    for names in names_list:
        if names:
            hostnames = ','.join(_quote(hostname) for hostname in names)
            hostname_filter = 'hostname IN (%s)' % hostnames
            full_filter = plot_info.filter_string + hostname_filter
            params.append({'type': 'normal',
                           'filterString': full_filter})
        else:
            params.append({'type': 'empty'})

    params.append({'type': 'not_applicable',
                   'hosts': '<br />'.join(no_tests)})

    area_data = [dict(left=ulx, top=height - uly,
                      right=brx, bottom=height - bry,
                      title=title, callback=plot_info.drilldown_callback,
                      callback_arguments=param_dict)
                 for (ulx, uly), (brx, bry), title, param_dict
                 in zip(upper_left_coords, bottom_right_coords, titles, params)]

    # TODO(showard): extract these magic numbers to named constants
    if extra_text:
        figure.text(.1, .95, extra_text, size='xx-small')

    return (figure, area_data)


def create_qual_histogram(query, filter_string, interval, drilldown_callback,
                          extra_text=None):
    plot_info = QualificationHistogram(query, filter_string, interval,
                                       drilldown_callback)
    figure, area_data = _create_qual_histogram_helper(plot_info, extra_text)
    return _create_image_html(figure, area_data, plot_info)


def create_embedded_plot(model, update_time):
    """\
    Given an EmbeddedGraphingQuery object, generate the PNG image for it.

    model: EmbeddedGraphingQuery object
    update_time: 'Last updated' time
    """

    params = pickle.loads(model.params)
    extra_text = 'Last updated: %s' % update_time

    if model.graph_type == 'metrics':
        plot_info = MetricsPlot(query_dict=params['queries'],
                                plot_type=params['plot'],
                                inverted_series=params['invert'],
                                normalize_to=None,
                                drilldown_callback='')
        figure, areas_unused = _create_metrics_plot_helper(plot_info,
                                                           extra_text)
    elif model.graph_type == 'qual':
        plot_info = QualificationHistogram(
            query=params['query'], filter_string=params['filter_string'],
            interval=params['interval'], drilldown_callback='')
        figure, areas_unused = _create_qual_histogram_helper(plot_info,
                                                             extra_text)
    else:
        raise ValueError('Invalid graph_type %s' % model.graph_type)

    image, bounding_box_unused = _create_png(figure)
    return image


_cache_timeout = global_config.global_config.get_config_value(
    'TKO', 'graph_cache_creation_timeout_minutes')


def handle_plot_request(id, max_age):
    """\
    Given the embedding id of a graph, generate a PNG of the embedded graph
    associated with that id.

    id: id of the embedded graph
    max_age: maximum age, in minutes, that a cached version should be held
    """
    model = models.EmbeddedGraphingQuery.objects.get(id=id)

    # Check if the cached image needs to be updated
    now = datetime.datetime.now()
    update_time = model.last_updated + datetime.timedelta(minutes=int(max_age))
    if now > update_time:
        cursor = django.db.connection.cursor()

        # We want this query to update the refresh_time only once, even if
        # multiple threads are running it at the same time. That is, only the
        # first thread will win the race, and it will be the one to update the
        # cached image; all other threads will show that they updated 0 rows
        query = """
            UPDATE embedded_graphing_queries
            SET refresh_time = NOW()
            WHERE id = %s AND (
                refresh_time IS NULL OR
                refresh_time + INTERVAL %s MINUTE < NOW()
            )
        """
        cursor.execute(query, (id, _cache_timeout))

        # Only refresh the cached image if we were successful in updating the
        # refresh time
        if cursor.rowcount:
            model.cached_png = create_embedded_plot(model, now.ctime())
            model.last_updated = now
            model.refresh_time = None
            model.save()

    return model.cached_png
