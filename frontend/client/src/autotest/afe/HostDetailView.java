package afeclient.client;

import afeclient.client.table.DataSource;
import afeclient.client.table.DynamicTable;
import afeclient.client.table.RpcDataSource;
import afeclient.client.table.SimpleFilter;
import afeclient.client.table.TableDecorator;
import afeclient.client.table.DataSource.DataCallback;
import afeclient.client.table.DynamicTable.DynamicTableListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.RootPanel;

public class HostDetailView extends DetailView implements DataCallback {
    public static final String[][] HOST_JOBS_COLUMNS = {
            {"job_id", "Job ID"}, {"job_owner", "Job Owner"}, 
            {"job_name", "Job Name"}, {"status", "Status"}
    };
    public static final int JOBS_PER_PAGE = 20;
    
    public interface HostDetailListener {
        public void onJobSelected(int jobId);
    }
    
    class HostJobsTable extends DynamicTable {
        public HostJobsTable(String[][] columns, DataSource dataSource) {
            super(columns, dataSource);
        }

        protected void preprocessRow(JSONObject row) {
            JSONObject job = row.get("job").isObject();
            int jobId = (int) job.get("id").isNumber().getValue();
            row.put("job_id", new JSONString(Integer.toString(jobId)));
            row.put("job_owner", job.get("owner"));
            row.put("job_name", job.get("name"));
        }
    }
    
    protected String hostname = "";
    protected DataSource hostDataSource = new HostDataSource();
    protected DynamicTable jobsTable = 
        new HostJobsTable(HOST_JOBS_COLUMNS, 
                          new RpcDataSource("get_host_queue_entries", 
                                            "get_num_host_queue_entries"));
    protected TableDecorator tableDecorator = new TableDecorator(jobsTable);
    protected SimpleFilter hostFilter = new SimpleFilter();
    protected HostDetailListener listener = null;

    public HostDetailView(HostDetailListener listener) {
        this.listener = listener;
    }

    public String getElementId() {
        return "view_host";
    }

    protected String getFetchControlsElementId() {
        return "view_host_fetch_controls";
    }
    
    protected String getDataElementId() {
        return "view_host_data";
    }
    
    protected String getTitleElementId() {
        return "view_host_title";
    }

    protected String getNoObjectText() {
        return "No host selected";
    }
    
    protected String getObjectId() {
        return hostname;
    }
    
    protected void setObjectId(String id) {
        if (id.length() == 0)
            throw new IllegalArgumentException();
        this.hostname = id;
    }
    
    protected void fetchData() {
        JSONObject params = new JSONObject();
        params.put("hostname", new JSONString(hostname));
        hostDataSource.updateData(params, this);
    }
    
    public void onGotData(int totalCount) {
        hostDataSource.getPage(null, null, null, null, this);
    }
    
    public void handlePage(JSONArray data) {
        JSONObject hostObject;
        try {
            hostObject = Utils.getSingleValueFromArray(data).isObject();
        }
        catch (IllegalArgumentException exc) {
            NotifyManager.getInstance().showError("No such host found");
            resetPage();
            return;
        }
        
        showField(hostObject, "status", "view_host_status");
        showField(hostObject, "platform", "view_host_platform");
        showField(hostObject, HostDataSource.OTHER_LABELS, "view_host_labels");
        showField(hostObject, HostDataSource.LOCKED_TEXT, "view_host_locked");
        String title = "Host " + hostname;
        displayObjectData(title);
        
        hostFilter.setParameter("host__hostname", new JSONString(hostname));
        jobsTable.refresh();
    }

    public void initialize() {
        super.initialize();
        
        jobsTable.setRowsPerPage(JOBS_PER_PAGE);
        jobsTable.sortOnColumn("Job ID", DataSource.DESCENDING);
        jobsTable.addFilter(hostFilter);
        jobsTable.setClickable(true);
        jobsTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                JSONObject job = row.get("job").isObject();
                int jobId = (int) job.get("id").isNumber().getValue();
                listener.onJobSelected(jobId);
            }

            public void onTableRefreshed() {}
        });
        tableDecorator.addPaginators();
        RootPanel.get("view_host_jobs_table").add(tableDecorator);
    }
}
