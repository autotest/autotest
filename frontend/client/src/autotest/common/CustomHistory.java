package autotest.common;

import com.google.gwt.user.client.History;
import com.google.gwt.user.client.HistoryListener;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Wrapper around gwt.user.client.History that won't call onHistoryChanged for
 * programmatically-generated history items.
 *
 */
public class CustomHistory implements HistoryListener {
    private static final CustomHistory theInstance = new CustomHistory();
    
    private List<CustomHistoryListener> listeners = new ArrayList<CustomHistoryListener>();
    private String lastHistoryToken = "";
    
    public static interface CustomHistoryListener {
        public void onHistoryChanged(Map<String, String> arguments);
    }
    
    private CustomHistory() {
        History.addHistoryListener(this);
    }
    
    /**
     * Allows programmatic simulation of history changes, without actually changing history or the 
     * URL.
     */
    public static void simulateHistoryToken(String token) {
        theInstance.onHistoryChanged(token);
    }
    
    public static void processInitialToken() {
        theInstance.onHistoryChanged(History.getToken());
    }
    
    public void onHistoryChanged(String historyToken) {
        if (historyToken.equals(lastHistoryToken)) {
            return;
        }
        
        lastHistoryToken = historyToken;
        
        Map<String, String> arguments;
        try {
            arguments = Utils.decodeUrlArguments(historyToken);
        } catch (IllegalArgumentException exc) {
            return;
        }

        for (CustomHistoryListener listener : listeners) {
            listener.onHistoryChanged(arguments);
        }
    }
    
    public static String getLastHistoryToken() {
        return theInstance.lastHistoryToken;
    }

    public static void addHistoryListener(CustomHistoryListener listener) {
        theInstance.listeners.add(listener);
    }
    
    public static void removeHistoryListener(CustomHistoryListener listener) {
        theInstance.listeners.remove(listener);
    }
    
    public static void newItem(String historyToken) {
        if (historyToken.equals(getLastHistoryToken())) {
            return;
        }
        theInstance.lastHistoryToken = historyToken;
        History.newItem(historyToken);
    }
}
