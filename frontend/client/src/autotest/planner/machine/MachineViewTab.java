package autotest.planner.machine;

import autotest.planner.TestPlanSelector;
import autotest.planner.TestPlannerDisplay;
import autotest.planner.TestPlannerPresenter;
import autotest.planner.TestPlannerTab;


public class MachineViewTab extends TestPlannerTab {

    private MachineViewPresenter presenter = new MachineViewPresenter();
    private MachineViewDisplay display = new MachineViewDisplay();

    public MachineViewTab(TestPlanSelector selector) {
        super(selector);
    }

    @Override
    public String getElementId() {
        return "machine_view";
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
