package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.TabView;
import autotest.tko.SeriesSelector.Series;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RadioButton;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Map;

public class MetricsPlotFrontend extends GraphingFrontend {
    
    public static final String NORMALIZE_SINGLE = "single";
    public static final String NORMALIZE_FIRST = "first";
    public static final String NORMALIZE_SERIES_PREFIX = "series__";
    public static final String NORMALIZE_X_PREFIX = "x__";
    
    private PreconfigSelector preconfig = new PreconfigSelector("metrics", this);
    private ListBox plotSelector = new ListBox();
    private DBColumnSelector xAxis = new DBColumnSelector(DBColumnSelector.PERF_VIEW, true);
    private FilterSelector globalFilter =
        new FilterSelector(DBColumnSelector.PERF_VIEW);
    private RadioButton noNormalizeMultiple =
        new RadioButton("normalize", "No normalization (multiple subplots)");
    private RadioButton noNormalizeSingle =
        new RadioButton("normalize", "No normalization (single plot)");
    private RadioButton normalizeFirst = new RadioButton("normalize", "First data point");
    private RadioButton normalizeSeries = new RadioButton("normalize", "Specified series:");
    private ListBox normalizeSeriesSelect = new ListBox();
    private RadioButton normalizeX = new RadioButton("normalize", "Specified X-axis value:");
    private TextBox normalizeXSelect = new TextBox();
    private Button graphButton = new Button("Graph");
    private HTML graph = new HTML();
    
    private SeriesSelector seriesSelector = new SeriesSelector(new ChangeListener() {
        public void onChange(Widget w) {
            refreshSeries();
        }
    });
    
    public MetricsPlotFrontend(final TabView parent) {
        noNormalizeSingle.setChecked(true);
        noNormalizeMultiple.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                normalizeSeriesSelect.setEnabled(false);
                normalizeXSelect.setEnabled(false);
                checkInvertible();
            }
        });
        noNormalizeSingle.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                normalizeSeriesSelect.setEnabled(false);
                normalizeXSelect.setEnabled(false);
                checkInvertible();
            }
        });
        normalizeFirst.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                normalizeSeriesSelect.setEnabled(false);
                normalizeXSelect.setEnabled(false);
                checkInvertible();
            }
        });
        normalizeSeries.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                normalizeSeriesSelect.setEnabled(true);
                normalizeXSelect.setEnabled(false);
                checkInvertible();
                refreshSeries();
            }
        });
        normalizeSeriesSelect.setEnabled(false);
        normalizeX.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                normalizeSeriesSelect.setEnabled(false);
                normalizeXSelect.setEnabled(true);
                checkInvertible();
            }
        });
        normalizeXSelect.setEnabled(false);
        
        plotSelector.addItem("Line");
        plotSelector.addItem("Bar");
        plotSelector.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                checkNormalizeInput();
            }
        });
        
        graphButton.addClickListener(new ClickListener() {
            public void onClick(Widget w) {
                parent.updateHistory();
                graph.setVisible(false);
                embeddingLink.setVisible(false);
                
                JSONObject params = buildParams();
                if (params == null) {
                    return;
                }
                
                rpcProxy.rpcCall("create_metrics_plot", params, new JsonRpcCallback() {
                    @Override
                    public void onSuccess(JSONValue result) {
                        graph.setHTML(Utils.jsonToString(result));
                        graph.setVisible(true);
                        embeddingLink.setVisible(true);
                    }
                });
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
        
        table.setWidget(table.getRowCount(), 1, graphButton);
        table.setWidget(table.getRowCount(), 0, graph);
        table.getFlexCellFormatter().setColSpan(table.getRowCount() - 1, 0, 3);
        
        table.setWidget(table.getRowCount(), 2, embeddingLink);
        table.getFlexCellFormatter().setHorizontalAlignment(
                table.getRowCount() - 1, 2, HasHorizontalAlignment.ALIGN_RIGHT);
        
        graph.setVisible(false);
        embeddingLink.setVisible(false);
        
        initWidget(table);
    }
    
    @Override
    public void refresh() {
        // Nothing to refresh
    }
    
    @Override
    protected void addToHistory(Map<String, String> args) {
        String plot = plotSelector.getValue(plotSelector.getSelectedIndex());
        args.put("plot", plot);
        args.put("xAxis", xAxis.getColumn());
        globalFilter.addToHistory(args, "globalFilter");
        seriesSelector.addToHistory(args);
        if (plot.equals("Line") && noNormalizeSingle.isChecked()) {
            args.put("normalize", "single");
        } else if (normalizeFirst.isChecked()) {
            args.put("normalize", "first");
        } else if (normalizeSeries.isChecked()) {
            String series = 
                normalizeSeriesSelect.getValue(normalizeSeriesSelect.getSelectedIndex());
            args.put("normalize", "series__" + series);
        } else if (normalizeX.isChecked()) {
            String baseline = normalizeXSelect.getText();
            args.put("normalize", "x__" + baseline);
        }
    }
    
    @Override
    protected void handleHistoryArguments(Map<String, String> args) {
        setVisible(false);
        graph.setVisible(false);
        embeddingLink.setVisible(false);
        globalFilter.reset();
        seriesSelector.reset();
        for (int i = 0; i < plotSelector.getItemCount(); i++) {
            if (plotSelector.getValue(i).equals(args.get("plot"))) {
                plotSelector.setSelectedIndex(i);
                break;
            }
        }
        
        xAxis.selectColumn(args.get("xAxis"));
        globalFilter.handleHistoryArguments(args, "globalFilter");
        seriesSelector.handleHistoryArguments(args);
        
        refreshSeries();
        noNormalizeMultiple.setChecked(true);
        normalizeSeriesSelect.setEnabled(false);
        normalizeXSelect.setEnabled(false);
        String normalizeString = args.get("normalize");
        if (normalizeString != null) {
            if (normalizeString.equals("single")) {
                noNormalizeSingle.setChecked(true);
            } else if (normalizeString.equals("first")) {
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
        int selectedIndex = normalizeSeriesSelect.getSelectedIndex();
        String selectedValue = null;
        if (selectedIndex != -1) {
            selectedValue = normalizeSeriesSelect.getValue(selectedIndex);
        }
        normalizeSeriesSelect.clear();
        for (Series selector : seriesSelector.getAllSeries()) {
            normalizeSeriesSelect.addItem(selector.getName());
            if (selector.getName().equals(selectedValue)) {
                normalizeSeriesSelect.setSelectedIndex(normalizeSeriesSelect.getItemCount() - 1);
            }
        }
    }
    
    @Override
    protected native void setDrilldownTrigger() /*-{
        var instance = this;
        $wnd.showMetricsDrilldown = function(query, series, param) {
            instance.@autotest.tko.MetricsPlotFrontend::showDrilldown(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)(query, series, param);
        }
    }-*/;
    
    @SuppressWarnings("unused")
    private void showDrilldown(String query, final String series, final String param) {
        JSONObject params = new JSONObject();
        params.put("query", new JSONString(query));
        params.put("param", new JSONString(param));
        rpcProxy.rpcCall("execute_query_with_param", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONArray data = result.isArray();
                
                String title = series + " for " + param;
                FlexTable contents = new FlexTable();
                final GraphingDialog drill = new GraphingDialog(title, contents);
                
                for (int i = 0; i < data.size(); i++) {
                    final JSONArray row = data.get(i).isArray();
                    SimpleHyperlink link = new SimpleHyperlink(Utils.jsonToString(row.get(1)));
                    link.addClickListener(new ClickListener() {
                        public void onClick(Widget sender) {
                            drill.hide();
                            listener.onSelectTest((int) row.get(0).isNumber().doubleValue());
                        }
                    });
                    contents.setWidget(i, 0, link);
                }
                
                drill.center();
            }
        });
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
        ArrayList<Series> seriesList = seriesSelector.getAllSeries();
        JSONObject queries = new JSONObject();
        StringBuilder sql = new StringBuilder();
        
        sql.append("SELECT ");
        sql.append(xAxis.getColumn());
        for (Series series : seriesList) {
            DBColumnSelector valueSelector = series.getDBColumnSelector();
            
            StringBuilder ifClause = new StringBuilder();
            String seriesFilter = series.getFilterString();
            if (!seriesFilter.equals("")) {
                ifClause.append("IF(");
                ifClause.append(seriesFilter);
                ifClause.append(", ");
            }
            ifClause.append(valueSelector.getColumn());
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
        
        sql.append(" FROM perf_view_2");
            
        String xFilterString = globalFilter.getFilterString();
        if (xFilterString.equals("")) {
            NotifyManager.getInstance().showError("You must enter a global filter");
            return null;
        }
        
        sql.append(" WHERE ");
        sql.append(xFilterString);

        sql.append(" GROUP BY ");
        sql.append(xAxis.getColumn());
        queries.put("__main__", new JSONString(sql.toString()));
        
        for (Series series : seriesList) {
            sql = new StringBuilder();
            DBColumnSelector valueSelector = series.getDBColumnSelector();
            
            sql.append("SELECT test_idx, ");
            sql.append(valueSelector.getColumn());
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
            
            sql.append(xAxis.getColumn());
            sql.append(" = %s ORDER BY ");
            sql.append(valueSelector.getColumn());
            queries.put("__" + series.getName() + "__", new JSONString(sql.toString()));
        }
        
        return queries;
    }
    
    // Disable the "Invert y-axis" checkboxes if inversion doesn't make sense
    private void checkInvertible() {
        boolean invertible = (
                noNormalizeMultiple.isChecked() ||
                normalizeFirst.isChecked() ||
                normalizeX.isChecked());
        seriesSelector.setInvertible(invertible);
    }
    
    private JSONObject buildParams() {
        JSONObject queries = buildQueries();
        if (queries == null) {
            return null;
        }
        
        JSONObject params = new JSONObject();
        
        params.put("queries", queries);
        String plot = plotSelector.getValue(plotSelector.getSelectedIndex());
        params.put("plot", new JSONString(plot));
        
        if (plot.equals("Line") && noNormalizeSingle.isChecked()) {
            params.put("normalize", new JSONString(NORMALIZE_SINGLE));
        } else if (normalizeFirst.isChecked()) {
            params.put("normalize", new JSONString(NORMALIZE_FIRST));
        } else if (normalizeSeries.isChecked()) {
            String series = 
                normalizeSeriesSelect.getValue(normalizeSeriesSelect.getSelectedIndex());
            params.put("normalize", new JSONString(NORMALIZE_SERIES_PREFIX + series));
        } else if (normalizeX.isChecked()) {
            String baseline = normalizeXSelect.getText();
            params.put("normalize", new JSONString(NORMALIZE_X_PREFIX + baseline));
        }
        
        params.put("invert", Utils.stringsToJSON(seriesSelector.getInverted()));
        
        return params;
    }
}
