package autotest.afe;

import autotest.afe.CreateJobView.JobCreateListener;

public class ClassFactory {
    public CreateJobView getCreateJobView(JobCreateListener listener) {
        return new CreateJobView(listener);
    }
}
