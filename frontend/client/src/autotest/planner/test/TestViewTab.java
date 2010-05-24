package autotest.planner.test;

import autotest.planner.TestPlanSelector;
import autotest.planner.TestPlannerDisplay;
import autotest.planner.TestPlannerPresenter;
import autotest.planner.TestPlannerTab;

public class TestViewTab extends TestPlannerTab {

    private TestViewPresenter presenter = new TestViewPresenter();
    private TestViewDisplay display = new TestViewDisplay();

    public TestViewTab(TestPlanSelector selector) {
        super(selector);
    }

    @Override
    public String getElementId() {
        return "test_view";
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

}
