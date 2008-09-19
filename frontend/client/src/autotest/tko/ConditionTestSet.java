package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class ConditionTestSet extends TestSet {
    private Map<String,String> fields = new HashMap<String,String>();
    private boolean isSingleTest;
    private JSONObject initialCondition = new JSONObject();

    public ConditionTestSet(boolean isSingleTest) {
        this.isSingleTest = isSingleTest;
    }
    
    public ConditionTestSet(boolean isSingleTest, JSONObject initialCondition) {
        this(isSingleTest);
        this.initialCondition = initialCondition;
    }
    
    public void setField(String field, String value) {
        fields.put(field, value);
    }

    public void setFields(List<String> fields, List<String> values) {
        assert fields.size() == values.size();
        for (int i = 0; i < fields.size(); i++) {
            setField(fields.get(i), values.get(i));
        }
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
              query += " = '" + escapeQuotes(value) + "'";
            }
            parts.add(query);
        }
        
        return Utils.joinStrings(" AND ", parts);
    }

    private String escapeQuotes(String value) {
        // TODO: make this more sophisticated if it becomes necessary
        return value.replace("'", "\\'");
    }

    @Override
    public boolean isSingleTest() {
        return isSingleTest;
    }
}
