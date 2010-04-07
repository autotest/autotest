package autotest.planner.triage;

import autotest.common.ui.TabView;
import autotest.planner.TestPlanSelector;

import com.google.gwt.user.client.ui.HTMLPanel;


public class TriageViewTab extends TabView {
    
    private TriageViewPresenter presenter;
    private TriageViewDisplay display = new TriageViewDisplay();
    
    public TriageViewTab(TestPlanSelector selector) {
        presenter = new TriageViewPresenter(selector);
    }
    
    @Override
    public String getElementId() {
        return "triage_view";
    }
    
    @Override
    public void initialize() {
        super.initialize();
        display.initialize((HTMLPanel) getWidget());
        presenter.bindDisplay(display);
    }
    
    @Override
    public void refresh() {
        super.refresh();
        presenter.refresh();
    }
}
