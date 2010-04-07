package autotest.planner;

import autotest.common.ui.TabView;


public class MachineViewTabDisplay extends TabView implements MachineViewTab.Display {
    
    @Override
    public String getElementId() {
        return "machine_view";
    }
    
}
