package afeclient.client;

import afeclient.client.table.DataSource;
import afeclient.client.table.DynamicTable;
import afeclient.client.table.RpcDataSource;
import afeclient.client.table.SimpleFilter;
import afeclient.client.table.TableDecorator;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.RootPanel;

public class HostDetailView extends DetailView {
    public static final String[][] HOST_JOBS_COLUMNS = {
            {"job", "Job ID"}, {"status", "Status"}
    };
    public static final int JOBS_PER_PAGE = 20;
    
    protected String hostname = "";
    protected DynamicTable jobsTable = 
        new DynamicTable(HOST_JOBS_COLUMNS, 
                         new RpcDataSource("get_host_queue_entries", 
                                           "get_num_host_queue_entries"));
    protected TableDecorator tableDecorator = new TableDecorator(jobsTable);
    protected SimpleFilter hostFilter = new SimpleFilter();

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
        rpcProxy.rpcCall("get_hosts", params, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                JSONObject hostObject;
                try {
                    hostObject = Utils.getSingleValueFromArray(result.isArray()).isObject();
                }
                catch (IllegalArgumentException exc) {
                    NotifyManager.getInstance().showError("No such host found");
                    resetPage();
                    return;
                }
                
                showField(hostObject, "status", "view_host_status");
                String title = "Host " + hostname;
                displayObjectData(title);
                
                hostFilter.setParameter("host__hostname", new JSONString(hostname));
                jobsTable.refresh();
            } 
        });
    }
    
    public void initialize() {
        super.initialize();
        
        jobsTable.setRowsPerPage(JOBS_PER_PAGE);
        jobsTable.sortOnColumn("Job ID", DataSource.DESCENDING);
        jobsTable.addFilter(hostFilter);
        tableDecorator.addPaginators();
        RootPanel.get("view_host_jobs_table").add(tableDecorator);
    }
}
