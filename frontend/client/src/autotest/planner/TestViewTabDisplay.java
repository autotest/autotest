package autotest.planner;

import autotest.common.ui.TabView;


public class TestViewTabDisplay extends TabView implements TestViewTab.Display {
    
    @Override
    public String getElementId() {
        return "test_view";
    }
    
}
