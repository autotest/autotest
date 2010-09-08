package autotest.afe.create;

import autotest.afe.create.CreateJobViewPresenter.JobCreateListener;
import autotest.common.ui.TabView;

import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.HTMLPanel;

public class CreateJobViewTab extends TabView {
    private CreateJobViewPresenter presenter;
    private CreateJobViewDisplay display;

    protected CreateJobViewTab() {}

    public CreateJobViewTab(JobCreateListener listener) {
        presenter = new CreateJobViewPresenter(listener);
        display = new CreateJobViewDisplay();
        presenter.bindDisplay(display);
    }

    @Override
    public String getElementId() {
        return "create_job";
    }

    @Override
    public void initialize() {
        super.initialize();
        getDisplay().initialize((HTMLPanel) getWidget());
        getPresenter().initialize();
    }

    @Override
    public void refresh() {
        super.refresh();
        getPresenter().refresh();
    }

    public void cloneJob(JSONValue cloneInfo) {
        getPresenter().cloneJob(cloneInfo);
    }

    public void onPreferencesChanged() {
        getPresenter().onPreferencesChanged();
    }

    protected CreateJobViewPresenter getPresenter() {
        return presenter;
    }

    protected CreateJobViewDisplay getDisplay() {
        return display;
    }
}
