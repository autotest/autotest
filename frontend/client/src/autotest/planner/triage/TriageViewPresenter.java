package autotest.planner.triage;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.ui.HasTabVisible;
import autotest.planner.TestPlanSelector;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

public class TriageViewPresenter implements TestPlanSelector.Listener {
    
    public interface Display {
        public void setLoading(boolean loading);
        public void clearAllFailureTables();
        public FailureTable.Display generateFailureTable();
    }
    
    private TestPlanSelector selector;
    private Display display;
    private HasTabVisible tab;
    
    public TriageViewPresenter(TestPlanSelector selector, HasTabVisible tab) {
        this.selector = selector;
        this.tab = tab;
        selector.addListener(this);
    }
    
    public void bindDisplay(Display display) {
        this.display = display;
    }
    
    public void refresh() {
        String planId = selector.getSelectedPlan();
        if (planId == null) {
            return;
        }
        
        display.setLoading(true);
        
        JSONObject params = new JSONObject();
        params.put("plan_id", new JSONString(planId));
        
        JsonRpcProxy.getProxy().rpcCall("get_failures", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                display.clearAllFailureTables();
                generateFailureTables(result.isObject());
                display.setLoading(false);
            }
        });
    }
    
    private void generateFailureTables(JSONObject failures) {        
        for (String group : failures.keySet()) {
            FailureTable table = new FailureTable(group);
            FailureTable.Display tableDisplay = display.generateFailureTable();
            table.bindDisplay(tableDisplay);
            
            JSONArray groupFailures = failures.get(group).isArray();
            
            for (int i = 0; i < groupFailures.size(); i++) {
                table.addFailure(groupFailures.get(i).isObject());
            }
            
            table.renderDisplay();
        }
    }

    @Override
    public void onPlanSelected() {
        if (tab.isTabVisible()) {
            refresh();
        }
    }
}
