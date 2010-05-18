package autotest.planner.overview;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.ui.HasTabVisible;
import autotest.planner.TestPlanSelector;
import autotest.planner.TestPlannerPresenter;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.dom.client.HasKeyPressHandlers;
import com.google.gwt.event.dom.client.KeyCodes;
import com.google.gwt.event.dom.client.KeyPressEvent;
import com.google.gwt.event.dom.client.KeyPressHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.HasText;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

public class OverviewTabPresenter extends TestPlannerPresenter
        implements ClickHandler, KeyPressHandler {

    public static interface Display {
        public HasText getAddPlanText();
        public HasClickHandlers getAddPlanButton();
        public HasKeyPressHandlers getAddPlanField();
        public void setLoading(boolean loading);
        public OverviewTable.Display generateOverviewTableDisplay();
    }

    private Display display;
    private Set<String> selectedPlans = new LinkedHashSet<String>();
    private String lastAdded;

    public void bindDisplay(Display display) {
        this.display = display;
        display.getAddPlanButton().addClickHandler(this);
        display.getAddPlanField().addKeyPressHandler(this);
    }

    @Override
    public void initialize(TestPlanSelector selector_unused, HasTabVisible tab_unused) {}

    @Override
    public void refresh(String planId) {
        throw new UnsupportedOperationException("Should never be called");
    }

    @Override
    public void refresh() {
        JSONObject params = new JSONObject();
        JSONArray planIds = new JSONArray();
        for (String plan : selectedPlans) {
            planIds.set(planIds.size(), new JSONString(plan));
        }
        params.put("plan_ids", planIds);

        display.setLoading(true);

        JsonRpcProxy.getProxy().rpcCall("get_overview_data", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                OverviewTable table = new OverviewTable();
                table.bindDisplay(display.generateOverviewTableDisplay());
                display.setLoading(false);
                table.setData(prepareData(result.isObject()));
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                display.setLoading(false);
                if (Utils.jsonToString(errorObject.get("name")).equals("DoesNotExist")
                        && lastAdded != null) {
                    selectedPlans.remove(lastAdded);
                    lastAdded = null;
                    refresh();
                }
            }
        });
    }

    @Override
    public void onClick(ClickEvent event) {
        assert event.getSource() == display.getAddPlanButton();
        addSelectedPlan();
    }

    @Override
    public void onKeyPress(KeyPressEvent event) {
        assert event.getSource() == display.getAddPlanField();
        if (event.getCharCode() == KeyCodes.KEY_ENTER) {
            addSelectedPlan();
        }
    }

    private void addSelectedPlan() {
        String plan = display.getAddPlanText().getText();
        selectedPlans.add(plan);
        lastAdded = plan;
        refresh();
    }

    private Map<String, JSONObject> prepareData(JSONObject data) {
        Map<String, JSONObject> preparedData = new LinkedHashMap<String, JSONObject>();
        for (String plan : selectedPlans) {
            preparedData.put(plan, data.get(plan).isObject());
        }
        return preparedData;
    }
}
