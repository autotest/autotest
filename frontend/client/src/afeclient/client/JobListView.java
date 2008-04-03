package afeclient.client;

import afeclient.client.table.LinkSetFilter;
import afeclient.client.table.ListFilter;
import afeclient.client.table.SelectionManager;
import afeclient.client.table.TableDecorator;
import afeclient.client.table.DynamicTable.DynamicTableListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.History;
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
    
    class JobStateFilter extends LinkSetFilter {
        public void addParams(JSONObject params) {
            params.put(filterStrings[getSelectedLink()], 
                       JSONBoolean.getInstance(true));
        }

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
    
    public String getElementId() {
        return "job_list";
    }

    public void refresh() {
        super.refresh();
        jobTable.refresh();
    }

    protected void populateUsers() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray userArray = staticData.getData("users").isArray();
        String[] userStrings = Utils.JSONtoStrings(userArray);
        ownerFilter.setChoices(userStrings);
        String currentUser = staticData.getData("user_login").isString().stringValue();
        ownerFilter.setSelectedChoice(currentUser);
    }

    public JobListView(JobSelectListener listener) {
        selectListener = listener;
    }
    
    public void initialize() {
        jobTable = new JobTable();
        jobTable.setRowsPerPage(JOBS_PER_PAGE);
        jobTable.setClickable(true);
        jobTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                int jobId = (int) row.get("id").isNumber().getValue();
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
        jobStateFilter.addListener(new SimpleCallback() {
            public void doCallback(Object source) {
                History.newItem(getHistoryToken());
            } 
        });
        jobTable.addFilter(jobStateFilter);
        HorizontalPanel jobControls = new HorizontalPanel();
        jobControls.add(jobStateFilter.getWidget());
        
        RootPanel.get("job_control_links").add(jobControls);

        // all jobs is selected by default
        jobStateFilter.setSelectedLink(ALL);
    }

    public String getHistoryToken() {
        return super.getHistoryToken() + "_" + 
               historyTokens[jobStateFilter.getSelectedLink()];
    }
    
    public void handleHistoryToken(String token) {
        for (int i = 0; i < LINK_COUNT; i++) {
            if (token.equals(historyTokens[i]))
                jobStateFilter.setSelectedLink(i);
        }
    }
}
