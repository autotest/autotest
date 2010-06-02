package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.spreadsheet.Spreadsheet;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.dom.client.Element;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.RootPanel;

import java.util.Collections;

public class EmbeddedSpreadsheetClient implements EntryPoint {
    private static class SimpleHeaderField extends HeaderField {
        protected SimpleHeaderField(String name) {
            super(name, name);
        }

        @Override
        public String getSqlCondition(String value) {
            throw new UnsupportedOperationException("No SQL condition");
        }
    }

    public static final String ROW_HEADER = "hostname";
    public static final String COLUMN_HEADER = "test_name";
    private static final String NO_RESULTS = "There are no results for this query (yet?)";

    private Label noResults = new Label(NO_RESULTS);
    private Spreadsheet spreadsheet = new Spreadsheet();
    private SpreadsheetDataProcessor spreadsheetProcessor =
            new SpreadsheetDataProcessor(spreadsheet);

    @Override
    public void onModuleLoad() {
        JsonRpcProxy.setDefaultBaseUrl(JsonRpcProxy.TKO_BASE_URL);
        checkAndRender(Window.Location.getParameter("afe_job_id"));
    }

    private void checkAndRender(String afeJobIdStr) {
        final JSONObject condition = getFilterCondition(afeJobIdStr);
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
        spreadsheetProcessor.setHeaders(
                Collections.singletonList(new SimpleHeaderField(ROW_HEADER)),
                Collections.singletonList(new SimpleHeaderField(COLUMN_HEADER)),
                new JSONObject());

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
}
