package autotest.common.table;

import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;

public class BooleanFilter extends ListFilter {
    public static final String[] choices = {"Yes", "No"};
    
    public BooleanFilter(String fieldName) {
        super(fieldName);
        setChoices(choices);
    }

    @Override
    public void addParams(JSONObject params) {
        String selected = getSelectedText();
        params.put(fieldName, JSONBoolean.getInstance(selected.equals("Yes")));
    }
}
