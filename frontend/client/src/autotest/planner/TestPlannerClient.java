package autotest.planner;

import autotest.common.CustomHistory;
import autotest.common.JsonRpcProxy;
import autotest.common.SiteCommonClassFactory;
import autotest.common.StaticDataRepository;
import autotest.common.ui.CustomTabPanel;
import autotest.common.ui.NotifyManager;
import autotest.planner.machine.MachineViewTab;
import autotest.planner.overview.OverviewTab;
import autotest.planner.test.TestViewTab;
import autotest.planner.triage.TriageViewTab;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.user.client.ui.RootPanel;

public class TestPlannerClient implements EntryPoint {

    private TestPlanSelector planSelector = new TestPlanSelector();
    private TestPlanSelectorDisplay planSelectorView = new TestPlanSelectorDisplay();

    private OverviewTab overviewTab = new OverviewTab(planSelector);
    private MachineViewTab machineViewTab = new MachineViewTab(planSelector);
    private TestViewTab testViewTab = new TestViewTab(planSelector);
    private TriageViewTab triageViewTab = new TriageViewTab(planSelector);

    private AutoprocessedTab autoprocessedTab = new AutoprocessedTab();
    private AutoprocessedTabDisplay autoprocessedTabDisplay = new AutoprocessedTabDisplay();

    private HistoryTab historyTab = new HistoryTab();
    private HistoryTabDisplay historyTabDisplay = new HistoryTabDisplay();

    private CustomTabPanel mainTabPanel = new CustomTabPanel();

    public void onModuleLoad() {
        JsonRpcProxy.setDefaultBaseUrl(JsonRpcProxy.PLANNER_BASE_URL);

        NotifyManager.getInstance().initialize();

        StaticDataRepository.getRepository().refresh(
                                 new StaticDataRepository.FinishedCallback() {
            public void onFinished() {
                finishLoading();
            }
        });
    }

    private void finishLoading() {
        SiteCommonClassFactory.globalInitialize();

        autoprocessedTab.bindDisplay(autoprocessedTabDisplay);
        historyTab.bindDisplay(historyTabDisplay);

        planSelectorView.initialize();
        planSelector.bindDisplay(planSelectorView);
        mainTabPanel.getCommonAreaPanel().add(planSelectorView);

        mainTabPanel.addTabView(overviewTab);
        mainTabPanel.addTabView(machineViewTab);
        mainTabPanel.addTabView(testViewTab);
        mainTabPanel.addTabView(triageViewTab);
        mainTabPanel.addTabView(autoprocessedTabDisplay);
        mainTabPanel.addTabView(historyTabDisplay);

        final RootPanel tabsRoot = RootPanel.get("tabs");
        tabsRoot.add(mainTabPanel);
        CustomHistory.processInitialToken();
        mainTabPanel.initialize();
        tabsRoot.removeStyleName("hidden");
    }
}
