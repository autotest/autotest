package afeclient.client;

import afeclient.client.CreateJobView.JobCreateListener;
import afeclient.client.JobListView.JobSelectListener;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.user.client.History;
import com.google.gwt.user.client.HistoryListener;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.SourcesTabEvents;
import com.google.gwt.user.client.ui.TabListener;
import com.google.gwt.user.client.ui.TabPanel;
import com.google.gwt.user.client.ui.Widget;

public class ClientMain implements EntryPoint, HistoryListener {
    static final String RPC_URL = "/afe/server/rpc/";

    protected JobListView jobList;
    protected JobDetailView jobDetail;
    protected CreateJobView createJob;
    protected HostListView hostListView;
    
    protected TabView[] tabViews;

    protected TabPanel mainTabPanel;
    protected Button refreshButton = new Button("Refresh");

    /**
     * Application entry point.
     */
    public void onModuleLoad() {
        JsonRpcProxy.getProxy().setUrl(RPC_URL);
        
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
        jobDetail = new JobDetailView();
        createJob = Utils.factory.getCreateJobView(new JobCreateListener() {
            public void onJobCreated(int jobId) {
                showJob(jobId);
            }
        });
        hostListView = new HostListView();
        
        tabViews = new TabView[4];
        tabViews[0] = jobList;
        tabViews[1] = jobDetail;
        tabViews[2] = createJob;
        tabViews[3] = hostListView;
        
        CustomTabPanel customPanel = new CustomTabPanel();
        mainTabPanel = customPanel.tabPanel;
        for(int i = 0; i < tabViews.length; i++) {
            mainTabPanel.add(tabViews[i], tabViews[i].getTitle());
        }
        mainTabPanel.addTabListener(new TabListener() {
            public boolean onBeforeTabSelected(SourcesTabEvents sender,
                                               int tabIndex) {
                // do nothing if the user clicks the selected tab
                if (mainTabPanel.getTabBar().getSelectedTab() == tabIndex)
                    return false;
                tabViews[tabIndex].ensureInitialized();
                tabViews[tabIndex].updateHistory();
                // let onHistoryChanged() call TabView.display()
                return true;
            }
            public void onTabSelected(SourcesTabEvents sender, int tabIndex) {}
        });
        
        final RootPanel tabsRoot = RootPanel.get("tabs");
        tabsRoot.add(customPanel);
        
        refreshButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                tabViews[mainTabPanel.getTabBar().getSelectedTab()].refresh();
            } 
        });
        customPanel.otherWidgetsPanel.add(refreshButton);
        
        History.addHistoryListener(this);
        String initialToken = History.getToken();
        if (!initialToken.equals("")) {
            onHistoryChanged(initialToken);
        }
        
        // if the history token didn't provide a selected tab, default to the 
        // first tab
        if (mainTabPanel.getTabBar().getSelectedTab() == -1)
            mainTabPanel.selectTab(0);
        
        RootPanel.get("tabs").setStyleName("");
    }
    
    protected void showJob(int jobId) {
        jobDetail.ensureInitialized();
        jobDetail.setJobID(jobId);
        mainTabPanel.selectTab(1);
    }

    public void onHistoryChanged(String historyToken) {
        if (!historyToken.startsWith(TabView.HISTORY_PREFIX))
            return;
        
        // remove prefix
        historyToken = historyToken.substring(TabView.HISTORY_PREFIX.length());
        for (int i = 0; i < tabViews.length; i++) {
            String tabId = tabViews[i].getElementId();
            if (historyToken.startsWith(tabId)) {
                tabViews[i].ensureInitialized();
                
                int prefixLength = tabId.length() + 1;
                if (historyToken.length() > prefixLength) {
                    String restOfToken = historyToken.substring(prefixLength);
                    tabViews[i].handleHistoryToken(restOfToken);
                }
                
                tabViews[i].display();
                if (mainTabPanel.getTabBar().getSelectedTab() != i)
                    mainTabPanel.selectTab(i);
                
                return;
            }
        }
    }
}
