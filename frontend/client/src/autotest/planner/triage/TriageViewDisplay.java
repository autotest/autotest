package autotest.planner.triage;

import autotest.common.ui.NotifyManager;

import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.VerticalPanel;


public class TriageViewDisplay implements TriageViewPresenter.Display {
    
    private VerticalPanel container = new VerticalPanel();
    
    public void initialize(HTMLPanel htmlPanel) {
        container.setSpacing(25);
        htmlPanel.add(container, "triage_failure_tables");
    }
    
    @Override
    public void setLoading(boolean loading) {
        NotifyManager.getInstance().setLoading(loading);
        container.setVisible(!loading);
    }
    
    @Override
    public FailureTable.Display generateFailureTable() {
        FailureTableDisplay display = new FailureTableDisplay();
        container.add(display);
        return display;
    }

    @Override
    public void clearAllFailureTables() {
        container.clear();
    }
}
