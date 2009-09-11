package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.Utils;
import autotest.common.ui.SimpleDialog;
import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.FlexTable;

class MetricsPlot extends Plot {
    public MetricsPlot() {
        super("create_metrics_plot");
    }

    /**
     * drilldownParams contains:
     * * query - SQL query for the selected series
     * * series - name of the selected series
     * * param - parameter to fill in query for the selected data point
     */
    @Override
    protected void showDrilldownImpl(JSONObject drilldownParams) {
        String query = Utils.jsonToString(drilldownParams.get("query"));
        final String series = Utils.jsonToString(drilldownParams.get("series"));
        final String param = Utils.jsonToString(drilldownParams.get("param"));

        JSONObject params = new JSONObject();
        params.put("query", new JSONString(query));
        params.put("param", new JSONString(param));
        rpcProxy.rpcCall("execute_query_with_param", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONArray data = result.isArray();
                
                String title = series + " for " + param;
                FlexTable contents = new FlexTable();
                final SimpleDialog drill = new SimpleDialog(title, contents);
                
                for (int i = 0; i < data.size(); i++) {
                    final JSONArray row = data.get(i).isArray();
                    final int testId = (int) row.get(0).isNumber().doubleValue();
                    String yValue = Utils.jsonToString(row.get(1));

                    SimpleHyperlink link = new SimpleHyperlink(yValue);
                    link.addClickHandler(new ClickHandler() {
                        public void onClick(ClickEvent event) {
                            drill.hide();
                            listener.onSelectTest(testId);
                        }
                    });
                    contents.setWidget(i, 0, link);
                }
                
                drill.center();
            }
        });
    }
}
