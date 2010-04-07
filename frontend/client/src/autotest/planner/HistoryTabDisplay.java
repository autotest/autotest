package autotest.planner;

import autotest.common.ui.TabView;


public class HistoryTabDisplay extends TabView implements HistoryTab.Display {
    
    @Override
    public String getElementId() {
        return "history";
    }
    
}
