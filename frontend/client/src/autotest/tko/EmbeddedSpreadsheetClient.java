package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.spreadsheet.Spreadsheet;
import autotest.common.spreadsheet.Spreadsheet.CellInfo;
import autotest.common.spreadsheet.Spreadsheet.SpreadsheetListener;
import autotest.tko.TkoSpreadsheetUtils.DrilldownType;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.dom.client.Element;
import com.google.gwt.http.client.URL;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.RootPanel;

import java.util.Collections;
import java.util.List;

public class EmbeddedSpreadsheetClient implements EntryPoint, SpreadsheetListener {
    private static class SimpleHeaderField extends HeaderField {
        protected SimpleHeaderField(String name) {
            super(name, name);
        }

        @Override
        public String getSqlCondition(String value) {
            return getSimpleSqlCondition(name, value);
        }
    }

    public static final String ROW_HEADER = "hostname";
    public static final String COLUMN_HEADER = "test_name";
    private static final String NO_RESULTS = "There are no results for this query (yet?)";

    public static final String DRILLDOWN_ROW_HEADER = "job_tag";
    public static final String DRILLDOWN_COLUMN_HEADER = "subdir";

    private Label noResults = new Label(NO_RESULTS);
    private Spreadsheet spreadsheet = new Spreadsheet();
    private SpreadsheetDataProcessor spreadsheetProcessor =
            new SpreadsheetDataProcessor(spreadsheet);
    private List<HeaderField> rowHeader =
            Collections.singletonList((HeaderField) new SimpleHeaderField(ROW_HEADER));
    private List<HeaderField> columnHeader =
            Collections.singletonList((HeaderField) new SimpleHeaderField(COLUMN_HEADER));

    private String afeJobIdStr;
    private JSONObject condition;

    @Override
    public void onModuleLoad() {
        JsonRpcProxy.setDefaultBaseUrl(JsonRpcProxy.TKO_BASE_URL);
        afeJobIdStr = Window.Location.getParameter("afe_job_id");
        checkAndRender();
    }

    private void checkAndRender() {
        condition = getFilterCondition(afeJobIdStr);
        if (condition == null) {
            showNoResults();
        }

        JsonRpcProxy.getProxy().rpcCall("get_num_test_views", condition, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                if (result.isNumber().doubleValue() != 0) {
                    renderSpreadsheet(condition);
                } else {
                    showNoResults();
                }
            }
        });
    }

    private JSONObject getFilterCondition(String afeJobIdStr) {
        if (afeJobIdStr == null) {
            return null;
        }

        int afeJobId;
        try {
            afeJobId = Integer.parseInt(afeJobIdStr);
        } catch (NumberFormatException e) {
            return null;
        }

        JSONObject condition = new JSONObject();
        condition.put("afe_job_id", new JSONNumber(afeJobId));
        return condition;
    }

    private void showNoResults() {
        RootPanel.get().add(noResults);
        notifyParent(noResults.getElement());
    }

    private void renderSpreadsheet(JSONObject condition) {
        spreadsheetProcessor.setDataSource(TestGroupDataSource.getStatusCountDataSource());
        spreadsheetProcessor.setHeaders(rowHeader, columnHeader, new JSONObject());

        spreadsheet.setListener(this);
        RootPanel.get().add(spreadsheet);
        spreadsheetProcessor.refresh(condition, new Command() {
            public void execute() {
                notifyParent(spreadsheet.getElement());
            }
        });
    }

    private void notifyParent(Element elem) {
        notifyParent(elem.getClientWidth(), elem.getClientHeight());
    }

    private native void notifyParent(int width, int height) /*-{
        $wnd.parent.postMessage(width + 'px ' + height + 'px', '*');
    }-*/;

    @Override
    public void onCellClicked(CellInfo cellInfo, boolean isRightClick) {
        TestSet testSet = TkoSpreadsheetUtils.getTestSet(
                cellInfo, condition, rowHeader, columnHeader);

        if (testSet.isSingleTest()) {
            openTestDetailView(testSet.getTestIndex());
        } else {
            openSpreadsheetView(testSet.getPartialSqlCondition(),
                    TkoSpreadsheetUtils.getDrilldownType(cellInfo));
        }
    }

    private void openTestDetailView(int testIdx) {
        openUrl("/new_tko/#tab_id=test_detail_view&object_id=" + testIdx);
    }

    private void openSpreadsheetView(String extraCondition, DrilldownType drilldownType) {
        String drilldownPath;

        switch (drilldownType) {
        case DRILLDOWN_ROW:
            drilldownPath = generatePath(DRILLDOWN_ROW_HEADER, COLUMN_HEADER, extraCondition);
            break;
        case DRILLDOWN_COLUMN:
            drilldownPath = generatePath(ROW_HEADER, DRILLDOWN_COLUMN_HEADER, extraCondition);
            break;
        case DRILLDOWN_BOTH:
            drilldownPath = generatePath(
                    DRILLDOWN_ROW_HEADER, DRILLDOWN_COLUMN_HEADER, extraCondition);
            break;
        default:
            throw new UnsupportedOperationException(
                    "DrilldownType " + drilldownType + " not supported");
        }

        openUrl(drilldownPath);
    }

    private String generatePath(String rowHeader, String columnHeader, String extraCondition) {
        String condition = "afe_job_id = " + afeJobIdStr + " AND " + extraCondition;

        return "/new_tko/#tab_id=spreadsheet_view&row=" + rowHeader + "&column=" + columnHeader +
                "&condition=" + URL.encodeComponent(condition, true) + "&show_incomplete=true";
    }

    private void openUrl(String url) {
        Window.open(url, "_blank", null);
    }
}
