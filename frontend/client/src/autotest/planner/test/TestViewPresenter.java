package autotest.planner.test;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.planner.TestPlannerPresenter;
import autotest.planner.TestPlannerTableDisplay;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

public class TestViewPresenter extends TestPlannerPresenter {

    public static interface Display {
        public void setLoading(boolean loading);
        public void clearAllData();
        public TestPlannerTableDisplay generateTestViewTableDisplay();
    }

    private Display display;

    public void bindDisplay(Display display) {
        this.display = display;
    }

    @Override
    public void refresh(String planId) {
        display.setLoading(true);

        JSONObject params = new JSONObject();
        params.put("plan_id", new JSONString(planId));

        JsonRpcProxy.getProxy().rpcCall("get_test_view_data", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                display.clearAllData();
                display.setLoading(false);

                TestViewTable table = new TestViewTable();
                table.bindDisplay(display.generateTestViewTableDisplay());
                table.setData(result.isObject());
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                display.setLoading(false);
            }
        });
    }

}
