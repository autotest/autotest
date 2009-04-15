package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;
import autotest.tko.SeriesSelector.Series;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RadioButton;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class MetricsPlotFrontend extends DynamicGraphingFrontend implements ClickListener {
    
    public static final String NORMALIZE_SINGLE = "single";
    public static final String NORMALIZE_FIRST = "first";
    public static final String NORMALIZE_SERIES_PREFIX = "series__";
    public static final String NORMALIZE_X_PREFIX = "x__";
    
    protected FilterSelector globalFilter = new FilterSelector(DBColumnSelector.PERF_VIEW);
    private ExtendedListBox plotSelector = new ExtendedListBox();
    private ExtendedListBox xAxis = new DBColumnSelector(DBColumnSelector.PERF_VIEW, true);
    private RadioButton noNormalizeMultiple =
        new RadioButton("normalize", "No normalization (multiple subplots)");
    private RadioButton noNormalizeSingle =
        new RadioButton("normalize", "No normalization (single plot)");
    private RadioButton normalizeFirst = new RadioButton("normalize", "First data point");
    private RadioButton normalizeSeries = new RadioButton("normalize", "Specified series:");
    private ExtendedListBox normalizeSeriesSelect = new ExtendedListBox();
    private RadioButton normalizeX = new RadioButton("normalize", "Specified X-axis value:");
    private TextBox normalizeXSelect = new TextBox();
    private SeriesSelector seriesSelector = new SeriesSelector(new ChangeListener() {
        public void onChange(Widget w) {
            refreshSeries();
        }
    });
    
    public MetricsPlotFrontend(final TabView parent) {
        super(parent, new MetricsPlot(), "metrics");

        noNormalizeSingle.setChecked(true);

        noNormalizeMultiple.addClickListener(this);
        noNormalizeSingle.addClickListener(this);
        normalizeFirst.addClickListener(this);
        normalizeSeries.addClickListener(this);
        normalizeX.addClickListener(this);

        normalizeSeriesSelect.setEnabled(false);
        normalizeXSelect.setEnabled(false);

        plotSelector.addItem("Line");
        plotSelector.addItem("Bar");
        plotSelector.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                checkNormalizeInput();
            }
        });

        Panel normalizePanel = new VerticalPanel();
        normalizePanel.add(noNormalizeMultiple);
        normalizePanel.add(noNormalizeSingle);
        Panel seriesPanel = new HorizontalPanel();
        seriesPanel.add(normalizeSeries);
        seriesPanel.add(normalizeSeriesSelect);
        normalizePanel.add(seriesPanel);
        normalizePanel.add(normalizeFirst);
        Panel baselinePanel = new HorizontalPanel();
        baselinePanel.add(normalizeX);
        baselinePanel.add(normalizeXSelect);
        normalizePanel.add(baselinePanel);
        
        addControl("Preconfigured:", preconfig);
        addControl("Plot:", plotSelector);
        addControl("X-axis values:", xAxis);
        addControl("Global filters:", globalFilter);
        addControl("Series:", seriesSelector);
        addControl("Normalize to:", normalizePanel);
        
        commonInitialization();
    }

    @Override
    public void onClick(Widget sender) {
        if (sender != noNormalizeSingle && sender != noNormalizeMultiple 
                && sender != normalizeSeries && sender != normalizeX) {
            super.onClick(sender);
            return;
        }

        normalizeSeriesSelect.setEnabled(false);
        normalizeXSelect.setEnabled(false);
        if (sender == normalizeSeries) {
            normalizeSeriesSelect.setEnabled(true);
            refreshSeries();
        } else if (sender == normalizeX) {
            normalizeXSelect.setEnabled(true);
        }

        checkInvertible();
    }
    
    private void addNormalizeParameter(String plotType, Map<String, String> parameters) {
        String normalizationType = null;
        if (plotType.equals("Line") && noNormalizeSingle.isChecked()) {
            normalizationType = NORMALIZE_SINGLE;
        } else if (normalizeFirst.isChecked()) {
            normalizationType = NORMALIZE_FIRST;
        } else if (normalizeSeries.isChecked()) {
            String series = normalizeSeriesSelect.getSelectedValue();
            normalizationType = NORMALIZE_SERIES_PREFIX + series;
        } else if (normalizeX.isChecked()) {
            String baseline = normalizeXSelect.getText();
            normalizationType = NORMALIZE_X_PREFIX + baseline;
        }
        
        if (normalizationType != null) {
            parameters.put("normalize", normalizationType);
        }
    }

    @Override
    public void addToHistory(Map<String, String> args) {
        String plot = plotSelector.getValue(plotSelector.getSelectedIndex());
        args.put("plot", plot);
        args.put("xAxis", xAxis.getSelectedValue());
        globalFilter.addToHistory(args, "globalFilter");
        seriesSelector.addToHistory(args);
        addNormalizeParameter(plot, args);
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> args) {
        setVisible(false);
        plot.setVisible(false);
        embeddingLink.setVisible(false);
        globalFilter.reset();
        seriesSelector.reset();
        for (int i = 0; i < plotSelector.getItemCount(); i++) {
            if (plotSelector.getValue(i).equals(args.get("plot"))) {
                plotSelector.setSelectedIndex(i);
                break;
            }
        }
        
        xAxis.selectByValue(args.get("xAxis"));
        globalFilter.handleHistoryArguments(args, "globalFilter");
        seriesSelector.handleHistoryArguments(args);
        
        refreshSeries();
        noNormalizeMultiple.setChecked(true);
        normalizeSeriesSelect.setEnabled(false);
        normalizeXSelect.setEnabled(false);
        String normalizeString = args.get("normalize");
        if (normalizeString != null) {
            if (normalizeString.equals(NORMALIZE_SINGLE)) {
                noNormalizeSingle.setChecked(true);
            } else if (normalizeString.equals(NORMALIZE_FIRST)) {
                normalizeFirst.setChecked(true);
            } else if (normalizeString.startsWith(NORMALIZE_SERIES_PREFIX)) {
                normalizeSeries.setChecked(true);
                String series = normalizeString.substring(NORMALIZE_SERIES_PREFIX.length());
                for (int i = 0; i < normalizeSeriesSelect.getItemCount(); i++) {
                    if (normalizeSeriesSelect.getValue(i).equals(series)) {
                        normalizeSeriesSelect.setSelectedIndex(i);
                        break;
                    }
                }
                normalizeSeriesSelect.setEnabled(true);
            } else if (normalizeString.startsWith(NORMALIZE_X_PREFIX)) {
                normalizeX.setChecked(true);
                normalizeXSelect.setText(normalizeString.substring(NORMALIZE_X_PREFIX.length()));
                normalizeXSelect.setEnabled(true);
            }
        }
        checkNormalizeInput();
        checkInvertible();

        setVisible(true);
    }
    
    @Override
    protected void addAdditionalEmbeddingParams(JSONObject params) {
        params.put("graph_type", new JSONString("metrics"));
        params.put("params", buildParams());
    }
    
    private void refreshSeries() {
        String selectedValue = normalizeSeriesSelect.getSelectedValue();
        normalizeSeriesSelect.clear();
        for (Series selector : seriesSelector.getAllSeries()) {
            normalizeSeriesSelect.addItem(selector.getName());
            if (selector.getName().equals(selectedValue)) {
                normalizeSeriesSelect.setSelectedIndex(normalizeSeriesSelect.getItemCount() - 1);
            }
        }
    }

    // Disable "No Normalization (multiple)" for bar charts
    private void checkNormalizeInput() {
        if (plotSelector.getValue(plotSelector.getSelectedIndex()).equals("Line")) {
            noNormalizeMultiple.setEnabled(true);
        } else {
            noNormalizeMultiple.setEnabled(false);
            if (noNormalizeMultiple.isChecked()) {
                noNormalizeSingle.setChecked(true);
            }
        }
    }
    
    private JSONObject buildQueries() {
        List<Series> seriesList = seriesSelector.getAllSeries();
        JSONObject queries = new JSONObject();
        StringBuilder sql = new StringBuilder();
        
        sql.append("SELECT ");
        sql.append(xAxis.getSelectedValue());
        for (Series series : seriesList) {
            addSeriesSelects(series, sql);
        }
        
        sql.append(" FROM perf_view_2");
            
        String xFilterString = globalFilter.getFilterString();
        if (xFilterString.equals("")) {
            NotifyManager.getInstance().showError("You must enter a global filter");
            return null;
        }
        
        sql.append(" WHERE ");
        sql.append(xFilterString);

        sql.append(" GROUP BY ");
        sql.append(xAxis.getSelectedValue());
        queries.put("__main__", new JSONString(sql.toString()));
        
        for (Series series : seriesList) {
            String drilldownQuery = getSeriesDrilldownQuery(series, xFilterString);
            queries.put("__" + series.getName() + "__", new JSONString(drilldownQuery));
        }
        
        return queries;
    }

    private String getSeriesDrilldownQuery(Series series, String xFilterString) {
        StringBuilder sql;
        sql = new StringBuilder();
        ExtendedListBox valueSelector = series.getDBColumnSelector();
        
        sql.append("SELECT test_idx, ");
        sql.append(valueSelector.getSelectedValue());
        sql.append(" FROM perf_view_2 WHERE ");
        
        String seriesFilter = series.getFilterString();
        if (!xFilterString.equals("") || !seriesFilter.equals("")) {
            sql.append(xFilterString.replace("%", "%%"));
            if (!xFilterString.equals("") && !seriesFilter.equals("")) {
                sql.append(" AND ");
            }
            sql.append(seriesFilter.replace("%", "%%"));
            sql.append(" AND ");
        }
        
        sql.append(xAxis.getSelectedValue());
        sql.append(" = %s ORDER BY ");
        sql.append(valueSelector.getSelectedValue());
        return sql.toString();
    }

    private void addSeriesSelects(Series series, StringBuilder sql) {
        ExtendedListBox valueSelector = series.getDBColumnSelector();
        
        StringBuilder ifClause = new StringBuilder();
        String seriesFilter = series.getFilterString();
        if (!seriesFilter.equals("")) {
            ifClause.append("IF(");
            ifClause.append(seriesFilter);
            ifClause.append(", ");
        }
        ifClause.append(valueSelector.getSelectedValue());
        if (!seriesFilter.equals("")) {
            ifClause.append(", NULL)");   
        }
        
        sql.append(", ");
        sql.append(series.getAggregation());
        sql.append(ifClause);
        sql.append(") '");
        sql.append(series.getName());
        sql.append("'");
        if (series.wantErrorBars()) {
            sql.append(", STDDEV(");
            sql.append(ifClause);
            sql.append(") 'errors-");
            sql.append(series.getName());
            sql.append("'");
        }
    }
    
    // Disable the "Invert y-axis" checkboxes if inversion doesn't make sense
    private void checkInvertible() {
        boolean invertible = noNormalizeMultiple.isChecked() || normalizeFirst.isChecked()
                             || normalizeX.isChecked();
        seriesSelector.setInvertible(invertible);
    }
    
    @Override
    protected JSONObject buildParams() {
        JSONObject queries = buildQueries();
        if (queries == null) {
            return null;
        }
        
        Map<String, String> params = new HashMap<String, String>();
        String plot = plotSelector.getSelectedValue();
        params.put("plot", plot);
        addNormalizeParameter(plot, params);

        JSONObject jsonParams = Utils.mapToJsonObject(params);
        jsonParams.put("invert", Utils.stringsToJSON(seriesSelector.getInverted()));
        jsonParams.put("queries", queries);
        return jsonParams;
    }

    @Override
    public String getFrontendId() {
        return "metrics_plot";
    }
}
