package autotest.common.table;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Widget;

/**
 * A simple filter that adds parameters from a string map.
 */
public class SimpleFilter extends Filter {
    private JSONObject parameters = new JSONObject();
    
    public void setParameter(String key, JSONValue value) {
        parameters.put(key, value);
    }
    
    private void updateObject(JSONObject to, JSONObject from) {
        for (String key : from.keySet()) {
            JSONValue value = from.get(key);
            to.put(key, value);
        }
    }
    
    public void setAllParameters(JSONObject params) {
        clear();
        updateObject(parameters, params);
    }

    @Override
    public void addParams(JSONObject params) {
        updateObject(params, parameters);
    }

    @Override
    public Widget getWidget() {
        return null;
    }

    @Override
    public boolean isActive() {
        return true;
    }

    public void clear() {
        parameters = new JSONObject();
    }

}
