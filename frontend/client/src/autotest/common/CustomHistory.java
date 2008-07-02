package autotest.common;

import com.google.gwt.user.client.History;
import com.google.gwt.user.client.HistoryListener;

import java.util.ArrayList;
import java.util.List;

/**
 * Wrapper around gwt.user.client.History that won't call onHistoryChanged for
 * programmatically-generated history items.
 *
 */
public class CustomHistory implements HistoryListener {
    protected static final CustomHistory theInstance = new CustomHistory();
    
    protected List<HistoryListener> listeners = new ArrayList<HistoryListener>();
    protected boolean ignoreNextChange = false;
    
    protected CustomHistory() {
        History.addHistoryListener(this);
    }
    
    public void onHistoryChanged(String historyToken) {
        if (ignoreNextChange) {
            ignoreNextChange = false;
            return;
        }

        for (HistoryListener listener : listeners) {
            listener.onHistoryChanged(historyToken);
        }
    }

    public static void addHistoryListener(HistoryListener listener) {
        theInstance.listeners.add(listener);
    }
    
    public static void removeHistoryListener(HistoryListener listener) {
        theInstance.listeners.remove(listener);
    }
    
    public static void newItem(String historyToken) {
        if (History.getToken().equals(historyToken))
            return;
        theInstance.ignoreNextChange = true;
        History.newItem(historyToken);
    }
}
