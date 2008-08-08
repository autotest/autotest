package autotest.tko;

import autotest.common.ui.TabView;

import java.util.Map;

abstract class ConditionTabView extends TabView {
    protected static CommonPanel commonPanel = CommonPanel.getPanel();
    private String lastCondition = "";
    private boolean needsRefresh;
    
    protected void checkForHistoryChanges(Map<String, String> newParameters) {
        if (!getHistoryArguments().equals(newParameters)) {
            needsRefresh = true;
        }
    }
    
    protected void setNeedsRefresh(boolean needsRefresh) {
        this.needsRefresh = needsRefresh;
    }
    
    protected abstract boolean hasFirstQueryOccurred();
    
    @Override
    public void display() {
        ensureInitialized();
        commonPanel.setConditionVisible(true);
        if (needsRefresh || !commonPanel.getSavedCondition().equals(lastCondition)) {
            saveCondition();
            refresh();
            needsRefresh = false;
        }
        visible = true;
    }

    protected void saveCondition() {
        commonPanel.saveSqlCondition();
        lastCondition = commonPanel.getSavedCondition();
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
}
