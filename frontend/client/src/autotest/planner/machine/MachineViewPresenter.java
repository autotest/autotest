package autotest.planner.machine;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.planner.TestPlannerPresenter;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;


public class MachineViewPresenter extends TestPlannerPresenter {

    public static interface Display {
        public void setLoading(boolean loading);
        public void clearAllData();
        public MachineViewTable.Display generateMachineViewTableDisplay();
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

        JsonRpcProxy.getProxy().rpcCall("get_machine_view_data", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                display.clearAllData();
                display.setLoading(false);

                MachineViewTable table = new MachineViewTable();
                table.bindDisplay(display.generateMachineViewTableDisplay());
                table.setData(result.isArray());
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                display.setLoading(false);
            }
        });
    }
}
