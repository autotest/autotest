package autotest.planner.triage;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.ui.HasTabVisible;
import autotest.planner.TestPlanSelector;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.List;

public class TriageViewPresenter implements ClickHandler, TestPlanSelector.Listener,
                                            TriagePopup.Listener {
    
    public interface Display {
        public void setLoading(boolean loading);
        public void clearAllFailureTables();
        public FailureTable.Display generateFailureTable(String group, String[] columnNames);
        public TriagePopup.Display generateTriagePopupDisplay();
        public HasClickHandlers getTriageButton();
    }
    
    private TestPlanSelector selector;
    private Display display;
    private HasTabVisible tab;
    private List<FailureTable> failureTables = new ArrayList<FailureTable>();
    
    public TriageViewPresenter(TestPlanSelector selector, HasTabVisible tab) {
        this.selector = selector;
        this.tab = tab;
        selector.addListener(this);
    }
    
    public void bindDisplay(Display display) {
        this.display = display;
        display.getTriageButton().addClickHandler(this);
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
                display.setLoading(false);
                generateFailureTables(result.isObject());
            }
            
            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                display.setLoading(false);
            }
        });
    }
    
    private void generateFailureTables(JSONObject failures) {
        failureTables.clear();
        
        for (String group : failures.keySet()) {
            FailureTable table = new FailureTable();
            FailureTable.Display tableDisplay =
                    display.generateFailureTable(group, FailureTable.COLUMN_NAMES);
            table.bindDisplay(tableDisplay);
            
            JSONArray groupFailures = failures.get(group).isArray();
            
            for (int i = 0; i < groupFailures.size(); i++) {
                table.addFailure(groupFailures.get(i).isObject());
            }
            
            failureTables.add(table);
        }
    }

    @Override
    public void onPlanSelected() {
        if (tab.isTabVisible()) {
            refresh();
        }
    }

    @Override
    public void onClick(ClickEvent event) {
        assert event.getSource() == display.getTriageButton();
        
        List<Integer> failureIds = new ArrayList<Integer>();
        for (FailureTable failure : failureTables) {
            failureIds.addAll(failure.getSelectedFailureIds());
        }
        
        TriagePopup popup = new TriagePopup(this, failureIds);
        popup.bindDisplay(display.generateTriagePopupDisplay());
        popup.render();
    }

    @Override
    public void onTriage() {
        refresh();
    }
}
