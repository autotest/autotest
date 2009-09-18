package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.List;

class ConditionTestSet extends TestSet {
    private List<String> conditionParts = new ArrayList<String>(); 
    private JSONObject initialCondition = new JSONObject();
    
    public ConditionTestSet(JSONObject initialCondition) {
        this.initialCondition = initialCondition;
    }

    public ConditionTestSet() {
        this.initialCondition = new JSONObject();
    }
    
    public void addCondition(String condition) {
        conditionParts.add(condition);
    }
    
    @Override
    public JSONObject getInitialCondition() {
        return Utils.copyJSONObject(initialCondition);
    }

    @Override
    public String getPartialSqlCondition() {
        return Utils.joinStrings(" AND ", conditionParts);
    }

    @Override
    public boolean isSingleTest() {
        return false;
    }

    @Override
    public int getTestIndex() {
        throw new UnsupportedOperationException();
    }
}
