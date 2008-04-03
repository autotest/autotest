package afeclient.client.table;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

abstract class FieldFilter extends Filter {
    protected String fieldName;
    protected boolean isExactMatch = true;
    
    public FieldFilter(String fieldName) {
        this.fieldName = fieldName;
    }
    
    public void setExactMatch(boolean exactMatch) {
        isExactMatch = exactMatch;
    }
    
    public abstract String getMatchValue();
    
    public void addParams(JSONObject params) {
        String queryField = fieldName;
        if (!isExactMatch)
            queryField += "__icontains";
        params.put(queryField, new JSONString(getMatchValue()));
    }
}