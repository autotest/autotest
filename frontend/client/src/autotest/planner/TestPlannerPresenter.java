package autotest.planner;

import autotest.common.ui.HasTabVisible;

public abstract class TestPlannerPresenter implements TestPlanSelector.Listener {
    private TestPlanSelector selector;
    private HasTabVisible tab;

    public void initialize(TestPlanSelector selector, HasTabVisible tab) {
        this.selector = selector;
        this.tab = tab;
        selector.addListener(this);
    }

    public void refresh() {
        String planId = selector.getSelectedPlan();
        if (planId == null) {
            return;
        }

        refresh(planId);
    }

    @Override
    public void onPlanSelected() {
        if (tab.isTabVisible()) {
            refresh();
        }
    }

    public abstract void refresh(String planId);
}
