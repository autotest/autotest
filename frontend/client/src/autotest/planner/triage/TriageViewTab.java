package autotest.planner.triage;

import autotest.planner.TestPlanSelector;
import autotest.planner.TestPlannerDisplay;
import autotest.planner.TestPlannerPresenter;
import autotest.planner.TestPlannerTab;


public class TriageViewTab extends TestPlannerTab {

    private TriageViewPresenter presenter = new TriageViewPresenter();
    private TriageViewDisplay display = new TriageViewDisplay();

    public TriageViewTab(TestPlanSelector selector) {
        super(selector);
    }

    @Override
    public String getElementId() {
        return "triage_view";
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
