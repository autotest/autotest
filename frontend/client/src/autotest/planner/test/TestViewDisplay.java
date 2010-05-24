package autotest.planner.test;

import autotest.common.ui.NotifyManager;
import autotest.planner.TestPlannerDisplay;
import autotest.planner.TestPlannerTableDisplay;
import autotest.planner.TestPlannerTableImpl;

import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SimplePanel;


public class TestViewDisplay implements TestPlannerDisplay, TestViewPresenter.Display {

    private Panel container = new SimplePanel();

    @Override
    public void initialize(HTMLPanel htmlPanel) {
        htmlPanel.add(container, "test_view_table");
    }

    @Override
    public void clearAllData() {
        container.clear();
    }

    @Override
    public void setLoading(boolean loading) {
        NotifyManager.getInstance().setLoading(loading);
        container.setVisible(!loading);
    }

    @Override
    public TestPlannerTableDisplay generateTestViewTableDisplay() {
        TestPlannerTableImpl display = new TestPlannerTableImpl();
        container.add(display);
        return display;
    }
}
