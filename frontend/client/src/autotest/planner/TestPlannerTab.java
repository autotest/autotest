package autotest.planner;

import autotest.common.ui.TabView;

import com.google.gwt.user.client.ui.HTMLPanel;

public abstract class TestPlannerTab extends TabView {

    private TestPlanSelector selector;

    public TestPlannerTab(TestPlanSelector selector) {
        this.selector = selector;
    }

    @Override
    public void initialize() {
        super.initialize();
        getPresenter().initialize(selector, this);
        getDisplay().initialize((HTMLPanel) getWidget());
        bindDisplay();
    }

    @Override
    public void refresh() {
        super.refresh();
        getPresenter().refresh();
    }

    @Override
    public void display() {
        super.display();
        setSelectorVisible(true);
    }

    protected final void setSelectorVisible(boolean visible) {
        selector.setVisible(visible);
    }

    protected abstract TestPlannerPresenter getPresenter();
    protected abstract TestPlannerDisplay getDisplay();
    protected abstract void bindDisplay();
}
