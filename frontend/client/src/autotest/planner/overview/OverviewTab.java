package autotest.planner.overview;

import autotest.planner.TestPlanSelector;
import autotest.planner.TestPlannerDisplay;
import autotest.planner.TestPlannerPresenter;
import autotest.planner.TestPlannerTab;

public class OverviewTab extends TestPlannerTab {
    private OverviewTabPresenter presenter = new OverviewTabPresenter();
    private OverviewTabDisplay display = new OverviewTabDisplay();

    public OverviewTab(TestPlanSelector selector) {
        super(selector);
    }

    @Override
    public String getElementId() {
        return "overview";
    }

    @Override
    protected TestPlannerDisplay getDisplay() {
        return display;
    }

    @Override
    protected TestPlannerPresenter getPresenter() {
        return presenter;
    }

    @Override
    protected void bindDisplay() {
        presenter.bindDisplay(display);
    }

    @Override
    public void display() {
        super.display();
        setSelectorVisible(false);
    }
}
