package autotest.afe;

import autotest.afe.create.CreateJobViewPresenter.JobCreateListener;
import autotest.afe.create.CreateJobViewTab;

class ClassFactory {
    public CreateJobViewTab getCreateJobView(JobCreateListener listener) {
        return new CreateJobViewTab(listener);
    }
}
