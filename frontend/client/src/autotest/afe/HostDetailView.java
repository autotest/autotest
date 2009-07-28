package autotest.afe;

import autotest.common.SimpleCallback;
import autotest.common.Utils;
import autotest.common.table.DataSource;
import autotest.common.table.DataTable;
import autotest.common.table.DynamicTable;
import autotest.common.table.RpcDataSource;
import autotest.common.table.SelectionManager;
import autotest.common.table.SimpleFilter;
import autotest.common.table.TableDecorator;
import autotest.common.table.DataSource.DataCallback;
import autotest.common.table.DataSource.SortDirection;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.SelectionManager.SelectableRowFilter;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.DetailView;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.Widget;

public class HostDetailView extends DetailView 
                            implements DataCallback, TableActionsListener, SelectableRowFilter {
    private static final String[][] HOST_JOBS_COLUMNS = {
            {DataTable.WIDGET_COLUMN, ""}, {"type", "Type"}, {"job__id", "Job ID"}, 
            {"job_owner", "Job Owner"}, {"job_name", "Job Name"}, {"started_on", "Time started"},
            {"status", "Status"}
    };
    public static final int JOBS_PER_PAGE = 20;
    
    public interface HostDetailListener {
        public void onJobSelected(int jobId);
    }
    
    static class HostJobsTable extends DynamicTable {
        private static final DataSource normalDataSource = 
            new RpcDataSource("get_host_queue_entries", "get_num_host_queue_entries");
        private static final DataSource dataSourceWithSpecialTasks = 
            new RpcDataSource("get_host_queue_entries_and_special_tasks",
                              "get_num_host_queue_entries_and_special_tasks");

        private SimpleFilter hostFilter = new SimpleFilter();
        private String hostname;

        public HostJobsTable() {
            super(HOST_JOBS_COLUMNS, normalDataSource);
            addFilter(hostFilter);
        }
        
        public void setHostname(String hostname) {
            this.hostname = hostname;
            updateFilter();
        }

        private void updateFilter() {
            String key;
            if (getDataSource() == normalDataSource) {
                key = "host__hostname";
                sortOnColumn("job__id", SortDirection.DESCENDING);
            } else {
                key = "hostname";
                clearSorts();
            }

            hostFilter.clear();
            hostFilter.setParameter(key, new JSONString(hostname));
        }
        
        public void setSpecialTasksEnabled(boolean enabled) {
            if (enabled) {
                setDataSource(dataSourceWithSpecialTasks);
            } else {
                setDataSource(normalDataSource);
            }
            
            updateFilter();
        }

        @Override
        protected void preprocessRow(JSONObject row) {
            JSONObject job = row.get("job").isObject();
            JSONString blank = new JSONString("");
            JSONString jobId = blank, owner = blank, name = blank;
            if (job != null) {
                int id = (int) job.get("id").isNumber().doubleValue();
                jobId = new JSONString(Integer.toString(id));
                owner = job.get("owner").isString();
                name = job.get("name").isString();
            }

            row.put("job__id", jobId);
            row.put("job_owner", owner);
            row.put("job_name", name);

            // get_host_queue_entries() doesn't return type, so fill it in for consistency
            if (!row.containsKey("type")) {
                row.put("type", new JSONString("Job"));
            }
        }
    }
    
    private String hostname = "";
    private DataSource hostDataSource = new HostDataSource();
    private HostJobsTable jobsTable = new HostJobsTable();
    private TableDecorator tableDecorator = new TableDecorator(jobsTable);
    private HostDetailListener listener = null;
    private SelectionManager selectionManager;
    
    private JSONObject currentHostObject;
    
    private Button lockButton = new Button();
    private Button reverifyButton = new Button("Reverify");
    private CheckBox showSpecialTasks = new CheckBox();

    public HostDetailView(HostDetailListener listener) {
        this.listener = listener;
    }

    @Override
    public String getElementId() {
        return "view_host";
    }

    @Override
    protected String getFetchControlsElementId() {
        return "view_host_fetch_controls";
    }
    
    @Override
    protected String getDataElementId() {
        return "view_host_data";
    }
    
    @Override
    protected String getTitleElementId() {
        return "view_host_title";
    }

    @Override
    protected String getNoObjectText() {
        return "No host selected";
    }
    
    @Override
    protected String getObjectId() {
        return hostname;
    }
    
    @Override
    protected void setObjectId(String id) {
        if (id.length() == 0)
            throw new IllegalArgumentException();
        this.hostname = id;
    }
    
    @Override
    protected void fetchData() {
        JSONObject params = new JSONObject();
        params.put("hostname", new JSONString(hostname));
        hostDataSource.updateData(params, this);
    }
    
    public void onGotData(int totalCount) {
        hostDataSource.getPage(null, null, null, this);
    }
    
    public void handlePage(JSONArray data) {
        try {
            currentHostObject = Utils.getSingleValueFromArray(data).isObject();
        }
        catch (IllegalArgumentException exc) {
            NotifyManager.getInstance().showError("No such host found");
            resetPage();
            return;
        }
        
        showField(currentHostObject, "status", "view_host_status");
        showField(currentHostObject, "platform", "view_host_platform");
        showField(currentHostObject, HostDataSource.HOST_ACLS, "view_host_acls");
        showField(currentHostObject, HostDataSource.OTHER_LABELS, "view_host_labels");
        showField(currentHostObject, HostDataSource.LOCKED_TEXT, "view_host_locked");
        showField(currentHostObject, "protection", "view_host_protection");
        String pageTitle = "Host " + hostname;
        updateLockButton();
        displayObjectData(pageTitle);
        
        DOM.setElementProperty(DOM.getElementById("view_host_logs_link"), "href",
                getLogLink(hostname));
        
        jobsTable.setHostname(hostname);
        jobsTable.refresh();
    }

    private String getLogLink(String hostname) {
        return "/results/hosts/" + hostname;
    }
    
    @Override
    public void initialize() {
        super.initialize();
        
        jobsTable.setRowsPerPage(JOBS_PER_PAGE);
        jobsTable.setClickable(true);
        jobsTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                if (isJobRow(row)) {
                    JSONObject job = row.get("job").isObject();
                    int jobId = (int) job.get("id").isNumber().doubleValue();
                    listener.onJobSelected(jobId);
                } else {
                    String resultsPath = Utils.jsonToString(row.get("execution_path"));
                    Utils.openUrlInNewWindow(Utils.getRetrieveLogsUrl(resultsPath));
                }
            }

            public void onTableRefreshed() {}
        });
        tableDecorator.addPaginators();
        selectionManager = tableDecorator.addSelectionManager(false);
        selectionManager.setSelectableRowFilter(this);
        jobsTable.setWidgetFactory(selectionManager);
        tableDecorator.addTableActionsPanel(this, true);
        tableDecorator.addControl("Show verifies, repairs and cleanups", showSpecialTasks);
        RootPanel.get("view_host_jobs_table").add(tableDecorator);
        
        showSpecialTasks.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                jobsTable.setSpecialTasksEnabled(showSpecialTasks.isChecked());
                jobsTable.refresh();
            }
        });
        
        lockButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
               boolean locked = currentHostObject.get("locked").isBoolean().booleanValue();
               changeLock(!locked);
            } 
        });
        RootPanel.get("view_host_lock_button").add(lockButton);
        
        reverifyButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                JSONObject params = new JSONObject();
                
                params.put("id", currentHostObject.get("id"));
                AfeUtils.callReverify(params, new SimpleCallback() {
                    public void doCallback(Object source) {
                       refresh();
                    }
                }, "Host " + hostname);
            }
        });
        RootPanel.get("view_host_reverify_button").add(reverifyButton);
    }

    public void onError(JSONObject errorObject) {
        // RPC handler will display error
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Abort job entries", new Command() {
            public void execute() {
                abortSelectedQueueEntries();
            }
        });
        return menu;
    }

    private void abortSelectedQueueEntries() {
        AfeUtils.abortHostQueueEntries(selectionManager.getSelectedObjects(), new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            } 
        });
    }
    
    private void updateLockButton() {
        boolean locked = currentHostObject.get("locked").isBoolean().booleanValue();
        if (locked) {
            lockButton.setText("Unlock");
        } else {
            lockButton.setText("Lock");
        }
    }
    
    private void changeLock(final boolean lock) {
        JSONArray hostIds = new JSONArray();
        hostIds.set(0, currentHostObject.get("id"));
        
        AfeUtils.changeHostLocks(hostIds, lock, "Host " + hostname, new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }
    
    private boolean isJobRow(JSONObject row) {
        String type = Utils.jsonToString(row.get("type"));
        return type.equals("Job");
    }

    public boolean isRowSelectable(JSONObject row) {
        return isJobRow(row);
    }
}
