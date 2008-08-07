package autotest.tko;

import autotest.common.ui.TabView;

import com.google.gwt.user.client.ui.RootPanel;

public class GraphingView extends TabView {
    
    private ExistingGraphsFrontend existingGraphsFrontend = new ExistingGraphsFrontend();
    
    @Override
    public void initialize() {
        RootPanel.get("graphing_frontend").add(existingGraphsFrontend);
    }
    
    @Override
    public String getElementId() {
        return "graphing_view";
    }
    
    @Override
    public void refresh() {
        super.refresh();
        existingGraphsFrontend.refresh();
    }

    @Override
    public void display() {
        super.display();
        CommonPanel.getPanel().setConditionVisible(false);
    }
}
