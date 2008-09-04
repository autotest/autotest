package autotest.tko;

import com.google.gwt.user.client.Event;

import autotest.common.ui.TabView;

import java.util.Map;

abstract class ConditionTabView extends TabView {
    protected static CommonPanel commonPanel = CommonPanel.getPanel();
    private boolean needsRefresh;
    
    protected void checkForHistoryChanges(Map<String, String> newParameters) {
        if (!getHistoryArguments().equals(newParameters)) {
            needsRefresh = true;
        }
    }
    
    protected abstract boolean hasFirstQueryOccurred();
    
    @Override
    public void display() {
        ensureInitialized();
        commonPanel.setConditionVisible(true);
        if (needsRefresh) {
            commonPanel.saveSqlCondition();
            refresh();
            needsRefresh = false;
        }
        visible = true;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        if (!hasFirstQueryOccurred()) {
            needsRefresh = true;
        }
        commonPanel.fillDefaultHistoryValues(arguments);
        fillDefaultHistoryValues(arguments);
        checkForHistoryChanges(arguments);
        commonPanel.handleHistoryArguments(arguments);
    }

    protected abstract void fillDefaultHistoryValues(Map<String, String> arguments);

    static boolean isSelectEvent(Event event) {
        // handle ctrl-click for windows or command-click for macs
        return event.getCtrlKey() || event.getMetaKey();
    }
}
