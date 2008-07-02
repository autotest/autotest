package autotest.common.table;

import autotest.common.SimpleCallback;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.List;

public abstract class Filter {
    protected List<SimpleCallback> changeListeners =
        new ArrayList<SimpleCallback>();
    
    public abstract void addParams(JSONObject params);
    public abstract boolean isActive();
    public abstract Widget getWidget();
    
    public void addListener(SimpleCallback listener) {
        changeListeners.add(listener);
    }
    
    public void removeListener(SimpleCallback listener) {
        changeListeners.remove(listener);
    }
    
    protected void notifyListeners() {
        for (SimpleCallback listener : changeListeners) {
            listener.doCallback(this);
        }
    }
}