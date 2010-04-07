package autotest.planner;

import autotest.common.ui.TabView;


public class OverviewTabDisplay extends TabView implements OverviewTab.Display {
  
    @Override
    public String getElementId() {
        return "overview";
    }
    
}
