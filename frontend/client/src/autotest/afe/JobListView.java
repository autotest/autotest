package autotest.afe;

import autotest.common.SimpleCallback;
import autotest.common.CustomHistory.HistoryToken;
import autotest.common.table.LinkSetFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.SearchFilter;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableDecorator;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.HorizontalPanel;

import java.util.Map;
import java.util.Set;


public class JobListView extends TabView implements TableActionsListener {
    protected static final String SELECTED_LINK_STYLE = "selected-link";
    protected static final int JOBS_PER_PAGE = 30;
    protected static final int QUEUED = 0, RUNNING = 1, FINISHED = 2, 
                               ALL = 3, LINK_COUNT = 4;
    private static final int DEFAULT_LINK = ALL;
    private static final String[] historyTokens = {"queued", "running", 
                                                     "finished", "all"};
    private static final String[] linkLabels = {"Queued Jobs", "Running Jobs",
                                                  "Finished Jobs", "All Jobs"};
    private static final String[] filterStrings = {"not_yet_run", "running",
                                                     "finished"};
    
    private JobSelectListener selectListener;

    private JobTable jobTable;
    private TableDecorator tableDecorator;
    private JobStateFilter jobStateFilter;
    private ListFilter ownerFilter;
    private SearchFilter nameFilter;
    private SelectionManager selectionManager;
    
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
    
    public void abortSelectedJobs() {
        Set<JSONObject> selectedSet = selectionManager.getSelectedObjects();
        if (selectedSet.isEmpty()) {
            NotifyManager.getInstance().showError("No jobs selected");
            return;
        }
        
        JSONArray ids = new JSONArray();
        for(JSONObject jsonObj : selectedSet) {
            ids.set(ids.size(), jsonObj.get("id"));
        }
        
        JSONObject params = new JSONObject();
        params.put("job__id__in", ids);
        AfeUtils.callAbort(params, new SimpleCallback() {
            public void doCallback(Object source) {
               refresh();
            }
        });
    }
    
    @Override
    public String getElementId() {
        return "job_list";
    }

    @Override
    public void refresh() {
        super.refresh();
        jobTable.refresh();
    }

    public JobListView(JobSelectListener listener) {
        selectListener = listener;
    }
    
    @Override
    public void initialize() {
        super.initialize();
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
        selectionManager = tableDecorator.addSelectionManager(false);
        jobTable.setWidgetFactory(selectionManager);
        tableDecorator.addTableActionsPanel(this, true);
        addWidget(tableDecorator, "job_table");
        
        ownerFilter = AfeUtils.getUserFilter("owner");
        jobTable.addFilter(ownerFilter);
        addWidget(ownerFilter.getWidget(), "user_list");
        
        nameFilter = new SearchFilter("name", false);
        jobTable.addFilter(nameFilter);
        addWidget(nameFilter.getWidget(), "jl_name_search");
        
        jobStateFilter = new JobStateFilter();
        for (int i = 0; i < LINK_COUNT; i++)
            jobStateFilter.addLink(linkLabels[i]);
        // all jobs is selected by default
        jobStateFilter.setSelectedLink(DEFAULT_LINK);
        jobStateFilter.addCallback(new SimpleCallback() {
            public void doCallback(Object source) {
                updateHistory();
            } 
        });
        jobTable.addFilter(jobStateFilter);
        HorizontalPanel jobControls = new HorizontalPanel();
        jobControls.add(jobStateFilter.getWidget());
        
        addWidget(jobControls, "job_control_links");
    }

    @Override
    public HistoryToken getHistoryArguments() {
        HistoryToken arguments = super.getHistoryArguments();
        arguments.put("state_filter", historyTokens[jobStateFilter.getSelectedLink()]);
        return arguments;
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        String stateFilter = arguments.get("state_filter");
        if (stateFilter == null) {
            jobStateFilter.setSelectedLink(DEFAULT_LINK);
            return;
        }
        
        for (int i = 0; i < LINK_COUNT; i++) {
            if (stateFilter.equals(historyTokens[i])) {
                jobStateFilter.setSelectedLink(i);
                return;
            }
        }
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Abort jobs", new Command() {
            public void execute() {
                abortSelectedJobs();
            }
        });
        return menu;
    }
}
