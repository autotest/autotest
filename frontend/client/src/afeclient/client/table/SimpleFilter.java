package afeclient.client.table;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Widget;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * A simple filter that adds parameters from a string map.
 */
public class SimpleFilter extends Filter {
    protected Map parameters = new HashMap();
    
    public void setParameter(String key, JSONValue value) {
        parameters.put(key, value);
    }

    public void addParams(JSONObject params) {
        for (Iterator i = parameters.keySet().iterator(); i.hasNext(); ) {
            String key = (String) i.next();
            JSONValue value = (JSONValue) parameters.get(key);
            params.put(key, value);
        }
    }

    public Widget getWidget() {
        return null;
    }

    public boolean isActive() {
        return true;
    }

}
