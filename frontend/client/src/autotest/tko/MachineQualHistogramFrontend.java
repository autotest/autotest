package autotest.tko;

import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;

import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.TextBox;

import java.util.Map;

public class MachineQualHistogramFrontend extends DynamicGraphingFrontend {
    private static final String DEFAULT_INTERVAL = "10";

    private FilterSelector globalFilters =
        new FilterSelector(DBColumnSelector.TEST_VIEW);
    private FilterSelector testFilters =
        new FilterSelector(DBColumnSelector.TEST_VIEW);
    private TextBox interval = new TextBox();

    public MachineQualHistogramFrontend(final TabView parent) {
        super(parent, new MachineQualHistogram(), "qual");

        interval.setText(DEFAULT_INTERVAL);

        addControl("Preconfigured:", preconfig);
        addControl("Global filters:", globalFilters);
        addControl("Test set filters:", testFilters);
        addControl("Interval:", interval);
        
        commonInitialization();
    }
    
    @Override
    protected void addAdditionalEmbeddingParams(JSONObject params) {
        params.put("graph_type", new JSONString("qual"));
        params.put("params", buildParams());
    }
    
    private JSONString buildQuery() {
        String gFilterString = globalFilters.getFilterString();
        String tFilterString = testFilters.getFilterString();
        boolean hasGFilter = !gFilterString.equals("");
        boolean hasTFilter = !tFilterString.equals("");
        
        StringBuilder sql = new StringBuilder();
        
        sql.append("SELECT hostname, COUNT(DISTINCT ");
        if (hasTFilter) {
            sql.append("IF(");
            sql.append(tFilterString);
            sql.append(", test_idx, NULL)");
        } else {
            sql.append("test_idx");
        }
        sql.append(") 'total', COUNT(DISTINCT IF(");
        if (hasTFilter) {
            sql.append(TkoUtils.wrapWithParens(tFilterString));
            sql.append(" AND ");
        }
        
        sql.append("status = 'GOOD', test_idx, NULL)) 'good' FROM tko_test_view_outer_joins");
        if (hasGFilter) {
            sql.append(" WHERE ");
            sql.append(gFilterString);
        }
        sql.append(" GROUP BY hostname");
        return new JSONString(sql.toString());
    }
    
    private JSONString buildFilterString() {
        StringBuilder filterString = new StringBuilder();
        String gFilterString = globalFilters.getFilterString();
        String tFilterString = testFilters.getFilterString();
        boolean hasGFilter = !gFilterString.equals("");
        boolean hasTFilter = !tFilterString.equals("");
        if (hasGFilter) {
            filterString.append(TkoUtils.wrapWithParens(gFilterString));
            if (hasTFilter) {
                filterString.append(" AND ");
            }
        }
        if (hasTFilter) {
            filterString.append(TkoUtils.wrapWithParens(tFilterString));
        }
        return new JSONString(filterString.toString());
    }
    
    @Override
    protected JSONObject buildParams() {
        if (interval.getText().equals("")) {
            NotifyManager.getInstance().showError("You must enter an interval");
            return null;
        }
        
        int intervalValue;
        try {
            intervalValue = Integer.parseInt(interval.getText());
        } catch (NumberFormatException e) {
            NotifyManager.getInstance().showError("Interval must be an integer");
            return null;
        }
        
        JSONObject params = new JSONObject();
        params.put("query", buildQuery());
        params.put("filter_string", buildFilterString());
        params.put("interval", new JSONNumber(intervalValue));

        return params;
    }

    @Override
    public String getFrontendId() {
        return "machine_qual_histogram";
    }
    
    @Override
    public void addToHistory(Map<String, String> args) {
        globalFilters.addToHistory(args, "globalFilter");
        testFilters.addToHistory(args, "testFilter");
        args.put("interval", interval.getText());
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> args) {
        setVisible(false);
        globalFilters.reset();
        testFilters.reset();
        globalFilters.handleHistoryArguments(args, "globalFilter");
        testFilters.handleHistoryArguments(args, "testFilter");
        interval.setText(args.get("interval"));
        setVisible(true);
    }
}
