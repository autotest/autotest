package autotest.tko;

import autotest.common.JsonRpcProxy;
import autotest.common.spreadsheet.Spreadsheet;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;
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

    private Spreadsheet spreadsheet = new Spreadsheet();
    private SpreadsheetDataProcessor spreadsheetProcessor =
            new SpreadsheetDataProcessor(spreadsheet);

    @Override
    public void onModuleLoad() {
        JsonRpcProxy.setDefaultBaseUrl(JsonRpcProxy.TKO_BASE_URL);
        setupListener();

        spreadsheetProcessor.setDataSource(TestGroupDataSource.getStatusCountDataSource());
        spreadsheetProcessor.setHeaders(
                Collections.singletonList(new SimpleHeaderField(ROW_HEADER)),
                Collections.singletonList(new SimpleHeaderField(COLUMN_HEADER)),
                new JSONObject());

        RootPanel.get().add(spreadsheet);
    }

    private native void setupListener() /*-{
        var instance = this;
        $wnd.onGotJobId = function(event) {
            var jobId = parseInt(event.data);
            instance.@autotest.tko.EmbeddedSpreadsheetClient::createSpreadsheet(I)(jobId);
        }

        $wnd.addEventListener("message", $wnd.onGotJobId, false);
    }-*/;

    @SuppressWarnings("unused") // called from native
    private void createSpreadsheet(int afeJobId) {
        spreadsheet.clear();
        final JSONObject condition = getFilterCondition(afeJobId);
        spreadsheetProcessor.refresh(condition, new Command() {
            public void execute() {
                condition.put("extra_info", null);
                notifyParent(spreadsheet.getElement().getClientWidth(),
                        spreadsheet.getElement().getClientHeight());
            }
        });
    }

    private JSONObject getFilterCondition(int afeJobId) {
        JSONObject condition = new JSONObject();
        condition.put("afe_job_id", new JSONNumber(afeJobId));
        return condition;
    }

    private native void notifyParent(int width, int height) /*-{
        $wnd.parent.postMessage(width + 'px ' + height + 'px', '*');
    }-*/;
}
