package autotest.planner;

import autotest.common.ui.TabView;


public class AutoprocessedTabDisplay extends TabView implements AutoprocessedTab.Display {
    
    @Override
    public String getElementId() {
        return "autoprocessed";
    }
    
}
