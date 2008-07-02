package autotest.common.table;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Widget;

import java.util.HashMap;
import java.util.Map;

/**
 * A simple filter that adds parameters from a string map.
 */
public class SimpleFilter extends Filter {
    protected Map<String, JSONValue> parameters = new HashMap<String, JSONValue>();
    
    public void setParameter(String key, JSONValue value) {
        parameters.put(key, value);
    }

    @Override
    public void addParams(JSONObject params) {
        for (String key : parameters.keySet()) {
            JSONValue value = parameters.get(key);
            params.put(key, value);
        }
    }

    @Override
    public Widget getWidget() {
        return null;
    }

    @Override
    public boolean isActive() {
        return true;
    }

}
