package autotest.afe;

import autotest.afe.CreateJobView.JobCreateListener;
import autotest.afe.HostDetailView.HostDetailListener;
import autotest.afe.HostListView.HostListListener;
import autotest.afe.JobDetailView.JobDetailListener;
import autotest.afe.JobListView.JobSelectListener;
import autotest.common.CustomHistory;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.ui.CustomTabPanel;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.RootPanel;

public class AfeClient implements EntryPoint {
    protected JobListView jobList;
    protected JobDetailView jobDetail;
    protected CreateJobView createJob;
    protected HostListView hostListView;
    protected HostDetailView hostDetailView;

    public CustomTabPanel mainTabPanel = new CustomTabPanel();

    /**
     * Application entry point.
     */
    public void onModuleLoad() {
        JsonRpcProxy.setDefaultUrl(JsonRpcProxy.AFE_URL);
        NotifyManager.getInstance().initialize();
        
        // initialize static data, and don't show main UI until that's done
        StaticDataRepository.getRepository().refresh(
                                 new StaticDataRepository.FinishedCallback() {
            public void onFinished() {
                finishLoading();
            }
        });
    }
    
    protected void finishLoading() {
        jobList = new JobListView(new JobSelectListener() {
            public void onJobSelected(int jobId) {
                showJob(jobId);
            }
        });
        jobDetail = new JobDetailView(new JobDetailListener() {
            public void onHostSelected(String hostname) {
                showHost(hostname);
            }
            
            public void onCloneJob(JSONValue cloneInfo) {
                createJob.ensureInitialized();
                mainTabPanel.selectTabView(createJob);
                createJob.cloneJob(cloneInfo);
            }
        });
        createJob = AfeUtils.factory.getCreateJobView(new JobCreateListener() {
            public void onJobCreated(int jobId) {
                showJob(jobId);
            }
        });
        hostListView = new HostListView(new HostListListener() {
            public void onHostSelected(String hostname) {
                showHost(hostname);
            }
        });
        hostDetailView = new HostDetailView(new HostDetailListener() {
            public void onJobSelected(int jobId) {
                showJob(jobId);
            }
        });
        
        TabView[] tabViews = new TabView[] {jobList, jobDetail, createJob, 
                                            hostListView, hostDetailView};
        for(int i = 0; i < tabViews.length; i++) {
            mainTabPanel.addTabView(tabViews[i]);
        }
        
        final RootPanel tabsRoot = RootPanel.get("tabs");
        tabsRoot.add(mainTabPanel);
        CustomHistory.processInitialToken();
        mainTabPanel.initialize();
        tabsRoot.setStyleName("");
    }
    
    protected void showJob(int jobId) {
        jobDetail.ensureInitialized();
        jobDetail.fetchJob(jobId);
        mainTabPanel.selectTabView(jobDetail);
    }

    protected void showHost(String hostname) {
        hostDetailView.ensureInitialized();
        hostDetailView.fetchById(hostname);
        mainTabPanel.selectTabView(hostDetailView);
    }
}
