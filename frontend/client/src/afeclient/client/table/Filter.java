package afeclient.client.table;

import afeclient.client.SimpleCallback;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public abstract class Filter {
    protected List changeListeners = new ArrayList();
    
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
        for (Iterator i = changeListeners.iterator(); i.hasNext(); ) {
            ((SimpleCallback) i.next()).doCallback(this);
        }
    }
}