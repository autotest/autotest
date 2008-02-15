package afeclient.client;

import afeclient.client.CreateJobView.JobCreateListener;

public class ClassFactory {
    public CreateJobView getCreateJobView(JobCreateListener listener) {
        return new CreateJobView(listener);
    }
}
