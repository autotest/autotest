package autotest.common.table;

import autotest.common.SimpleCallback;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.List;

public abstract class Filter {
    protected List<SimpleCallback> callbacks = new ArrayList<SimpleCallback>();
    
    public abstract void addParams(JSONObject params);
    public abstract boolean isActive();
    public abstract Widget getWidget();
    
    public void addCallback(SimpleCallback callback) {
        callbacks.add(callback);
    }
    
    public void removeCallback(SimpleCallback callback) {
        callbacks.remove(callback);
    }
    
    protected void notifyListeners() {
        for (SimpleCallback callback : callbacks) {
            callback.doCallback(this);
        }
    }
}