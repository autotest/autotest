package autotest.tko;

import autotest.common.CustomHistory;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.ui.CustomTabPanel;
import autotest.common.ui.NotifyManager;
import autotest.tko.SpreadsheetView.SpreadsheetViewListener;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.user.client.ui.RootPanel;

public class TkoClient implements EntryPoint, SpreadsheetViewListener {
    private CommonPanel commonPanel;
    private SpreadsheetView spreadsheetView;
    private TableView tableView;
    private GraphingView graphingView;
    private TestDetailView detailView;
    
    private CustomTabPanel mainTabPanel = new CustomTabPanel();
    private SavedQueriesControl savedQueriesControl;
    
    public void onModuleLoad() {
        JsonRpcProxy.setDefaultUrl(JsonRpcProxy.TKO_URL);
        
        NotifyManager.getInstance().initialize();
        
        StaticDataRepository.getRepository().refresh(
                                 new StaticDataRepository.FinishedCallback() {
            public void onFinished() {
                finishLoading();
            }
        });
    }
    
    protected void finishLoading() {
        commonPanel = CommonPanel.getPanel();
        spreadsheetView = new SpreadsheetView(this);
        tableView = new TableView(this);
        graphingView = new GraphingView();
        detailView = new TestDetailView();
        
        mainTabPanel.getCommonAreaPanel().add(commonPanel);
        mainTabPanel.addTabView(spreadsheetView);
        mainTabPanel.addTabView(tableView);
        mainTabPanel.addTabView(graphingView);
        mainTabPanel.addTabView(detailView);
        
        savedQueriesControl = new SavedQueriesControl();
        mainTabPanel.getOtherWidgetsPanel().add(savedQueriesControl);
        
        final RootPanel tabsRoot = RootPanel.get("tabs");
        tabsRoot.add(mainTabPanel);
        CustomHistory.processInitialToken();
        mainTabPanel.initialize();
        commonPanel.initialize();
        tabsRoot.removeStyleName("hidden");
    }
    
    public void onSwitchToTable(boolean isTriageView) {
        tableView.ensureInitialized();
        if (isTriageView) {
            tableView.setupJobTriage();
        } else {
            tableView.setupDefaultView();
        }
        tableView.doQuery();
        mainTabPanel.selectTabView(tableView);
    }

    public void onSelectTest(int testId) {
        detailView.ensureInitialized();
        detailView.updateObjectId(Integer.toString(testId));
        mainTabPanel.selectTabView(detailView);
    }
}
