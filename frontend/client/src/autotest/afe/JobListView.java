package autotest.afe;

import autotest.common.CustomHistory;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.LinkSetFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableDecorator;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.Paginator;
import autotest.common.ui.TabView;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Hyperlink;
import com.google.gwt.user.client.ui.RootPanel;

public class JobListView extends TabView {
    protected static final String ALL_USERS = "All Users";
    protected static final String SELECTED_LINK_STYLE = "selected-link";
    protected static final int JOBS_PER_PAGE = 30;
    protected static final int QUEUED = 0, RUNNING = 1, FINISHED = 2, 
                               ALL = 3, LINK_COUNT = 4;
    protected static final String[] historyTokens = {"queued", "running", 
                                                     "finished", "all"};
    protected static final String[] linkLabels = {"Queued Jobs", "Running Jobs",
                                                  "Finished Jobs", "All Jobs"};
    protected static final String[] filterStrings = {"not_yet_run", "running",
                                                     "finished"};
    
    interface JobSelectListener {
        public void onJobSelected(int jobId);
    }
    
    static class JobStateFilter extends LinkSetFilter {
        @Override
        public void addParams(JSONObject params) {
            params.put(filterStrings[getSelectedLink()], 
                       JSONBoolean.getInstance(true));
        }

        @Override
        public boolean isActive() {
            return getSelectedLink() < ALL;
        }
    }

    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected JSONObject jobFilterArgs = new JSONObject();
    protected JobSelectListener selectListener;

    protected JobTable jobTable;
    protected TableDecorator tableDecorator;
    protected SelectionManager selectionManager;
    protected JobStateFilter jobStateFilter;
    protected ListFilter ownerFilter;
    protected Paginator paginator;

    protected Hyperlink nextLink, prevLink;
    
    @Override
    public String getElementId() {
        return "job_list";
    }

    @Override
    public void refresh() {
        super.refresh();
        jobTable.refresh();
    }

    protected void populateUsers() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray userArray = staticData.getData("users").isArray();
        String[] userStrings = Utils.JSONObjectsToStrings(userArray, "login");
        ownerFilter.setChoices(userStrings);
        String currentUser = staticData.getData("user_login").isString().stringValue();
        ownerFilter.setSelectedChoice(currentUser);
    }

    public JobListView(JobSelectListener listener) {
        selectListener = listener;
    }
    
    @Override
    public void initialize() {
        jobTable = new JobTable();
        jobTable.setRowsPerPage(JOBS_PER_PAGE);
        jobTable.setClickable(true);
        jobTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                int jobId = (int) row.get("id").isNumber().doubleValue();
                selectListener.onJobSelected(jobId);
            }
            
            public void onTableRefreshed() {}
        });
        
        tableDecorator = new TableDecorator(jobTable);
        tableDecorator.addPaginators();
        RootPanel.get("job_table").add(tableDecorator);
        
        ownerFilter = new ListFilter("owner");
        ownerFilter.setMatchAllText("All users");
        jobTable.addFilter(ownerFilter);
        populateUsers();
        RootPanel.get("user_list").add(ownerFilter.getWidget());
        
        jobStateFilter = new JobStateFilter();
        for (int i = 0; i < LINK_COUNT; i++)
            jobStateFilter.addLink(linkLabels[i]);
        // all jobs is selected by default
        jobStateFilter.setSelectedLink(ALL);
        jobStateFilter.addListener(new SimpleCallback() {
            public void doCallback(Object source) {
                CustomHistory.newItem(getHistoryToken());
            } 
        });
        jobTable.addFilter(jobStateFilter);
        HorizontalPanel jobControls = new HorizontalPanel();
        jobControls.add(jobStateFilter.getWidget());
        
        RootPanel.get("job_control_links").add(jobControls);
    }

    @Override
    public String getHistoryToken() {
        return super.getHistoryToken() + "_" + 
               historyTokens[jobStateFilter.getSelectedLink()];
    }
    
    @Override
    public void handleHistoryToken(String token) {
        for (int i = 0; i < LINK_COUNT; i++) {
            if (token.equals(historyTokens[i]))
                jobStateFilter.setSelectedLink(i);
        }
    }
}
