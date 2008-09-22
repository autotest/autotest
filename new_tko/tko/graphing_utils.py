import base64, os, tempfile, operator, pickle, datetime, django.db
from math import sqrt

os.environ['HOME'] = tempfile.gettempdir()

import matplotlib
matplotlib.use('Agg')

import matplotlib.figure, matplotlib.backends.backend_agg
import StringIO, colorsys, PIL.Image, PIL.ImageChops
from autotest_lib.frontend.afe import readonly_connection
from autotest_lib.frontend.afe.model_logic import ValidationError
from autotest_lib.client.common_lib import global_config
from new_tko.tko import models, tko_rpc_utils


class NoDataError(Exception):
    """\
    Exception to raise if the graphing query returned an empty resultset.
    """


def _colors(n):
    """\
    Returns a generator function for creating n colors. The return value is a
    tuple representing the RGB of the color.
    """

    incr = 1.0 / n
    hue = 0.0
    for i in xrange(n):
        yield colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        hue += incr


def _resort(kernel_labels, list_to_sort):
    """\
    Resorts a list, using a list of kernel strings as the keys. Returns the
    resorted list.
    """

    labels = [tko_rpc_utils.KernelString(label) for label in kernel_labels]
    resorted_pairs = sorted(zip(labels, list_to_sort))

    # We only want the resorted list; we are not interested in the kernel
    # strings.
    resorted_list = [pair[1] for pair in resorted_pairs]
    return resorted_list


_tmpl = """\
<html><head></head><body>
<img src="data:image/png;base64,%s" usemap="#%s"
  border="0" alt="graph">
<map name="%s">%s</map>
</body></html>"""

_area = """\
<area shape="rect" coords="%i,%i,%i,%i" title="%s"
href="#"
onclick="%s(%s); return false;">"""


def _create_figure(height_inches):
    """\
    Creates an instance of matplotlib.figure.Figure, given the height in inches.
    Returns the figure and the height in pixels.
    """

    dpi = 100;
    fig = matplotlib.figure.Figure(figsize=(10, 2 + height_inches),
                                   dpi=dpi, facecolor='white')
    fig.subplots_adjust(bottom=2.0/height_inches)
    return (fig, fig.get_figheight() * dpi)


def _create_line(plots, labels, queries, invert, single):
    """\
    Given all the data for the metrics, create a line plot.

    plots: dictionary containing the plot data.
            x: list of x-values for the plot
            y: list of corresponding y-values
            errors: errors for each data point, or None if no error information
                    available
            label: plot title
    labels: x-tick labels
    queries: dictionary containing the relevant drilldown queries for series
    invert: list of series that should have an inverted y-axis
    single: True if this should be a single plot, False for multiple subplots
    """

    area_data = []
    lines = []
    if single:
        h = 6
    else:
        h = 4 * len(plots)
    fig, height = _create_figure(h)
    plot_index = 1

    if single:
        sub = fig.add_subplot(1,1,1)

    # Plot all the data
    for plot, color in zip(plots, _colors(len(plots))):
        needs_invert = (plot['label'] in invert)

        # Add a new subplot, if user wants multiple subplots
        # Also handle axis inversion for subplots here
        if not single:
            sub = fig.add_subplot(len(plots), 1, plot_index)
            sub.set_title(plot['label'])
            if needs_invert:
                sub.set_ylim(1,0)
        elif needs_invert:
            plot['y'] = [-y for y in plot['y']]

        # Plot the series
        sub.set_xticks(range(0, len(labels)))
        sub.set_xlim(-1, len(labels))
        if single:
            lines += sub.plot(plot['x'], plot['y'], label=plot['label'],
                              marker='o', markersize=4)
            color = lines[-1].get_color()
        else:
            lines += sub.plot(plot['x'], plot['y'], 'bs-', label=plot['label'])
            color = 'r'
        if plot['errors']:
            sub.errorbar(plot['x'], plot['y'], linestyle='None',
                         yerr=plot['errors'], color=color)
        sub.set_xticklabels([])

        plot_index += 1

    # Construct the information for the drilldowns
    for line in lines:

        # Get the pixel coordinates of each point on the figure
        x = line.get_xdata()
        y = line.get_ydata()
        label = line.get_label()
        icoords = line.get_transform().transform(zip(x,y))

        # Get the appropriate drilldown query
        drill = "'%s'" % (queries['__' + label + '__'].replace("'", "\\'"))

        # Set the title attributes (hover-over tool-tips)
        x_labels = [labels[x_val] for x_val in x]
        titles = ['%s - %s: %f' % (label, x_label, y_val)
                  for x_label, y_val in zip(x_labels, y)]

        # Get the appropriate parameters for the drilldown query
        params = [[drill, "'%s'" % (line.get_label()), "'%s'" % x_label]
                  for x_label in x_labels]

        area_data += [(ix - 5, height - iy - 5, ix + 5, height - iy + 5,
                       title, 'showMetricsDrilldown', ','.join(param))
                      for (ix, iy), title, param
                      in zip(icoords, titles, params)]

    sub.set_xticklabels(labels, rotation=90, size='x-small')

    # Show the legend if there are not multiple subplots
    if single:
        prop = matplotlib.font_manager.FontProperties(size='xx-small')
        legend = fig.legend(lines, [plot['label'] for plot in plots],
                            prop=prop, handlelen=0.03, numpoints=3)
        # workaround for matplotlib not keeping all line markers in the legend
        lines = legend.get_lines()
        for line in lines:
            line.set_marker('o')

    return (fig, area_data)


def _get_adjusted_bar(x, width, index, num_plots):
    """\
    Adjust the list 'x' to take the multiple series into account. Each series
    should be shifted to the right by the width of a bar.
    """
    adjust = width * (index - 0.5 * num_plots - 1)
    return [x_val + adjust for x_val in x]


def _create_bar(plots, labels, queries, invert):
    """\
    Given all the data for the metrics, create a line plot.

    plots: dictionary containing the plot data.
            x: list of x-values for the plot
            y: list of corresponding y-values
            errors: errors for each data point, or None if no error information
                    available
            label: plot title
    labels: x-tick labels
    queries: dictionary containing the relevant drilldown queries for series
    invert: list of series that should have an inverted y-axis
    """

    area_data = []
    bars = []
    fig, height = _create_figure(6)

    # Set up the plot
    sub = fig.add_subplot(1,1,1)
    sub.set_xticks(range(0, len(labels)))
    sub.set_xlim(-1, len(labels))
    sub.set_xticklabels(labels, rotation=90, size=8)
    sub.axhline(linewidth=2, color='black')

    # width here is the width for each bar in the plot. Matplotlib default is
    # 0.8.
    width = 0.8 / len(plots)
    plot_index = 1

    # Plot the data
    for plot, color in zip(plots, _colors(len(plots))):
        # Invert the y-axis if needed
        if plot['label'] in invert:
            plot['y'] = [-y for y in plot['y']]

        adjusted_x = _get_adjusted_bar(plot['x'], width, plot_index, len(plots))
        bars.append(sub.bar(adjusted_x, plot['y'],
                            width=width, yerr=plot['errors'], facecolor=color,
                            label=plot['label'])[0])
        plot_index += 1

    # Construct the information for the drilldowns
    plot_index = 1
    for plot in plots:
        adjusted_x = _get_adjusted_bar(plot['x'], width, plot_index, len(plots))

        # Let matplotlib plot the data, so that we can get the data-to-image
        # coordinate transforms
        line = sub.plot(adjusted_x, plot['y'], linestyle='None')[0]
        ulcoords = line.get_transform().transform(zip(adjusted_x, plot['y']))
        brcoords = line.get_transform().transform(
            [(x + width, 0) for x in adjusted_x])

        # Get the drilldown query
        key = '__' + plot['label'] + '__'
        drill = "'%s'" % (queries[key].replace("'", "\\'"))

        # Set the title attributes
        x_labels = [labels[x] for x in plot['x']]
        titles = ['%s - %s: %f' % (plot['label'], label, y)
                  for label, y in zip(x_labels, plot['y'])]
        params = [[drill, "'%s'" % plot['label'], "'%s'" % x_label]
                  for x_label in x_labels]
        area_data += [(ulx, height - uly, brx, height - bry,
                       title, 'showMetricsDrilldown', ','.join(param))
                      for (ulx, uly), (brx, bry), title, param
                      in zip(ulcoords, brcoords, titles, params)]
        plot_index += 1

    fig.legend(bars, [plot['label'] for plot in plots])
    return (fig, area_data)


def _normalize(data_values, data_errors, base_values, base_errors):
    """\
    Normalize the data against a baseline.

    data_values: y-values for the to-be-normalized data
    data_errors: standard deviations for the to-be-normalized data
    base_values: list of values normalize against
    base_errors: list of standard deviations for those base values
    """

    values = [100 * (value - base) / base
              for value, base in zip(data_values, base_values)]

    # Based on error for f(x,y) = 100 * (x - y) / y
    if data_errors:
        if not base_errors:
            base_errors = [0] * len(data_errors)
        errors = [sqrt(error**2 * (100 / base_value)**2
                       + base_error**2 * (100 * data / base_value**2)**2
                       + error * base_error * (100 / base_value**2)**2)
                  for data, error, base_value, base_error
                  in zip(data_values, data_errors, base_values, base_errors)]
    else:
        errors = None

    return (values, errors)


def _create_png(fig):
    """\
    Given the matplotlib figure, generate the PNG data for it.
    """

    # Draw the image
    canvas = matplotlib.backends.backend_agg.FigureCanvasAgg(fig)
    canvas.draw()
    size = canvas.get_renderer().get_canvas_width_height()
    buf = canvas.tostring_rgb()
    im = PIL.Image.fromstring('RGB', size, buf, 'raw', 'RGB', 0, 1)
    bg = PIL.Image.new(im.mode, im.size, fig.get_facecolor())

    # Crop the image to remove surrounding whitespace
    diff = PIL.ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    im = im.crop(bbox)

    imdata = StringIO.StringIO()
    im.save(imdata, format='PNG')

    return imdata.getvalue(), bbox


def _create_image_html(fig, area_data, name):
    """\
    Given the figure and drilldown data, construct the HTML that will render the
    graph as a PNG image, and attach the image map to that image.

    fig: figure containing the drawn plot(s)
    area_data: list of parameters for each area of the image map. See the
               definition of the template string '_area'
    name: name to give the image map in the HTML
    """

    png, bbox = _create_png(fig)

    # Construct the list of image map areas
    areas = [_area % (data[0] - bbox[0], data[1] - bbox[1],
                      data[2] - bbox[0], data[3] - bbox[1],
                      data[4], data[5], data[6])
             for data in area_data]

    return _tmpl % (base64.b64encode(png), name,
                    name, '\n'.join(areas))


def _create_metrics_plot_helper(queries, plot, invert, normalize=None,
                                extra_text=None):
    """\
    Create a metrics plot of the given data.

    queries: dictionary containing the main query and the drilldown queries
    plot: 'Line' or 'Bar', depending on the plot type the user wants
    invert: list of series that should be plotted on an inverted y-axis
    normalize: None - do not normalize
               'first' - normalize against the first data point
               'x__%s' - normalize against the x-axis value %s
               'series__%s' - normalize against the series %s
    extra_text: text to show at the uppper-left of the graph
    """

    if normalize is None:
        normalize = ''
    query = queries['__main__']
    cursor = readonly_connection.connection.cursor()
    cursor.execute(query)

    if not cursor.rowcount:
        raise NoDataError('query did not return any data')
    rows = cursor.fetchall()
    # "transpose" rows, so columns[0] is all the values from the first column,
    # etc.
    columns = zip(*rows)

    if plot == 'Line':
        line = True
    elif plot == 'Bar':
        line = False
    else:
        raise ValidationError({
            'Plot' : 'Plot must be either Line or Bar'
        })
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

        x = [enum[0] for enum in enumerate(y) if enum[1] is not None]
        y = [y[i] for i in x]
        if errors:
            errors = [error for error in errors if error is not None]
        plots.append({
            'label': label,
            'x': x,
            'y': y,
            'errors': errors
        })

    if needs_resort:
        labels = _resort(labels, labels)

    # Normalize the data if necessary
    if normalize == 'first' or normalize.startswith('x__'):
        if normalize != 'first':
            baseline = normalize[3:]
            try:
                baseline_index = labels.index(baseline)
            except ValueError:
                raise ValidationError({
                    'Normalize' : 'Invalid baseline %s' % baseline
                    })
        for plot in plots:
            if normalize == 'first':
                plot_index = 0
            else:
                try:
                    plot_index = plot['x'].index(baseline_index)
                # if the value is not found, then we cannot normalize
                except ValueError:
                    raise ValidationError({
                        'Normalize' : ('%s does not have a value for %s'
                                       % (plot['label'], normalize[3:]))
                        })
            base_values = [plot['y'][plot_index]] * len(plot['y'])
            if plot['errors']:
                base_errors = [plot['errors'][plot_index]] * len(plot['errors'])
            plot['y'], plot['errors'] = _normalize(plot['y'], plot['errors'],
                                                   base_values,
                                                   None or base_errors)

    elif normalize.startswith('series__'):
        series = normalize[8:]
        series_index = [plot['label'] for plot in plots].index(series)
        plot = plots[series_index]
        base_x = plot['x']
        base_values = plot['y']
        base_errors = plot['errors']
        del plots[series_index]
        for plot in plots:
            # Remove all points in the to-be-normalized data that do not
            # have a corresponding baseline value
            to_remove = []
            for index, data in enumerate(plot['x']):
                if not data in base_x:
                    to_remove.append(index)
            to_remove.reverse()
            for index in to_remove:
                del plot['x'][index]
                del plot['y'][index]
                if plot['errors']:
                    del plot['errors'][index]

            plot['y'], plot['errors'] = _normalize(plot['y'], plot['errors'],
                                                   base_values, base_errors)

    # Call the appropriate function to draw the line or bar plot
    params = [plots, labels, queries, invert]
    if line:
        func = _create_line
        params.append(normalize)
    else:
        func = _create_bar
    fig, area_data = func(*params)

    if extra_text:
        text_y = .95 - .0075 * len(plots)
        fig.text(.1, text_y, extra_text, size='xx-small')

    return (fig, area_data, 'metrics_drilldown')

def create_metrics_plot(queries, plot, invert, normalize, extra_text=None):
    """\
    Wrapper for _create_metrics_plot_helper
    """

    fig, area_data, name = _create_metrics_plot_helper(queries, plot,
                                                       invert, normalize,
                                                       extra_text)
    return _create_image_html(fig, area_data, name)


def _get_hostnames_in_bucket(hist_data, bucket):
    """\
    Get all the hostnames that constitute a particular bucket in the histogram.

    hist_data: list containing tuples of (hostname, pass_rate)
    bucket: tuple containing the (low, high) values of the target bucket
    """

    return [data[0] for data in hist_data
            if data[1] >= bucket[0] and data[1] < bucket[1]]


def _create_qual_histogram_helper(query, filter_string, interval, extra_text=None):
    """\
    Create a machine qualification histogram of the given data.

    query: the main query to retrieve the pass rate information
    filter_string: filter to apply to the common global filter to show the Table
                   View drilldown of a histogram bucket
    interval: interval for each bucket. E.g., 10 means that buckets should be
              0-10%, 10%-20%, ...
    extra_text: text to show at the upper-left of the graph
    """
    cursor = readonly_connection.connection.cursor()
    cursor.execute(query)

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
        if total != 0:
            if good == 0:
                no_pass.append(hostname)
            elif good == total:
                perfect.append(hostname)
            else:
                percentage = 100.0 * good / total
                hist_data.append((hostname, percentage))
        else:
            no_tests.append(hostname)

    bins = range(0, 100, interval)
    if bins[-1] != 100:
        bins.append(bins[-1] + interval)

    fig, height = _create_figure(6)
    sub = fig.add_subplot(1,1,1)

    # Plot the data and get all the bars plotted
    _,_, bars = sub.hist([data[1] for data in hist_data],
                         bins=bins, align='left')
    bars += sub.bar([-interval], len(no_pass),
                    width=interval, align='center')
    bars += sub.bar([bins[-1]], len(perfect),
                    width=interval, align='center')
    bars += sub.bar([-3 * interval], len(no_tests),
                    width=interval, align='center')

    buckets = [(bin, min(bin + interval, 100)) for bin in bins[:-1]]
    sub.set_xlim(-4 * interval, bins[-1] + interval)
    sub.set_xticks([-3 * interval, -interval] + bins + [100 + interval])
    sub.set_xticklabels(['N/A', '0%'] +
                        ['%d%% - <%d%%' % bucket for bucket in buckets] +
                        ['100%'], rotation=90, size='small')

    # Find the coordinates on the image for each bar
    x = []
    y = []
    for bar in bars:
        x.append(bar.get_x())
        y.append(bar.get_height())
    f = sub.plot(x, y, linestyle='None')[0]
    ulcoords = f.get_transform().transform(zip(x, y))
    brcoords = f.get_transform().transform(
        [(x_val + interval, 0) for x_val in x])

    filter_string_base = filter_string.replace("'", "\\'").replace('%', '%%')

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
    if filter_string_base:
        filter_string_base += ' AND '

    # Construct the list of JavaScript functions to be called when the user
    # clicks on the bar.
    funcs = []
    params = []
    for names in names_list:
        if names:
            s_string = ','.join(["\\'%s\\'"] * len(names))
            filter_tmpl = '%shostname IN (%s)' % (filter_string_base, s_string)
            filter_string = filter_tmpl % tuple(names)
            funcs.append('showQualDrilldown')
            params.append("'%s'" % filter_string)
        else:
            funcs.append('showQualEmptyDialog')
            params.append([])
    funcs.append('showQualNADialog')
    params.append("<html>%s</html>" % ('<br />'.join(no_tests)))

    area_data = [(ulx, height - uly, brx, height - bry,
                  title, func, param)
                 for (ulx, uly), (brx, bry), title, func, param
                 in zip(ulcoords, brcoords, titles, funcs, params)]

    if extra_text:
        fig.text(.1, .95, extra_text, size='xx-small')

    return (fig, area_data, 'qual_drilldown')


def create_qual_histogram(query, filter_string, interval, extra_text=None):
    """\
    Wrapper for _create_qual_histogram_helper
    """

    fig, area_data, name = _create_qual_histogram_helper(query, filter_string,
                                                         interval, extra_text)
    return _create_image_html(fig, area_data, name)


def create_embedded_plot(model, update_time):
    """\
    Given an EmbeddedGraphingQuery object, generate the PNG image for it.

    model: EmbeddedGraphingQuery object
    update_time: 'Last updated' time
    """

    if model.graph_type == 'metrics':
        func = _create_metrics_plot_helper
    elif model.graph_type == 'qual':
        func = _create_qual_histogram_helper

    params = pickle.loads(model.params)
    params['extra_text'] = 'Last updated: %s' % update_time
    fig, _, _ = func(**params)
    img, _ = _create_png(fig)

    return img


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
