package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class ConditionTestSet extends TestSet {
    private Map<String,String> fields = new HashMap<String,String>();
    private List<String> conditionParts = new ArrayList<String>(); 
    private JSONObject initialCondition = new JSONObject();
    
    public ConditionTestSet(JSONObject initialCondition) {
        this.initialCondition = initialCondition;
    }

    public ConditionTestSet() {
        this.initialCondition = new JSONObject();
    }

    public void setField(String field, String value) {
        fields.put(field, value);
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
        ArrayList<String> parts = new ArrayList<String>();
        for (Map.Entry<String, String> entry : fields.entrySet()) {
            String query = entry.getKey();  
            String value = entry.getValue();
            if (value.equals(Utils.JSON_NULL)) {
              query += " is null";
            } else {
              query += " = '" + TkoUtils.escapeSqlValue(value) + "'";
            }
            parts.add(query);
        }
        for (String part : conditionParts) {
            parts.add(part);
        }
        
        return Utils.joinStrings(" AND ", parts);
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
